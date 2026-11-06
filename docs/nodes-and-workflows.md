# 节点及工作流完整手册

本文面向实际使用 ComfyUI 画布的人。**CLIProxyAPI Provider 是推荐入口**；原生 OAuth Provider、通用 API Provider 继续保留，目的是兼容原有工作流和其他供应商。先按 [本机安装与登录](setup-cli-proxy-api.md) 完成环境准备。

## 1. 六个节点及其职责

| 画布节点名 | 实际类名 | 输入 | 输出/功能 |
| --- | --- | --- | --- |
| GPT Image Bridge · CLIProxyAPI Provider | `GPTImageBridgeCLIProxyAPIProvider` | 客户端 Key、代理地址、图片模型、Responses 主模型 | `GPT_IMAGE_PROVIDER`；推荐 |
| GPT Image Bridge · API Provider | `GPTImageBridgeAPIProvider` | 通用 API Key、Base URL、model、protocol、自定义端点/异步参数 | `GPT_IMAGE_PROVIDER`；第三方兼容 API |
| GPT Image Bridge · Codex OAuth Provider | `GPTImageBridgeOAuthProvider` | 图片 model、protocol | `GPT_IMAGE_PROVIDER`；旧的内置 Codex 登录方案 |
| GPT Image Bridge · Generate | `GPTImageBridgeGenerate` | Provider、提示词、生成参数、至多 9 张独立参考图 | `IMAGE`、`revised_prompt`、`request_report` |
| GPT Image Bridge · Edit | `GPTImageBridgeEdit` | Provider、基础图、提示词、生成参数、参考图列表、可选 MASK | 同上 |
| GPT Image Bridge · Edit Reference List (Image 2–9) | `GPTImageBridgeReferenceList` | `image_2`…`image_9` | `GPT_IMAGE_REFERENCES`，只用于 Edit |

所有节点都在 `GPT Image Bridge` 分类下。需要保存输出时，**手动添加 ComfyUI 的 Save Image 节点**；本插件不是自动写文件节点。

### 主要输出

- `image`：真实 `IMAGE` 张量，可连 Save Image、放大、裁剪等后处理。实际转换为 ComfyUI 图像 batch；当 `n>1` 时，输出多张。
- `revised_prompt`：上游若返回修订后的提示词则提供文本，否则为空串；**不要假定一定有值**。
- `request_report`：字符串形式的脱敏 JSON，包括协议选择依据、请求次数、端点、响应状态与耗时等。它不是图片，也不是上游原始响应；见 [诊断与安全](security.md)。

## 2. CLIProxyAPI Provider 配置

| 控件名 | 默认 | 实际含义 | 常见错误 |
| --- | --- | --- | --- |
| `api_key` | 空 | `config.yaml` 的 `access.api-keys` 中一条客户端 Key | 误填 Codex OAuth Token、误填 OpenAI 平台 API Key |
| `base_url` | `http://127.0.0.1:8317/v1` | 必须是 **ComfyUI 进程可达** 的 CLIProxyAPI HTTP 地址；若是容器，localhost 不指向宿主机 | 把 `/v1` 填两次、端口错误、代理未启动 |
| `image_model` | `gpt-image-2` | Images API 和 Responses 图片工具请求的模型名称；实际支持以当前代理为准 | 将主模型与图片模型混淆 |
| `responses_model` | `gpt-5.4-mini` | 带参考图 Generate 时 `/v1/responses` 的主模型 | 选择未授权或不支持图片工具的模型 |

该 Provider **没有** `api_protocol`、`use_async`、`generate_endpoint`、`edit_endpoint` 等输入。代码固定采用自动路由和同步 Images API；不支持从画布配置自定义异步任务协议。需要其他服务特有协议时换用通用 API Provider。

即使只是第一次做纯文生图，`responses_model` 控件仍需非空（该值在纯文本 Images 请求中不会使用）。

### 路由选择

| 操作 | 条件 | 代理路径 | 特点 |
| --- | --- | --- | --- |
| Generate | 无任何参考图 | `POST /v1/images/generations` | JSON，请求 `model=image_model` |
| Generate | 至少一张参考图 | `POST /v1/responses` | JSON/SSE，`model=responses_model`，`tools[].model=image_model` |
| Edit | 基础图已连接 | `POST /v1/images/edits` | multipart，基础图在 Image 1，参考图依次为 Image 2… |

