# 节点及工作流完整手册

本文面向实际使用 ComfyUI 画布的人。**Provider Profile 是推荐入口**；原生 OAuth Provider、通用 API Provider 继续保留，目的是兼容原有工作流和其他供应商。先按 [本机安装与登录](setup-cli-proxy-api.md) 完成环境准备。

## 1. 节点与职责（八个已注册，默认推荐 Profile）

| 画布节点名 | 实际类名 | 输入 | 输出/功能 |
| --- | --- | --- | --- |
| GPT Image Bridge · Provider Profile | `GPTImageBridgeProviderProfile` | 服务商名称、可选模型/参考图模式 | `GPT_IMAGE_PROVIDER`；推荐，不含 Key/Base URL |
| GPT Image Bridge · CLIProxyAPI Provider | `GPTImageBridgeCLIProxyAPIProvider` | 客户端 Key、代理地址、图片模型、Responses 主模型 | `GPT_IMAGE_PROVIDER`；推荐 |
| GPT Image Bridge · API Provider | `GPTImageBridgeAPIProvider` | 通用 API Key、Base URL、model、protocol、自定义端点/异步参数 | `GPT_IMAGE_PROVIDER`；第三方兼容 API |
| GPT Image Bridge · Codex OAuth Provider | `GPTImageBridgeOAuthProvider` | 图片 model、protocol | `GPT_IMAGE_PROVIDER`；旧的内置 Codex 登录方案 |
| GPT Image Bridge · Generate | `GPTImageBridgeGenerate` | Provider、提示词、生成参数、至多 16 张独立参考图 | `IMAGE`、`revised_prompt`、`request_report` |
| GPT Image Bridge · Edit | `GPTImageBridgeEdit` | Provider、基础图、提示词、生成参数、参考图列表、可选 MASK | 同上 |
| GPT Image Bridge · Edit Reference List (Image 2–16)（旧版/特殊尺寸） | `GPTImageBridgeReferenceList` | `image_2`…`image_16` | `GPT_IMAGE_REFERENCES`，只用于 Edit |
| GPT Image Bridge · Export JPEG/WebP (optional) | `GPTImageBridgeSaveImage` | `IMAGE`、文件格式、质量、文件名前缀、JPEG 背景色 | 保存 PNG/JPEG/WebP 到 ComfyUI `output/`，并继续输出原 IMAGE batch |

旧 API / CLIProxyAPI / OAuth 三个 Provider，以及旧 Edit Reference List，已标记 DEPRECATED / DEV_ONLY：默认新建菜单隐藏，但旧工作流可继续运行。配置请先参阅[服务商配置](provider-profiles.md)。

**优先使用 ComfyUI 自带的 Text、Int、Get Image Size、Batch Images、Resize Image/Mask、Mask、Save Image。** Bridge 只负责模型请求、图片转换、参数验证与诊断。详见[逐项职责审计](native-comfyui-delegation-audit-2026-11-07.md)。

所有节点都在 `GPT Image Bridge` 分类下。日常 PNG 保存请使用 ComfyUI 原生 **Save Image**；只有确实需要 JPEG/WebP 编码或自选 JPEG 底色时，才用本插件 **Export JPEG/WebP (optional)**。旧 PNG 导出模式仍可运行。

### 主要输出

- `image`：真实 `IMAGE` 张量，可连 Save Image、放大、裁剪等后处理。实际转换为 ComfyUI 图像 batch；当 `n>1` 时，输出多张。
- `revised_prompt`：上游若返回修订后的提示词则提供文本，否则为空串；**不要假定一定有值**。
- `request_report`：字符串形式的脱敏 JSON，包括协议选择依据、请求次数、端点、响应状态与耗时等；`output.conformance` 会将请求尺寸/格式/透明背景与解码后的实际图片逐项比对，发现上游未兑现时给出 warning。被协议忽略或无法比较的字段不会被误报为 pass。它不是图片，也不是上游原始响应；见 [诊断与安全](security.md)。

