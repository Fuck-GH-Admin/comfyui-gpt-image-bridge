# GPT Image 模型与 CLIProxyAPI 兼容性

更新时间：2026-11-06。本文对 **OpenAI 正式公告**、**CLIProxyAPI v8.0.57 的源代码实现**以及**本仓库测试证据**分层说明，避免把任意代理别名写成官方模型。

**本机更新验收：** [Main 0.7.0 报告](main-acceptance-2026-11-06.md)已对两个 2.6 型号完成真实生成与默认参考图请求；尺寸、格式和透明度存在未达标项，Responses 路径仍被网络阻塞。本文早先的“待验证”状态须结合该报告阅读。

## 1. OpenAI 官方确认的最新图片模型

OpenAI 于 **2026-11-04** 正式发布 **GPT Image 2.6** 两个变体：

| 正式 ID | 官方用途 | ComfyUI 建议 |
| --- | --- | --- |
| `gpt-image-2.6-flare` | 更快的日常生成、迭代 | **新 Provider 默认** |
| `gpt-image-2.6-sunburst` | 复杂构图、更高细节及更精确编辑 | 需要精细控制时改填此模型 |

官方文档（发布当天/当前版本）：

- [OpenAI API Changelog：2026-11-04](https://developers.openai.com/api/docs/changelog)
- [GPT Image 2.6 Flare 型号页](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare)
- [GPT Image 2.6 Sunburst 型号页](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst)
- [官方图片生成与编辑指南](https://developers.openai.com/api/docs/guides/image-generation)
- [官方 Images Generate API](https://developers.openai.com/api/reference/resources/images/methods/generate)
- [官方 Images Edit API](https://developers.openai.com/api/reference/resources/images/methods/edit)

**`gpt-image-2.6` 不应被当成 OpenAI 官方承诺的第三个独立型号。** CLIProxyAPI 代码确实识别它，但官方正式产品目录明确列出 `-flare` 和 `-sunburst`。因此本插件默认后者中的 Flare，并允许自由输入任何当前实际可用的图片模型名称。

## 2. 旧型号继续受支持，不限制字符串

Provider 的 `image_model` 仍是普通字符串输入。不会通过本插件硬编码白名单限制代理或用户账户的模型别名。

OpenAI 的 Images API 文档也列出 `gpt-image-2`、`gpt-image-2-2026-04-21`、`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst` 及它们的部分快照等旧型号。

此前 PR #2 的历史报告只验证过 `gpt-image-2`。后续 [Main 0.7.0 实机报告](main-acceptance-2026-11-06.md)已在本次 CLIProxyAPI 8.0.57 + Codex OAuth 环境中分别验证 Flare、Sunburst 真实生成，并验证默认 Images Edit 参考图生成。**这证明当前测试账户和链路可用，不代表其他账户、代理版本或区域都已开放。** 若其他环境不支持，可改回已验证的 `gpt-image-2`，并重新记录结果。

特别注意：OpenAI 正式 API 的模型目录，与 Codex **订阅型授权**、CLIProxyAPI 的实际 OAuth 路由不是一个保证；官方支持不代表订阅永远包含全部模型。

## 3. CLIProxyAPI v8.0.57 的源码证据

已核对版本标签 `v8.0.57`，而不只核对浮动的 `main`。

关键文件：[Codex Images 执行器](https://github.com/router-for-me/CLIProxyAPI/blob/v8.0.57/internal/runtime/executor/codex_openai_images.go)。

该源码的图片模型识别中明确包含：

- `gpt-image-2`
- `gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`
- `gpt-image-2.6-flare`、`gpt-image-2.6-sunburst`
- 代理额外识别的 `gpt-image-2.5`、`gpt-image-2.6` 等路由名称（**不能据此推断是 OpenAI 正式 ID**）

CLIProxyAPI 会将 `/v1/images/generations` 或 `/v1/images/edits` 映射到它认为合适的 Codex 代理/图片路由，包括图片模型直接接口和部分内部 Responses 兼容实现。因此，**ComfyUI 使用 Images API 并不代表 CLIProxyAPI 的每个后端版本都执行同样的上游 HTTP 路径**。

实机排障时先确定 CLIProxyAPI 的实际版本和 `/v1/models` 可见的模型名称；可见不等于已验收成功。

## 4. 2.6 新参数：`complexity`

OpenAI 文档将 `complexity` 描述为图片生成前的规划计算强度，独立于 `quality` 渲染质量。支持 `low`、`medium`、`high`。

此 fork 在 CLIProxyAPI Provider 新增：

| `image_complexity` | 请求行为 |
| --- | --- |
| `auto`（默认） | **不发送** `complexity`，由服务端/模型采用默认值 |
| `low` | 请求包含 `complexity=low` |
| `medium` | 请求包含 `complexity=medium` |
| `high` | 请求包含 `complexity=high` |

在 Images Generate 中为 JSON 字段，在 Images Edit 中为 multipart 字段；选择可选 Responses 模式时进入图片工具参数。当前源码对这三个合法值做了校验。

**不要在老型号上盲目开启**：不同模型/代理版本可能拒绝未知字段。2.6 官方指南称未设置时其默认规划复杂度为 `high`；这里 UI 的 `auto` 表示“不指定”，并不保证低延迟或低额度消耗。Main 0.7.0 实机工作流使用过 low/medium/high，但没有进行隔离变量的 A/B 对照，因此不能据此量化复杂度对效果、延迟或费用的影响。

## 5. 从官方 ComfyUI 节点补齐的高级控制

本分支的 Generate / Edit 节点补充了 OpenAI GPT Image 官方 ComfyUI Partner Node 已有的高价值控制面：

- `size` 提供常规三种尺寸、2K/4K 预设和 `Custom`。Custom 须设置宽高各 480–3840、均为 16 的倍数、长宽比不超过 3:1、总像素在 655,360–8,294,400。未选 Custom 时两个可选宽高输入被忽略。
- `quality` 扩大为 `auto/low/medium/high/xhigh/max`；其中 `xhigh`、`max` 面向官方支持它们的 2.5/2.6 型号，较旧型号可能拒绝。
- Generate 最多 16 张连续编号参考图；Edit 最多一张基础图与 15 张独立参考图，仍保留输入次序和 Image 1 身份。
- 旧工作流无需改动尺寸或质量字段；当前有 `image_model` 自由填写框，未来代理模型别名无需改白名单。

官方 OpenAI 节点本身明确注明 Seed 尚未在后端实现，我们没有制造一个不起作用的 Seed 控件。不同型号接受的参数仍要以实际代理/服务端为准。完整源码对比见[官方节点自由度分析](official-node-comparison.md)。

## 6. 当前 ComfyUI 节点明确没有覆盖的 2.6 功能

OpenAI 官方还介绍了 2.6 的 SVG 输出、GIF 动画和 markup-guided editing。但是本插件目前：

- `output_format` 仅支持 `png`、`jpeg`、`webp`。
- ComfyUI 的 `IMAGE` 输出是图片张量，不能未经处理就把 SVG 源文件或完整 GIF 动画当成同一张 `IMAGE` 返回。
- 未暴露 GIF 帧数/帧间隔、markup-guided edit 相关输入语法，也没有实测它们在 CLIProxyAPI 的订阅路由下的支持情况。
- 新增的 `complexity` 目前有 Mock 请求形态测试，真实 2.6 的上游结果仍需本人账号测试。

这些限制不是 OpenAI 2.6 不支持，而是**本插件还没有实现或验证完整的新媒体输出通道**。不要把「可选择 2.6 生图模型」写成「2.6 全部能力都已支持」。

## 7. 参考图模式与型号的关系

新的默认参考图模式 `images_edit` 并不需要调用 `gpt-6.1-sol` 等文本模型：当 Generate 接入参考图时，插件通过 Images Edit 发送参考图，强调“把图作为视觉参考，生成一张新图”。这是**参考图引导的编辑式生成**，不是 OpenAI 定义的从零 Generations 请求，也不保证严格不保留旧图构图。

可以将 `reference_mode` 改成 `responses` 以让一个支持图片工具的文本模型协调生成。此时需要额外设置 `responses_model`；你此前报告的默认 `gpt-5.4-mini` 在当地代理中返回 `model_not_found`，说明不能再强制把它设成所有用户的有效默认值。

模型选择建议：

1. 日常云端纯文生成：`gpt-image-2.6-flare`（若账号有权限），`reference_mode=images_edit` 不影响无参考图场景。
2. 精细图像编辑和复杂参考任务：`gpt-image-2.6-sunburst`（若账号有权限），参考图默认 Images Edit。
3. 真正需要文本/Agent 工具协调的流程：手动选 Responses，再选择**本机代理实际支持**的 `responses_model`，并单独验证该模型能调用 `image_generation`。
4. 遇到上游模型不可用：明确记下状态和模型，必要时退回你已实测的 `gpt-image-2`，不要无限重复提交。

## 8. 不同证据的边界

| 结论 | 证据状态 |
| --- | --- |
| 2.6 Flare / Sunburst 是 OpenAI 正式模型 | 官方更新日志、官方模型文档 |
| CLIProxyAPI v8.0.57 识别两个型号及 Images 端点 | 指定发布标签源码 |
| ComfyUI 可通过插件传递 2.6 型号及 complexity | 本 fork 请求形态单元测试（Mock HTTP） |
| 参考图默认 Images Edit，Responses 可手动选择 | 本 fork 源码、单元和真实 ComfyUI + 假代理集成测试 |
| 2.6 Flare / Sunburst 在本次真实账户的生图与默认参考图链路 | **已实机通过**；自定义尺寸/格式、透明输出仍未达标，Responses 另受 DNS 阻塞；其他账户需自行验证 |
| SVG、GIF、markup-guided 编辑在当前 ComfyUI 节点可用 | **未实现/未验证** |
