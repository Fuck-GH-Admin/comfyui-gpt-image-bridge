# ComfyUI 官方云端生图节点对照与本项目自由度评估

核对日期：2026-11-06。本次阅读的是 [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) 的真实源码，而不是按宣传图推断节点能力。

主要参考：

- [官方 OpenAI GPT Image 节点](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_api_nodes/nodes_openai.py)：`OpenAIGPTImageNodeV2`、`_gpt_image_26_model_inputs`；
- [官方 Gemini Nano Banana 2.1 节点](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_api_nodes/nodes_gemini.py)：`GeminiNanoBanana2V2`；
- [官方 Ideogram 节点](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_api_nodes/nodes_ideogram.py)：`IdeogramV3`、`IdeogramV4`；
- [OpenAI GPT Image 2.6 官方型号与接口](model-support.md)。

## 1. 一眼看懂：官方有哪些自由度？

| 项目 | 官方 OpenAI GPT Image 2.6 | 本 fork（PR #3 + 本轮完善） | 评估 |
| --- | --- | --- | --- |
| 模型选择 | 2.6 Flare、Sunburst、2.5、2、1.5；根据型号显示不同控件 | `image_model` 是可自由填写的字符串，默认 2.6 Flare | 本 fork 更适合 CLIProxyAPI 别名或新模型，缺少动态提示 |
| 生成与编辑 | 一个节点可根据有无图片选择 Images Generate/Edit | 独立 Generate、Edit，另有 Provider | 显式职责更清晰，适合 ComfyUI 复杂工作流 |
| 自定义大小 | 2K/4K 预设 + 自定义宽高和本地尺寸检查 | 同样加入预设及 `Custom` 宽高；非法尺寸在发请求前拒绝 | 已补齐核心差距 |
| 质量档位 | 2.6 和 2.5 包含 `low/medium/high/xhigh/max` | `auto/low/medium/high/xhigh/max` | 已补齐，旧型号可能拒绝高档位 |
| 规划复杂度 | 2.6 的 `low/medium/high` | Provider 中 `auto/low/medium/high` | `auto` 不发送字段，避免破坏旧服务 |
| 参考图 | OpenAI 节点最多 16 张，可输入多图编辑 | Generate 最多 16 张参考图；Edit 最多基础图 1 张 + 15 张参考图 | 已补齐，沿用连续编号/单图插口 |
| 局部编辑 | 可选 Mask，需要正确的输入图数 | Edit 具有 Mask，参考图生成另设 Images Edit 模式 | 基本具备 |
| 输出数量 | `n` 1–8 | `n` 1–8；CLIProxyAPI 每张单独请求 | 结果相似，远端使用量/延迟不等同 |
| 模型自动判断参数有效性 | 动态控件根据官方型号限制可选参数 | 用户自由填写，远端不兼容参数保留错误而不隐藏 | 自由度高，但必须读文档 |
| Seed | 在官方 OpenAI 节点中标注“not implemented yet in backend” | **不提供虚假的 Seed 控件** | 刻意不照搬 |
| 订阅与计费 | ComfyUI Partner Nodes 的认证与价格显示 | CLIProxyAPI 客户端 Key、Codex OAuth 由独立代理管理 | 两个系统的成本与权限不能混同 |
| SVG/GIF | OpenAI 2.6 API 可以提供，需单独媒体/文件通道 | 目前只输出 ComfyUI 位图 IMAGE | **未实现**，不能声称覆盖全部 2.6 能力 |

**结论：** 对日常云端生图、图生图、参考图和编辑，本 fork 在本轮补全后有接近官方 OpenAI 节点的关键控制面；但它不是所有媒体类型全能节点，也不应硬做官方 Partner Nodes 的私有认证、成本徽章或模型列表。

## 2. 与其他官方云端生图节点的设计差异

### Gemini Nano Banana

官方 Gemini / Nano Banana 2.1 节点支持模型分级、1K/2K/4K、横纵比、思考强度、文本+图像联合输出等。较新的版本还会按模型自动展示不同的 `thinking_level`，历史版本通常最多 14 张参考图。

这说明一个好的云端节点应该**按模型能力分组**，而不是把任何供应商的高级参数全部混在一个固定输入区。我们的 GPT Image 接口没有 Gemini 的 `temperature`、`top_p`、思考图等同类控制，因此不应直接把它们复制进来。

