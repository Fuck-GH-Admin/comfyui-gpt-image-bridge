# 协议与实现：CLIProxyAPI ↔ GPT Image Bridge

本手册用于解释 **本 fork 现在实际发什么请求、在哪个层面做转换、什么由 CLIProxyAPI 负责**。它不是对 Codex 非公开上游接口的稳定性承诺。适用版本：插件 v0.6.0 开发分支；CLIProxyAPI 的 v8 路由设计以 [官方仓库](https://github.com/router-for-me/CLIProxyAPI) 源码为准。

## 1. 责任边界

```text
ComfyUI (实际工作流引擎)
    │ GRAPH: Provider → Generate/Edit → Save Image
    ▼
GPT Image Bridge (Python 自定义节点)
    ├─ 参数/参考图次序验证
    ├─ IMAGE/MASK ↔ PNG 编码
    ├─ 选择 Images 或 Responses 协议
    ├─ 使用一次性句柄解析 CLIProxyAPI 客户端 Key
    ├─ HTTP 请求、响应解析与错误脱敏
    └─ 输出 IMAGE、revised_prompt、request_report
    │
    ▼  /v1/* + Bearer <CLIProxyAPI client key>
CLIProxyAPI v8（独立进程）
    ├─ 验证客户端 Key
    ├─ 管理 Codex OAuth 登录/续期/账号选择
    ├─ 模型路由、图片接口转换、上游错误
    └─ 转发/调用 Codex 图片生成服务
    │
    ▼
Codex/图片服务（远端，订阅额度与模型能力由服务端决定）
```

两端的 Key 含义不同。插件只需要 CLIProxyAPI 颁发的客户端 Key；**不要在插件中填 Codex OAuth Access/Refresh Token**。

源码定位：

| 组件 | 本 fork | 主要职责 |
| --- | --- | --- |
| 节点 | [nodes.py](../nodes.py) | 6 个节点、参数、Generate/Edit 输出 |
| 配置 | [gpt_image_bridge/config.py](../gpt_image_bridge/config.py) | ProviderConfig、端点规范化、校验、独立 responses_model |
| 协议 | [gpt_image_bridge/protocols.py](../gpt_image_bridge/protocols.py) | 选路、请求体、Images/Responses 解析、n 次数、报告 |
| 传输 | [gpt_image_bridge/transport.py](../gpt_image_bridge/transport.py) | HTTP、重试、重定向约束与响应限制 |
| 图像 | [gpt_image_bridge/images.py](../gpt_image_bridge/images.py) | ComfyUI IMAGE、Base64、PNG、图片边界 |
| 浏览器控件 | [gpt_image_bridge/web/api_key_widget.js](../gpt_image_bridge/web/api_key_widget.js) | 密码控件和一次性队列句柄 |
| 队列路由 | [gpt_image_bridge/routes.py](../gpt_image_bridge/routes.py) | 会话凭据 HTTP 端点、/prompt 守卫 |
| Key 句柄 | [gpt_image_bridge/session_credentials.py](../gpt_image_bridge/session_credentials.py) | 进程内凭据缓存与消耗 |

CLIProxyAPI 参考：[Codex Images 执行器](https://github.com/router-for-me/CLIProxyAPI/blob/main/internal/runtime/executor/codex_openai_images.go)、[OpenAI Images 处理器](https://github.com/router-for-me/CLIProxyAPI/blob/main/sdk/api/handlers/openai/openai_images_handlers.go)、[v8 配置样例](https://github.com/router-for-me/CLIProxyAPI/blob/main/config.example.yaml)。

## 2. 三条主要路由

### A. 无参考图的 Generate：Images JSON

```http
POST /v1/images/generations
Authorization: Bearer <CLIProxyAPI-client-key>
Content-Type: application/json
```

请求主要字段：

```json
{
  "model": "gpt-image-2",
  "prompt": "a blue ceramic cup on a wooden table",
  "size": "auto",
  "quality": "auto",
  "n": 1
}
```

实际请求体由 `protocols.py::_images_request` 构造，可能包含其他用户所选的兼容字段；上面是**字段说明示例**，不是所有代理和模型都逐项支持的万能请求。图片响应通常是：

```json
{
  "data": [
    {
      "b64_json": "<base64 encoded image>"
    }
  ]
}
```

协议层可以解析 Base64 结果或受限的图片 URL 结果。URL 下载的响应数据随后也会经过图片格式及尺寸校验。

### B. 有参考图的 Generate：Responses + 图片工具

这条路线不是单纯把输入图片附加到 `/images/generations`；它调用 `/v1/responses`：

```http
POST /v1/responses
Authorization: Bearer <CLIProxyAPI-client-key>
Content-Type: application/json
Accept: text/event-stream, application/json
```

关键字段的简化示例：

```json
{
  "model": "gpt-5.4-mini",
  "input": [
    {"role": "developer", "content": "Generate a new image rather than editing any reference."},
    {
      "role": "user",
      "content": [
        {"type": "input_text", "text": "Reference 1: use its lighting; create a new image"},
        {"type": "input_image", "image_url": "data:image/png;base64,<reference-image>"}
      ]
    }
  ],
  "tools": [
    {
      "type": "image_generation",
      "model": "gpt-image-2",
      "action": "generate"
    }
  ],
  "tool_choice": {"type": "image_generation"},
  "stream": true
}
```

真实实现还会给 `image_generation` 工具传递尺寸、质量、背景、格式和审核等字段，设置明确的开发者指令，并按连接顺序给参考图编号。

**两个模型的角色不得混淆：**

- 顶层 `model` = `responses_model`，普通 Codex Responses 主模型。
- `tools[0].model` = `image_model`，希望调用的图片工具模型。
- 用户可在节点 UI 分别改这两个名字；是否被服务端接受须真实账号验证。

返回既可能是普通 JSON，也可能是 SSE 数据流。插件只在解析到实际 `image_generation_call` 图片结果时才认为有图片；普通文字回复或拒绝不能当成成功的生图。

简化 SSE 结束事件示例：

```text
data: {"type":"response.completed","response":{"output":[{"type":"image_generation_call","result":"<base64-image>"}]}}
```

### C. Edit：Images multipart

```http
POST /v1/images/edits
Authorization: Bearer <CLIProxyAPI-client-key>
Content-Type: multipart/form-data; boundary=<generated-boundary>
```

主要部分：

```text
model         = gpt-image-2
prompt        = edit Image 1; use Image 2 as reference
image[]       = image-1-base.png
image[]       = image-2-reference.png
image[]       = image-3-reference.png
...           = 可选 mask/尺寸等表单字段
```

Image 1 必须是待编辑的基础图，所有参考图在其后面，且保持顺序。这里的 `image[]` 来自真实测试的 multipart 约定，**不是把多个 IMAGE 帧塞进一个 ComfyUI 插口**。

Mask 能否生效由代理与模型决定；没有真实后端支持时不能把它当作一定可用。

## 3. 自动选择与不可用路径

`GPTImageBridgeCLIProxyAPIProvider.build()` 调用 `ProviderConfig.from_api_inputs()`，把 `api_protocol` 固定为 `auto`，把 `use_async` 固定为 `False`，并设置独立的 `responses_model`。因此实际路由选择：

| Operation | References | Protocol | Endpoint |
| --- | --- | --- | --- |
| Generate | 0 | images | `/v1/images/generations` |
| Generate | 1–9 | responses | `/v1/responses` |
| Edit | 0–8 + 必需的基础图 | images | `/v1/images/edits` |

该专用 Provider **不会尝试** `/images/generations/async`、`/images/edits/async`、`/images/tasks/{task_id}`。对于其他兼容服务的异步任务，改用通用 API Provider；详见 [兼容 API 与异步任务](compatibility-and-async.md)。

如果服务因网络问题、429 或 5xx 失败，代码不会擅自从 Images 切到 Responses，也不会自动重放一个可能已创建付费图片的 POST。这样做是为避免重复生成，不是保证上游一定没有完成请求。

## 4. `n` 的明确语义

CLIProxyAPI 专用节点为避免代理不支持 `n>1` 而静默少图，**对 Images Generate / Edit 使用一张一次请求的策略**。例如：

```text
n=3
  POST /v1/images/generations (n=1) ─► image 1
  POST /v1/images/generations (n=1) ─► image 2
  POST /v1/images/generations (n=1) ─► image 3
  → combined IMAGE batch
```

Responses 同样按 `n` 重复调用，而不期望一次工具调用必然输出多张。它们是独立的远端使用行为，不保证相同 seed、图像一致性或费用合并。

达到本地超时、上游拒绝、解码错误时节点会失败；**先前已送出的请求不能从 ComfyUI 侧撤销**。排障时看 `request_report` 和代理日志中的请求次数，而不是只看最终文件数。

## 5. Base URL 和认证语义

`base_url` 是代理入口，建议填 `http://127.0.0.1:8317/v1`。正常代码会处理末尾 `/`，并避免标准端点重复拼接 `/v1/v1`。一般无需在 Base URL 后写 `images/generations`；那是请求路径，不是服务根。

插件发给代理的客户端 Key 使用 `Authorization: Bearer ...`。具体认证从浏览器控件进入 `/gpt-image-bridge/session-credential`、生成一次性内存句柄、通过 ComfyUI 队列再交给 Provider；详见 [安全与凭据](security.md)。

**它不会向 CLIProxyAPI 自动提供 Codex 的登录状态。** Codex OAuth 登录必须单独在 CLIProxyAPI 自身配置；即使 API Key 正确，代理仍可能由于未登录或模型不可用而无法生成。

## 6. 返回解析、报告和错误

成功结果需要转换成实际可解码的图片数据，随后输出 `IMAGE`。常见响应约定：

| 协议 | 典型返回 | 插件动作 |
| --- | --- | --- |
| Images | `data[].b64_json` | Base64 解码，验证图像字节 |
| Images | `data[].url` | 只下载通过安全检查的图片 URL，不转发 Bearer |
| Responses | JSON 中的 `image_generation_call.result` | 提取并解码图像 |
| Responses | SSE 事件中的 `image_generation_call` | 解析事件、汇总图片 |
| 无实际图片 | 拒绝、只有文字、空结果、损坏图片 | 按失败处理，不伪造成功 |

HTTP 请求是带凭据请求，因此不跟随可能泄漏 Authorization 的跨站重定向。对图片 URL 下载会进行 SSRF/地址、MIME、大小等检查。网络是否可达与服务器是否接受协议是两种不同故障。

`request_report` 是**脱敏 JSON 字符串**，用于诊断协议、模型、耗时、HTTP 状态、请求 ID 等。不得把它解释为能证明真实模型 ID、内部后端版本、实际订阅扣费或任务取消成功。

## 7. 为什么当前还需要实机验收？

[ComfyUI 集成 CI](testing.md) 确认了插件在真实 ComfyUI 的请求构造、图片后处理和保存流程。但是测试替身按上述 HTTP 约定返回图片，**没有启动 CLIProxyAPI 本体，没有加载 Codex OAuth，也没有请求远端真实模型**。

只有按 [本机安装](setup-cli-proxy-api.md) 完成登录，并从 ComfyUI 实际生成图像后，才能把「服务端图片生成」这一列标记为通过。接口来自演进中的 Codex 服务；客户端代码可测不代表服务端账户长期保证可用。