## 2. CLIProxyAPI Provider 配置

| 控件 | 默认 | 用途 |
| --- | --- | --- |
| `api_key` | 空 | CLIProxyAPI 客户端访问 Key，非 Codex OAuth Token |
| `base_url` | `http://127.0.0.1:8317/v1` | ComfyUI 能访问的代理地址 |
| `image_model` | `gpt-image-2.6-flare` | 图片型号；可选 `gpt-image-2.6-sunburst` 或实际授权的旧型号 |
| `responses_model` | 空 | 仅在 `reference_mode=responses` 时需要文本主模型 |
| `reference_mode` | `images_edit` | 参考图默认经 Images Edit 生成新图，或手动选择 `responses` |
| `image_complexity` | `auto` | 保留 `low/medium/high` 选项用于兼容；CLIProxyAPI v8.0.57 默认 Images 路径会丢弃该字段，当前请保持 `auto` |

新增 `reference_mode` 和 `image_complexity` 是可选字段。旧 Provider 的四个必需输入保持原名，旧的 Generate/Edit 节点 ID 均不变。通用 API Provider / 旧 Codex OAuth Provider 的原有自动选路没有改动。

### 三条操作路径

| 操作 | 路径 | 区别 |
| --- | --- | --- |
| Generate，无参考图 | `/v1/images/generations` | 真正从零生图，无文本主模型 |
| Generate，有参考图、默认 `images_edit` | `/v1/images/edits` | 首张参考图作为输入 Image 1，以指令要求**生成新图**，其余参考图按顺序附加 |
| Generate，有参考图、可选 `responses` | `/v1/responses` | 文本主模型调用 `image_generation` 工具，需要填写有效 `responses_model` |
| Edit | `/v1/images/edits` | Image 1 是待修改基础图，非单纯视觉参考 |

**参考图引导的 Images Edit 并非真正无参考图的 Generations。** 模型可能保留原有构图；此差异不会被隐藏。初次验收建议默认 Images 路线，`n=1`，`image_complexity=auto`。

OpenAI 官方 2026-11-04 发布了 Flare / Sunburst；CLIProxyAPI v8.0.57 代码识别这两个 ID。本仓库的 Main 0.7.0 报告已在一套真实账户上验证两者生成；其他订阅账号仍需自行实测。详见[模型兼容说明](model-support.md)。

## 3. Generate 参数与画布分层

**画布界面简化，功能和参数没有删减。** 新增的前端扩展仅改变显示状态，不修改 Generate / Edit 的 `INPUT_TYPES`、参数名、执行值或原有请求校验。日常使用时，提示词、`size`、`quality`、背景、输出格式和 `n` 直接可见。

- `size=Custom` 时，显示宽度和高度；选择其他尺寸时收起。**宽和高已经决定宽高比，不需要独立比例参数**。宽、高历史值会保留，切回 Custom 可继续使用。
- `size` 来自动态输入连线时，宽高不会因为显示值不是 Custom 而被隐藏。
- `moderation`、`timeout_sec` 默认收起，在节点上打开 **「显示高级参数」** 即可编辑；高级参数处于非默认值或已连接时，不会被无声隐藏。
- 这个展开开关是**纯前端控件**：展开状态存放在工作流节点的 `properties` 中，但开关不会成为新的 API 请求参数，也不会改变旧工作流按位置保存的原有 widget 列表。
- Provider Profile 只有在显式选择 `responses`、填写过主模型覆盖值，或主模型字段有输入连线时，才显示 `responses_model`。留空仍使用本机 Profile 的默认值。
- Generate 的参考图插口仍是原来的自动伸缩，Edit 的基础图/参考图/Mask 接口完全保留。某些旧版/定制 ComfyUI 前端可能采用不同的布局机制，请按[浏览器端验收](testing.md)核实。

### Generate 全部请求参数（含隐藏在高级设置内的参数）