### Ideogram

官方 Ideogram 节点有分辨率/宽高比切换、角色图/角色蒙版、渲染速度、风格和数量等能力。它体现了**语义不同的视觉任务需要独立输入**。我们保留 Generate/ Edit 两类节点、独立首图角色和参考图顺序，符合这个原则。

### 官方 OpenAI 动态参数

官方通过 `IO.DynamicCombo` 根据型号动态切换合法 `quality`、背景与尺寸：

- 2.6：五级渲染质量与独立复杂度。
- 2.5：五级渲染质量，但没有 2.6 的规划复杂度。
- 2：通常只允许 `low/medium/high`，且背景透明度有差异。
- 1.5：尺寸限制更严格。

我们**故意不加固定的型号白名单**：CLIProxyAPI 允许版本别名、内部模型名称和未来模型；在 ComfyUI 里完全封闭列表反而阻止新功能。代价是：不支持的参数由代理或上游拒绝。初次使用建议 `size=auto`、`quality=auto`、`image_complexity=auto`；进阶用户才选择自定义尺寸和更高质量。

## 3. 参数处理边界（源码实际实现）

### Custom 尺寸

Generate 与 Edit 节点将 `size=Custom` 转成 `宽x高` 字符串，满足：

- 宽、高各 480–3840，必须为 16 的倍数。
- 宽高比最大 3:1。
- 像素总数在 655,360–8,294,400 范围内。

这些限制是参考官方 OpenAI 节点的客户端检查，服务端模型仍可能拒绝某些组合。未选择 Custom 时，`custom_width`/`custom_height` 完全忽略，不影响旧工作流。

### 图像顺序与安全

- Generate 的 `reference_1`～`reference_16` 是独立单张 IMAGE 输入口，前端自动扩展。
- Edit 的基础图仍叫 `base_image（Image 1）`，其余 `image_2`～`image_16` 由 Edit Reference List 组织。
- 参考图 Generate 选默认 `images_edit` 时，首张参考图被作为 Images Edit 的 Image 1 输入。它是**参考引导式新图**，而不等于无参考图的 Generate。
- `Responses` 是有意选择的单独模式；只有该模式需要有效文本主模型。
- 参数无效、参考图存在空洞或输入为多帧 batch 时，在发送远端 POST 前拒绝，避免浪费账号额度。
- 本地工作流保存的客户端 Key 仍可能是明文，分享前必须清除（[安全说明](security.md)）。

## 4. 暂时不纳入的功能及原因

| 功能 | 为什么没有直接做 |
| --- | --- |
| Seed | 官方 OpenAI 节点明确提示其后端暂未实现；不做虚假的可重复性承诺 |
| ComfyUI 平台价格徽章 | 我们走独立 CLIProxyAPI + Codex 账户，额度、实际价格和账号权限不一定等同官方 API |
| 自动读取/展示 Codex 账号额度 | CLIProxyAPI 不保证提供统一、稳定的额度协议；拒绝猜测 |
| 所有第三方模型（Gemini、Ideogram 等）控件 | 本插件目标是 GPT Image Bridge，不应伪造其他供应商支持 |
| 动态型号白名单 | 会阻碍用户使用新模型名或代理别名。先保留自由文本，后续可考虑建议列表 + 自定义 |
| 自动在 Images 与 Responses 之间失败回退 | 远端请求可能已执行，重发可能重复耗额度；必须由用户明确选择 |
| SVG、GIF 和 2.6 markup-guided 编辑 | 需要独立文件/动画输出和真实协议验证，不能仅将媒体伪装成 `IMAGE` |

## 5. 后续可独立推进

目前的高优先级是本地真实 Codex 账户验证 **2.6 Flare / Sunburst + Images Edit 参考图**，而不是把数十个未验证的参数全部塞进节点。

如果真实账号可用，后续再考虑引入**支持自定义内容且不过度约束的模型建议列表**、独立 SVG/GIF 文件输出节点以及可复用的参考图序列节点。任何新增功能都要附带对应真实 ComfyUI 工作流和独立错误边界，而不是一次重写整套 ComfyUI 插件。