**这是本 fork 选择的 API 组合，不是所有代理版本都必然支持的接口合同**。如果 References Generate 失败但纯文生图成功，首先排查 `/v1/responses` 模型、工具与 `multimedia.disable-image-generation`，不要反复修改 Images API 地址。

## 3. Generate 参数表

| 输入 | 类型/范围 | 用途与提醒 |
| --- | --- | --- |
| `provider` | `GPT_IMAGE_PROVIDER` | 从上述三个 Provider 之一连接 |
| `prompt` | 多行文本 | 图片生成指令；不能为空 |
| `size` | `auto`、`1024x1024`、`1536x1024`、`1024x1536` | 只表示**请求尺寸**；服务可能不支持或拒绝 |
| `quality` | `auto`、`low`、`medium`、`high` | 不同服务可能只支持一部分 |
| `background` | `auto`、`opaque`、`transparent` | 透明图建议配 PNG/WebP；不保证上游兑现 |
| `output_format` | `png`、`jpeg`、`webp` | 后端返回可能受模型/路由约束；ComfyUI 的 Save Image 通常存 PNG |
| `moderation` | `auto`、`low` | 服务端可能忽略或拒绝 |
| `n` | 整数 1–8 | 需要多少张输出。**CLIProxyAPI 专用模式每张对应一次独立上游请求** |
| `timeout_sec` | 整数 30–3600 | 超过后本地等待结束，未必代表上游操作已取消 |
| `reference_1`…`reference_9` | 可选 `IMAGE` | 按顺序连接，不允许中间空洞；每个入口单张，非 IMAGE batch |

首次接入建议采用全部 `auto`、`png`、`n=1`、`timeout_sec=300`。只有验证了最简单请求后，才调高级选项。

### 文生图连线

可从[无密钥的 CLIProxyAPI 文生图示例](../example_workflows/CLIProxyAPI-Text-to-Image.json)开始，直接拖入 ComfyUI 画布后填客户端 Key。示例工作流无需 Checkpoint、VAE 或 GPU 推理。

```text
[CLIProxyAPI Provider] ── provider ──► [Generate] ── image ──► [Save Image]
                                        │
                                      prompt
```

启动两个后端（CLIProxyAPI、ComfyUI），填写 Key 和提示词，Queue。若 Save Image 有输出，证明当前账号实际可访问生图服务；若只有 `request_report` 而无图片，请检查是否存在任务执行错误与日志。

### 参考图生成

```text
[Load Image] ── IMAGE ────────────────► [Generate.reference_1]
[CLIProxyAPI Provider] ── provider ──► [Generate.provider]
[Generate.image] ────────────────────► [Save Image]
```

- Generate 的参考图不是待修改底图，仅作为新图上下文。
- 前端默认显示三个入口，连接当前末尾入口会扩展下一个（至多 9 张）。
- `reference_1`、`reference_2`…从 1 开始**连续**连接。中间有空洞会报错。
- 每个参考图各自编码，不要求尺寸相同；不可把多个图片帧放进单个入口。
- CLIProxyAPI 下这条工作流改走 Responses，涉及两个模型名；**它不等同于 Edit 的 multipart 路径**。

## 4. Edit 参数和接线

Edit 与 Generate 共享 `provider`、`prompt`、`size`、`quality`、`background`、`output_format`、`moderation`、`n`、`timeout_sec`。

另外需要：

| 输入 | 用途 |
| --- | --- |
| `base_image（Image 1）` | **必需**。原始待编辑图片，通常接 Load Image 的 `IMAGE` |
| `references（Image 2 开始）` | **可选**。来自 `Edit Reference List` 的参考图集合，不能直接接普通 IMAGE |
| `mask` | **可选**。ComfyUI `MASK`，尺寸必须与基础图一致；部分代理/模型不支持 Mask |

```text
[Load Image：原图] ── IMAGE ────────────────► [Edit.base_image（Image 1）]
[Load Image：参考图] ── IMAGE ─► [Edit Reference List.image_2]
[Edit Reference List.references] ─────────► [Edit.references（Image 2 开始）]
[CLIProxyAPI Provider.provider] ──────────► [Edit.provider]
[Edit.image] ─────────────────────────────► [Save Image]
```