| 输入 | 类型/范围 | 用途与提醒 |
| --- | --- | --- |
| `provider` | `GPT_IMAGE_PROVIDER` | 从 Provider Profile（推荐）或兼容旧 Provider 连接 |
| `prompt` | 多行文本 | 图片生成指令；不能为空 |
| `size` | `auto`、基础尺寸、2K/4K 预设、`Custom` | 按所选模型能力请求，旧型号可能拒绝 |
| `custom_width`、`custom_height` | 可选整数，默认 1024×1024 | 仅 `size=Custom` 时有效：480–3840、16 的倍数、比例 ≤3:1、像素 655,360–8,294,400 |
| `quality` | `auto`、`low`、`medium`、`high`、`xhigh`、`max` | 2.5/2.6 可用更高质量档位，旧型号可能拒绝 |
| `background` | `auto`、`opaque`、`transparent` | 透明图建议配 PNG/WebP；不保证上游兑现 |
| `output_format` | `png`、`jpeg`、`webp` | 这是上游 API 响应编码请求，不是本地文件保存格式；ComfyUI 原生 Save Image 仍保存 PNG，本插件的特殊 JPEG/WebP 导出节点 可重新编码为 PNG/JPEG/WebP |
| `moderation` | `auto`、`low` | 服务端可能忽略或拒绝 |
| `n` | 整数 1–8 | 需要多少张输出。**CLIProxyAPI 专用模式每张对应一次独立上游请求** |
| `timeout_sec` | 整数 30–3600 | 超过后本地等待结束，未必代表上游操作已取消 |
| `reference_batch` | 可选 `IMAGE` batch | 普通多图使用原生 Batch Images，输出批次按帧发送。与编号参考图互斥；原生 Batch 可能统一尺寸 |
| `reference_1`…`reference_16` | 可选 `IMAGE` | 按顺序连接，不允许中间空洞；每个入口单张，非 IMAGE batch |

首次接入建议采用全部 `auto`、`png`、`n=1`、`timeout_sec=300`。只有验证了最简单请求后，才调高级选项。

### 文生图连线（原生 ComfyUI Text/Int 优先）

推荐先拖入[原生 Text、Int 与 Bridge 组合工作流](../example_workflows/Native-ComfyUI-Text-and-Size.json)。原生 `Text (Multiline)` 连接 Generate 的 `prompt`，两个原生 `Int` 连接 `custom_width` / `custom_height`，并设 `size=Custom`。最后接原生 Save Image。无需再做专用 Prompt 或比例计算器。

下方为保留的极简兼容示例：

可从[无密钥的 CLIProxyAPI 文生图示例](../example_workflows/CLIProxyAPI-Text-to-Image.json)开始，直接拖入 ComfyUI 画布后选用本机 Provider Profile（Key 在本机配置中）。示例工作流无需 Checkpoint、VAE 或 GPU 推理。

```text
[Provider Profile] ───── provider ──► [Generate] ── image ──► [Save Image]
                                        │
                                      prompt
```

配置好 Provider Profile 后启动 ComfyUI（本机 Codex 路径还需启动 CLIProxyAPI），填写提示词并 Queue。若 Save Image 有输出，证明当前账号实际可访问生图服务；若只有 `request_report` 而无图片，请检查是否存在任务执行错误与日志。

### 参考图生成（优先使用原生 Batch Images）

```text
[Load Image A] ── IMAGE ──────► [Batch Images.image0]
[Load Image B] ── IMAGE ──────► [Batch Images.image1]
[Batch Images] ── IMAGE ─────► [Generate.reference_batch]
[Provider Profile] ── provider ► [Generate.provider]
[Generate.image] ────────────► [Save Image]
```

**不同尺寸的参考图不建议直接 Batch**：官方 Batch Images 会把后面的图片统一成第一张的尺寸。要保留各张尺寸和比例，可以改用 `Generate.reference_1`、`reference_2` 等独立输入。

