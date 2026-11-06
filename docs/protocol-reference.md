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

## 2. 图片优先：默认 Images，Responses 可选

### A. 无参考图 Generate → Images JSON

```http
POST /v1/images/generations
Authorization: Bearer <CLIProxyAPI-client-key>
Content-Type: application/json
```

示例请求：`{"model":"gpt-image-2.6-flare","prompt":"a ceramic cup","size":"auto","n":1}`。当 `image_complexity` 为 `low`、`medium`、`high` 时，**插件向 CLIProxyAPI 提交的 JSON** 会增加对应 `complexity` 字段；`auto` 不发送。但 CLIProxyAPI **v8.0.57** 构建 Codex Images 工具请求时使用固定 allowlist，不会继续转发该字段，因此不能认为复杂度已生效。

### B. 有参考图 Generate，默认 Images Edit

`reference_mode=images_edit` 时：

```http
POST /v1/images/edits
Content-Type: multipart/form-data
```

Generate 的 `reference_1` 作为 Image 1 输入，后续参考图依次作为 Image 2、3……上传。单图使用 multipart 的 `image` 字段，多图使用有序 `image[]`。提示词前缀明确说“Create a NEW image guided by the supplied reference images. Image 1 is a visual reference, not a canvas to preserve or minimally edit.”

这里的 Images Edit 只是**参考图引导式新图生成**：和无图的 Images Generations 语义不同，可能保留参考图布局。插件报告里仍保留用户的 `operation=generate`，但通过 `reference_generation.mode=images_edit`、`transport_operation=edit` 明确披露请求真实路径。**不会隐式调用文本/Agent 主模型**。

### C. 有参考图 Generate，手动选 Responses

`reference_mode=responses` 时，向 `POST /v1/responses` 发送：

```json
{
  "model": "your-available-text-model",
  "input": [
    {"role":"developer","content":"Generate a new image."},
    {"role":"user","content":[
      {"type":"input_image","image_url":"data:image/png;base64,<reference>"},
      {"type":"input_text","text":"Create a new illustration using the reference"}
    ]}
  ],
  "tools":[{"type":"image_generation","model":"gpt-image-2.6-flare","action":"generate"}],
  "tool_choice":{"type":"image_generation"},
  "stream":true
}
```

顶部 `model` 为用户手动设置的 `responses_model`（文本主模型），`tools[0].model` 为 `image_model`（真正生成图片的模型）。不填写 `responses_model` 则在请求前拒绝；不会默认使用之前实际报过 `model_not_found` 的 `gpt-5.4-mini`。配置非 `auto` 的 `image_complexity` 时它进入**插件提交给代理的**图片工具字段；当前 Responses 实机调用曾受 DNS 问题阻断，尚不能断言代理继续透传或模型执行。

返回可以是 JSON 或 SSE 的 `image_generation_call` 结果；并非所有文本模型都具备图片工具权限。

### D. Edit 节点 → Images Edit

Edit 节点继续通过 `POST /v1/images/edits` multipart 请求：Image 1 是**待修改的基础图**，Image 2～16 是有序参考图，允许附加 Mask（实际模型可能不支持）。`image_complexity` 选择非 `auto` 时进入插件提交的 multipart `complexity` 字段，但 CLIProxyAPI v8.0.57 的 Codex Images 转换层会丢弃该字段。

## 3. 兼容与支持边界

- 新的 `reference_mode` 仅对 CLIProxyAPI Provider 生效，通用 API Provider 和旧 Codex OAuth Provider 原有自动选路不变。
- 该 Provider 关闭异步 Images 探测；不因上游断线自动无条件重发 POST，以免重复使用额度。
- 用户可以填写 `gpt-image-2.6-flare`、`gpt-image-2.6-sunburst` 或仍受支持的旧型号；**模型能否真正访问取决于实际代理与账号权限**。
- 2.6 官方还有 GIF、SVG、markup-guided 编辑，但当前 ComfyUI 插件的 `IMAGE` 仅按 PNG/JPEG/WebP 位图通道工作，不能宣称支持所有 2.6 输出格式。
- 查看[官方版本与型号兼容](model-support.md)，以及旧的[通用 API / 异步任务接口](compatibility-and-async.md)。

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