- **Image 1 永远是待编辑的基础图**。
- Image 2 是 `image_2`，Image 3 是 `image_3`，顺序严格保留到 HTTP 请求中。
- `Edit Reference List` 有 `image_2`～`image_9` 八个接口，缺少中间接口会报错。
- 单图编辑不需要 `Edit Reference List`，只连 Image 1。
- 参考图的宽高可以不同。
- Images Edit 使用 multipart；如果模型不支持指定选项会返回请求错误，避免反复提交可能产生费用的请求。
- Mask 并不强制上游精准局部编辑；实际效果取决于模型和代理。

### Generate 和 Edit 的区别

| 场景 | 推荐节点 | 为什么 |
| --- | --- | --- |
| 从零生成图片 | Generate，不连接参考图 | 直接走 Images 生图 |
| 用参考图作为风格/构图参考，生成一张新图 | Generate + `reference_1` 等 | 不指定固定待编辑底图 |
| 修改已有图中的特定内容 | Edit + `base_image` | 明确 Image 1 作为待修改对象 |
| 根据参考图修改已有图 | Edit + base + Reference List | 同时有待修改底图和参考素材 |
| 要做蒙版修改 | Edit + base + MASK | 仅在供应商支持时可用 |

## 5. 生成数量与额度

对于 CLIProxyAPI Provider，`n=4` 不是一次上游请求返回四张，而是**四次同步请求**，每次要求一张。即：

```text
ComfyUI Generate (n=4)
  ├─ POST /v1/images/generations  → Image A
  ├─ POST /v1/images/generations  → Image B
  ├─ POST /v1/images/generations  → Image C
  └─ POST /v1/images/generations  → Image D
                                   ↓
                            IMAGE batch (4)
```

如第 3 次请求失败，整个节点可能失败；已经提交的前两次请求**不会自动退款或自动取消**。不要在不知道上游是否已受理时简单无限重试。第一次测试 `n=1`，确认可用后再扩大数量。

通用 API Provider 的 `n` 行为依协议不同，见 [兼容 API 文档](compatibility-and-async.md)。

## 6. 旧 Provider 与迁移

### 原生 Codex OAuth Provider

- 自动查找 `CODEX_HOME/auth.json` 或当前用户 `~/.codex/auth.json`，**不通过 CLIProxyAPI**。
- 只支持 `auto`、`responses`、`images` 协议选择；对已有工作流继续保留。
- 直接请求 Codex 的非公开接口；凭据刷新后可能原子写回登录文件。
- 旧路径 Edit 最多接受 **1 张基础图 + 4 张参考图**，不支持 Mask；与通用 API / CLIProxyAPI Provider 的能力不可混为一谈。

### 通用 API Provider

用于其他 OpenAI 兼容服务，允许独立设置 `api_protocol`、自定义同步/异步端点、JSON 任务映射等。不应为了连接 CLIProxyAPI 盲目把所有通用异步开关开启。完整说明见 [兼容 API 与异步任务](compatibility-and-async.md)。

旧工作流中的 Provider 类名没有被更改，已有节点不会自动转成 CLIProxyAPI Provider。要迁移，手动把 Generate/Edit 的 `provider` 线改接新的 Provider 节点，并重新填写客户端 Key。

## 7. 图片输出与节点边界

插件通过图片响应解析和格式校验，将返回内容转成 ComfyUI `IMAGE`。它不加载 Checkpoint/LoRA/VAE/CLIP，不在本机渲染云端模型的推理过程，也不自动调用 Codex Agent。

图片输入与输出都有编码、尺寸和体积限制；高分辨率、多参考图可能增加请求体积、内存占用、延迟与上游失败概率。参数不被服务支持时应该调整模型或请求，而不是把一切问题归咎于 ROCm。

若已配置其他 ComfyUI 本地后处理节点（例如自定义放大器），是否需要 GPU/ROCm 取决于那些节点，**不由本插件决定**。

继续：[故障排查](troubleshooting.md) · [协议与实现](protocol-reference.md) · [安全与凭据](security.md)。
