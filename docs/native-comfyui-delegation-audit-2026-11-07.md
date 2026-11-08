# GPT Image Bridge × ComfyUI 功能职责逐项核对（2026-11-07）

> 定位：**本项目只做云端模型连接器与必要的协议边界，不重新造一个图像工作台。** 该文档依据官方 ComfyUI 源码及本仓库当前实现逐项对照，兼容窗口以仓库 CI 固定的 ComfyUI 0.44.0（SHA `63e5bf594339f676b4b15e072529873e3448409e`）为测试基线。官方源码的主线能力可能更新，非本机已测能力不会标记为 PASS。

官方代码证据：
- [原生 LoadImage / SaveImage / PreviewImage / ImageScale / ImageScaleBy / EmptyImage / 旧 ImageBatch](https://github.com/Comfy-Org/ComfyUI/blob/master/nodes.py)
- [PrimitiveStringMultiline / PrimitiveInt / PrimitiveFloat / PrimitiveBoolean](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_primitive.py)
- [StringConcatenate / StringFormat / StringReplace / StringTrim](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_string.py)
- [ResizeImageMaskNode / BatchImagesNode / BatchMasksNode](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_post_processing.py)
- [GetImageSize / SaveImageAdvanced](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_images.py)
- [MaskComposite / ImageCompositeMasked / MaskToImage / ImageToMask / grow/shrink](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_mask.py)
- [官方 OpenAIGPTImageNodeV2](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_api_nodes/nodes_openai.py)

## 1. 逐项职责清单

| 能力/入口 | ComfyUI 是否已有 | 处理决定 | 原因与证据 |
| --- | --- | --- | --- |
| 提示词文本输入、长文本编辑 | **有**：`PrimitiveStringMultiline` | **交给原生 Text (Multiline)**；桥接节点只保留 API 必需 `STRING prompt` 入参和快捷默认文本 | `prompt` 是远端必填请求字段，不是自定义文本编辑器；可直接连原生 STRING |
| 提示词模板、拼接、替换、截取 | **有**：`StringFormat`、`StringConcatenate`、`StringReplace`、`StringSubstring` | **不在 Bridge 新增专用 Prompt Builder** | 不复制字符串处理逻辑 |
| 整数、宽高计算与参数共享 | **有**：`PrimitiveInt` 等 | **通过标准 INT 连线**接 `custom_width`、`custom_height`，不另建 Bridge 分辨率计算器 | 宽高输入是 API 请求目标，不是本地图片处理 |
| 根据现有图像获取宽高 | **有**：`GetImageSize` | **交给官方节点**，输出 width/height 连到 Bridge 的 Custom 宽高 | 不复制图像元数据工具 |
| 宽高比、缩放、裁切、补边、统一尺寸 | **有**：`ResizeImageMaskNode`、`ImageScale`、`ImageScaleBy`、`ImageCropV2`、`ImagePadForOutpaint` | **交给 ComfyUI** | 没有为 GPT 模型再开发一套 Resize/Crop/Ratio 运算 |
| 云端图片请求的 `size`、尺寸值有效性 | **没有等价通用节点** | **保留协议转换和前置校验** | 图像预处理不是图像生成目标尺寸；必须符合上游支持范围，不能请求后才处理 |
| 单图读取、加载上传文件 | **有**：`LoadImage` | **交给原生加载器**，桥接只将 `IMAGE` 转远端可上传的 PNG bytes | 不复制本机文件浏览和图像加载 UI |
| 普通等尺寸多参考图组合 | **有**：`BatchImagesNode`（新）、旧 `ImageBatch`（已弃用） | **新增标准 `reference_batch: IMAGE` 输入**；优先连原生 Batch Images | 图片按帧展开并送远端；无需在默认工作流使用专用 Reference List |
| **不同尺寸**参考图独立上传 | 原生 Batch Images 会把其他图片**缩放成第一张大小** | **保留有序独立参考图入口**，专用 Edit Reference List 负责保留多张不同尺寸原图，同时兼容旧工作流 | 不可宣称原生 Batch 等价无损独立参考图。官方 `batch_images` 明确执行缩放 |
| 参考图枚举、编号、上传顺序 | 部分通过 ComfyUI 连线获得 | **Bridge 保留 HTTP multipart、角色和次序映射** | 服务端使用 Image 1 基础图 / Image 2–16 参考图，序列号是 API 语义 |
| 蒙版绘制、反转、扩展、合成 | **有**：原生 Mask/图像处理节点 | **交给 ComfyUI**，Bridge 仅接受 `MASK` 并按上游格式发送 | Mask 图形编辑不是 API 桥接职责；仍保留蒙版与基础图尺寸校验 |
| 透明通道导入与编辑 | `LoadImage` / 其他图像节点已有 | **原生图像流**，Bridge 负责正确编码、解码和保留 Alpha | 不能丢掉云端 RGBA 像素 |
| 图片数量/IMAGE batch 输出 | **有标准 IMAGE batch** | Bridge 输出原生 `IMAGE`；**不做私有图片类型** | `n` 是远端请求参数；CLIProxyAPI 会分次计费请求，Bridge 必须报告失败进度 |
| PNG 保存与预览 | **有**：`SaveImage`、`PreviewImage` | **默认交给原生节点** | Bridge 不再在入门图中重复一套 PNG Save |
| JPEG、WebP 导出、Alpha 转 JPEG 背景合成 | 本次查到的原生 `SaveImageAdvanced` 支持 PNG/EXR/AVIF，**未提供 JPEG/WebP** | **保留特殊导出节点**，命名明确为 `Export JPEG/WebP (optional)` | 不与原生 PNG 导出竞争；原有 PNG 模式留作旧工作流兼容 |
| PNG 的元数据与文件名 | **有**：`SaveImage` 包含原生元数据与文件名功能 | **交给原生 SaveImage** | 避免重复维护文件名与 PNG 元数据行为 |
| 本地模型、VAE、采样器、LoRA、ROCm | **ComfyUI 已有生态** | **本插件不碰** | 云端 API 的计算不能假装是本地采样 |
| 自定义模型名称/路由、服务商 Base URL、Key | ComfyUI 不提供针对本插件的多服务商 OpenAI-compatible Profiles | **保留 Provider Profile** | 保护本机密钥、不把连接配置写入 workflow |
| Images Generate / Images Edit / Responses / Chat 协议 | 官方 Partner Nodes 实现与 CLIProxyAPI 等代理不同 | **桥接层核心功能，必须保留** | 不复制官方付费代理认证，但负责用户自有第三方兼容 API |
| 参考图引导新图 vs 修改基础图 | 官方节点也有区分，但模型端语义不同 | **保留 Generate/Edit 的操作角色** | 避免把“参考引导生成”混成“修改已有底图” |
| 画质、透明背景、审核强度、数量、超时 | ComfyUI 有通用数值和 **原生 advanced 展开控制**，但无统一供应商 HTTP API 语义 | **保留远端参数；审核强度与超时标记为原生 advanced，不再自造展开控件** | 不把上游参数伪装成图像变换，也不与 ComfyUI 重复维护高级设置开关 |
| 请求失败、批次已计费的部分进度、实际尺寸/格式兑现 | **原生图像节点不承担第三方 HTTP 责任** | **保留诊断报告、验证与不可盲目重试的安全策略** | 属于连接器必须自己实现的逻辑 |
| Codex OAuth 老节点、旧 Provider | 新 Profile 已可取代常用入口 | **已隐藏/弃用；本轮仍保留注册** | 历史图加载时不能直接出现 Missing Node |

## 2. 本轮具体代码处理

1. **新增 `Generate.reference_batch` 与 `Edit.reference_batch`**：接标准 ComfyUI `IMAGE` batch，自动按帧、按原始顺序转换成云端参考图；Generate 最多 16，Edit 最多 15（加上 Image 1 基础图共 16）。不会对参考图自行做 Resize。
2. **输入互斥**：Generate 的 `reference_batch` 与 `reference_1–16` 不能同时使用；Edit 的 `reference_batch` 与历史 `Edit Reference List` 不能同时使用。请求发出前拒绝混用，避免重复上传或重复计费。
3. **保留有序单图输入**：复杂参考图大小和纵横比不同的场景，Generate 直接接独立 `reference_1–16`；Edit 可用保留的旧 Reference List。Edit References · Original Sizes 维持可搜索，不标记弃用（因为原生 Batch Images 会改变非等尺寸输入）；注册类 ID 不变，旧工作流继续兼容。
4. **简化前端默认占用**：Generate 只显示 1 个独立参考图 socket，连接后自动增长；不需要把 16 张的自定义聚合节点塞进每个工作流。
5. **不造新的文本/尺寸节点**：原生 Text、Int、GetImageSize、Resize/Batch/Mask/SaveImage 继续完全由 ComfyUI 提供。增加一份 [原生 Text + Int → GPT Image → 原生 Save Image](../example_workflows/Native-ComfyUI-Text-and-Size.json) 可导入工作流。
6. **保存责任显式区分**：`GPTImageBridgeSaveImage` 仍保留 PNG/JPEG/WebP 编码以兼容旧图，但展示名改为 `Export JPEG/WebP (optional)`，入门工作流默认使用 ComfyUI 原生 `SaveImage`。

## 3. 重要限制与不能冒充“去重完成”的点

- **云端尺寸 ≠ 对输入 IMAGE 进行 Resize**。给 Generate 输入一个 1536×1024 的图，也不代表云端会输出这个尺寸。只有设置 `size=Custom`、把标准 `Int` 输出接到 `custom_width/height` 后才会明确请求。代理有可能忽略，仍需看 `request_report.output.conformance`。
- **原生 Batch Images ≠ 保留不同大小图片**。根据官方 `batch_images` 实现，它会将不同形状的图片通过 `common_upscale(..., "center")` 变成首张大小。要避免裁切原参考图就使用独立单图接口（或旧 Edit Reference List）。
- 仍然需要原始 `prompt` 和 `size` 参数，因为它们是 HTTP 请求合同；**不是另做一个提示词编辑器/尺寸引擎**。旧工作流可继续把字符串写在 Bridge 节点里，但推荐用原生 Text/String Format。
- 官方某些非旧版节点基于较新的 `ComfyExtension`/Autogrow API，不能仅凭主线有源码就宣称所有 ComfyUI 版本都注册；CI 必须记录固定版本的测试结果。
- 完整浏览器 UI 点击/重载不由纯 Python HTTP 集成代替，标记为 `NOT_RUN` 直到实际测试；真实第三方付费请求本轮不执行。
- `ReferenceList` 原有功能是支持不同尺寸及保留旧图，因此应在正常节点搜索中可见，不仅保留运行兼容；JPEG/WebP 原生保存也未覆盖，不应该贸然删除。

## 4. 验收清单

- Python：标准 batch 顺序/索引、16/15 上限、互斥错误在请求前发生；历史单张参考图路径原样工作。
- JavaScript：单个起始独立参考图插口可扩展至 16；断开的空洞会按规则整理；历史 Reference List 迁移不改变已有连接次序。
- 实际 ComfyUI CPU + 模拟图像 API：原生 Text + 原生 ImageBatch → Bridge Generate → 原生 SaveImage；原生 Batch → Bridge Edit → 原生 SaveImage；历史路径、Key 隔离和 WebP/JPEG 特殊导出回归。
- 本机 ComfyUI 浏览器：原生 Text、Int 输入连线在画布上可编辑、可保存重载；Native Batch 自动伸缩；不同尺寸引用的例外场景可按文档处理；这些需要实际客户端验证。