- Generate 的参考图不是待修改底图，仅作为新图上下文。
- 前端默认显示一个独立参考图入口，连接最后一个后自动扩展（至多 16 张）；普通等尺寸参考图推荐原生 Batch Images 接到 `reference_batch`。
- `reference_1`、`reference_2`…从 1 开始**连续**连接。中间有空洞会报错。
- 每个参考图各自编码，不要求尺寸相同；不可把多个图片帧放进单个入口。
- CLIProxyAPI 下默认走 **Images Edit multipart**：第一张参考图作为输入 Image 1，后续按 Image 2、3……有序追加，提示词明确要求“生成新图”。这与完全从零的 Generations 不完全等价。选择 `reference_mode=responses` 才会调用文本主模型 + 图片工具；两种模式要分别验收。

## 4. Edit 参数和接线

Edit 与 Generate 共享 `provider`、`prompt`、`size`、`quality`、`background`、`output_format`、`moderation`、`n`、`timeout_sec`。

另外需要：

| 输入 | 用途 |
| --- | --- |
| `base_image（Image 1）` | **必需**。原始待编辑图片，通常接 Load Image 的 `IMAGE` |
| `reference_batch` | **可选，推荐**。标准 `IMAGE` batch，由 ComfyUI 原生 Batch Images 连接，最多 15 张；与旧列表互斥 |
| `references（Image 2 开始）` | **可选，旧版特殊入口**。来自 `Edit Reference List` 的原始尺寸参考图集合 |
| `mask` | **可选**。ComfyUI `MASK`，尺寸必须与基础图一致；部分代理/模型不支持 Mask |
| `custom_width` / `custom_height` | **可选**。`size=Custom` 时指定输出宽高，需为 16 的倍数并满足官方像素/比例限制 |

```text
[Load Image：原图] ── IMAGE ──────────► [Edit.base_image（Image 1）]
[Load Image：参考图 A] ── IMAGE ───► [Batch Images.image0]
[Load Image：参考图 B] ── IMAGE ───► [Batch Images.image1]
[Batch Images] ── IMAGE ────────────► [Edit.reference_batch]
[Provider Profile.provider] ────────► [Edit.provider]
[Edit.image] ────────────────────────► [Save Image]
```

- **Image 1 永远是待编辑的基础图**。
- Image 2 是 `image_2`，Image 3 是 `image_3`，顺序严格保留到 HTTP 请求中。
- 普通多参考图优先使用官方 Batch Images；`Edit Reference List` 是保留的旧节点，用于不同宽高图片需要保持原始尺寸的场景，其 `image_2`～`image_16` 十五个接口不能有空洞。
- 单图编辑不需要任何参考图聚合节点，只连 Image 1。
- 批量编辑参考图连接 `reference_batch`，**不要同时连接旧的 `references（Image 2 开始）`**；该节点会在发出远端请求前拒绝。
- 参考图的宽高可以不同。
- Images Edit 使用 multipart；如果模型不支持指定选项会返回请求错误，避免反复提交可能产生费用的请求。
- Mask 并不强制上游精准局部编辑；实际效果取决于模型和代理。

### Generate 和 Edit 的区别

| 场景 | 推荐节点 | 为什么 |
| --- | --- | --- |
| 从零生成图片 | Generate，不连接参考图 | 直接走 Images 生图 |
| 用参考图作为风格/构图参考，生成一张新图 | Generate + `reference_1` 等 | 不指定固定待编辑底图 |
| 修改已有图中的特定内容 | Edit + `base_image` | 明确 Image 1 作为待修改对象 |
| 根据参考图修改已有图 | Edit + base + 原生 Batch Images / 旧 Reference List | 同时有待修改底图和参考素材 |
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

本插件保存节点的详细编码行为见[本地图片导出](local-image-export.md)。

请求参数与真实响应的核验规则见[输出参数兑现核验](output-conformance.md)。

继续：[故障排查](troubleshooting.md) · [协议与实现](protocol-reference.md) · [安全与凭据](security.md)。
