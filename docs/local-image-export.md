# 本地图片导出：PNG、JPEG 与 WebP

本插件新增的 `GPT Image Bridge · Save Image` 是一个本地 ComfyUI 输出节点。它接收 `IMAGE` batch，将像素数据编码为用户选择的文件格式，并写入 ComfyUI 配置的 output directory。

它解决的是**本地文件编码**问题，不会改变 GPT Image 上游实际生成的分辨率或响应编码。

## 1. 为什么需要独立保存节点

Generate/Edit 节点返回的是 ComfyUI 的 `IMAGE` Tensor，典型形状为 `[batch, height, width, channels]`。解码成 Tensor 后，像素仍在，但上游原始 PNG/JPEG/WebP 文件字节与编码参数已经不再附着于这个 Tensor。

因此有两个不同的格式控制：

- Generate/Edit 的 `output_format`：请求上游 API 尽量按指定格式返回图片。
- 本节点的 `file_format`：将收到的 IMAGE Tensor 在本机重新编码成 PNG、JPEG 或 WebP。

即使上游忽略 JPEG/WebP 请求并返回 PNG，本地保存节点仍可从解码后的像素编码 JPEG/WebP。它不会恢复或保留上游原始文件字节，也不能证明上游原生输出格式请求已生效。

## 2. 节点输入

| 输入 | 默认值 | 说明 |
| --- | --- | --- |
| `images` | 必需 | ComfyUI IMAGE batch，支持 RGB 三通道和 RGBA 四通道 |
| `file_format` | `png` | `png`、`jpeg` 或 `webp` |
| `filename_prefix` | `GPTImageBridge` | 文件名前缀；使用 ComfyUI 的输出目录和命名/子目录处理 |
| `quality` | 90 | JPEG/WebP 编码质量，范围 1–100；PNG 忽略 |
| `png_compress_level` | 4 | PNG 压缩级别，范围 0–9；越高通常文件越小、编码越慢 |
| `webp_lossless` | false | WebP 是否无损编码；无损和有损 WebP 均可保存 Alpha |
| `jpeg_background` | `#FFFFFF` | JPEG 遇到 RGBA 输入时的背景合成色，必须为 `#RRGGBB` |

节点输出原始 `IMAGE` batch，便于继续连接后处理节点；同时作为 ComfyUI Output Node 保存文件并在队列历史中报告文件名。

## 3. 格式和 Alpha 行为

### PNG

- RGB 输入保存为 RGB PNG。
- RGBA 输入保存为 RGBA PNG。
- 保留 Alpha 样本，不会为了保存而强制转成 RGB。
- `png_compress_level` 只影响 PNG 编码压缩，不改变像素值。

### WebP

- RGB 输入保存为 RGB WebP。
- RGBA 输入保存为 RGBA WebP。
- `webp_lossless=false` 时使用有损 WebP；Alpha 通道仍然保留，但 RGB 像素可能因有损压缩发生变化。
- `webp_lossless=true` 时使用无损 WebP。
- 如果当前 ComfyUI Python 环境中的 Pillow 没有 WebP 编码支持，节点会明确报错，不会伪装成保存成功。

### JPEG

JPEG 不支持 Alpha。本节点不会静默丢弃透明通道，而是将 RGBA 图像按 `jpeg_background` 指定颜色合成后再编码：

`output = foreground × alpha + background × (1 − alpha)`

- `#FFFFFF`：透明区域变为白色。
- `#000000`：透明区域变为黑色。
- `#RRGGBB`：可以指定任意 8-bit RGB 背景色。
- RGB 输入直接保存为 JPEG。

JPEG 是有损格式，边缘像素和颜色可能出现压缩偏差；不要用 JPEG 验证逐像素精确一致性。

## 4. 保存位置和命名

文件保存到 ComfyUI 的标准 output directory，不使用插件私有目录，也不改变 ComfyUI 全局配置。

`filename_prefix` 交给 ComfyUI 的 `folder_paths.get_save_image_path` 处理，因此遵守 ComfyUI 的输出路径约束、子目录和文件名变量规则。示例：

- `GPTImageBridge` → `output/GPTImageBridge_00001_.png`
- `images/gpt-image` → `output/images/gpt-image_00001_.webp`
- `daily/%year%-%month%-%day%/image` → 按 ComfyUI 日期变量创建子目录

batch 中每一帧会单独保存并递增序号；如果文件名前缀包含 `%batch_num%`，会替换为从 0 开始的 batch index。UI 返回的 `filename`、`subfolder`、`type=output` 可用于 ComfyUI 历史/预览。

## 5. 工作流

### GPT Image 生成后保存 WebP

```text
[CLIProxyAPI Provider] ── provider ──► [Generate]
                                         │ image
                                         ▼
                                [GPT Image Bridge · Save Image]
                                  file_format = webp
                                  webp_lossless = true
```

### 透明图片保存为 JPEG

```text
[Generate / Edit] ── IMAGE ──► [GPT Image Bridge · Save Image]
                                  file_format = jpeg
                                  jpeg_background = #FFFFFF
```

这只表示本地保存节点能够正确处理已有 Alpha。它不会替上游生成透明背景。如果真实图片 API 返回的是 RGB，节点没有透明信息可供保留或合成。

## 6. 与 ComfyUI 原生 Save Image 的关系

- 原生 Save Image 继续保留，适合常规 PNG 工作流和现有画布。
- 本节点提供 JPEG/WebP 本地编码、质量控制、JPEG Alpha 背景合成。
- 两者都写入 ComfyUI output directory。
- 本节点不嵌入 prompt、workflow 或 `extra_pnginfo` 元数据，避免将本地工作流/提示词内容意外写入可分享的 JPEG/WebP/PNG 文件。需要 ComfyUI 原生 PNG 元数据行为时，继续使用原生 Save Image。
- 本节点返回原始 IMAGE Tensor，不会因为保存为 JPEG 就把下游 IMAGE 也改成 RGB；下游仍收到输入的 RGB/RGBA Tensor。

## 7. 边界和故障排查

| 现象 | 原因/处理 |
| --- | --- |
| WebP 保存报 Pillow 不支持 | 检查启动 ComfyUI 的同一个 Python 环境中的 Pillow 是否带 WebP 编码能力；不要只在另一个系统 Python 中安装 Pillow |
| JPEG 透明区域颜色不对 | 检查 `jpeg_background`，必须使用 `#RRGGBB` |
| JPEG 边缘与 PNG 不完全相同 | JPEG 有损压缩，属于预期；需要无损时用 PNG 或 lossless WebP |
| 生成结果仍是 1536×1024 | 本节点只编码已有像素，不负责上游尺寸控制或超分 |
| 上游设置了 `output_format=webp`，但本地保存 PNG | 上游响应格式和本地保存格式是两个控件；分别检查 Generate/Edit 的 `output_format` 与本节点的 `file_format` |
| 透明背景请求仍得到 RGB | 上游没有返回 Alpha；本节点不能从纯 RGB 图像推断出真实透明区域 |

## 8. 隐私和资源

- 不向第三方上传图片；编码和文件写入都在 ComfyUI 进程本机完成。
- 文件保存在 ComfyUI output directory，目录权限和备份策略由用户环境决定。
- 输出 Tensor 会被复制到 CPU 并转换为 8-bit 像素后编码；高分辨率、多图 batch 会占用相应 CPU 内存。
- 节点拒绝空 batch、非 RGB/RGBA 通道、NaN/Inf 像素、非法质量/压缩值和非法 JPEG 背景色。
