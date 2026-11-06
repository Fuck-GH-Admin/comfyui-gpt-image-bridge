# 输出参数兑现核验

GPT Image 请求成功返回图片，不代表所有请求选项都被上游执行。特别是在 Codex OAuth 经 CLIProxyAPI 转换调用时，HTTP 200 只能说明请求链路完成，不能证明模型按指定尺寸、编码或透明背景生成。

本功能在 Generate/Edit 的脱敏 `request_report.output.conformance` 中，对可从图片字节直接验证的参数做事后核对。

## 核验项目

| 请求字段 | 核验方法 | 判定 |
| --- | --- | --- |
| `size` | 对比请求的 `WIDTHxHEIGHT` 与每张返回图片实际宽高 | 任一张不一致，产生 `size_mismatch` warning |
| `output_format` | 对比请求的 PNG/JPEG/WebP 与 Pillow 检测到的实际编码 | 任一张不一致，产生 `format_mismatch` warning |
| `background=transparent` | 检查返回图片是否有 Alpha 通道，并且 Alpha 最小值小于 255 | 没有透明像素，产生 `transparency_missing` warning |

质量、复杂度等无法仅从最终图片可靠反推的选项不会被伪造为“已验证”。`auto` 尺寸不做固定尺寸断言。

## 报告结构

`request_report` 是脱敏 JSON。示例：

```json
{
  "output": {
    "count": 1,
    "images": [
      {
        "width": 1536,
        "height": 1024,
        "format": "PNG",
        "mode": "RGB",
        "has_alpha": false,
        "alpha_extrema": null
      }
    ],
    "conformance": {
      "status": "warning",
      "requested": {
        "size": "2048x1152",
        "background": "transparent",
        "output_format": "webp"
      },
      "checked_images": 1,
      "warnings": [
        {
          "field": "size",
          "type": "size_mismatch",
          "images": [
            {
              "index": 1,
              "requested": "2048x1152",
              "actual": "1536x1024"
            }
          ]
        },
        {
          "field": "output_format",
          "type": "format_mismatch"
        },
        {
          "field": "background",
          "type": "transparency_missing"
        }
      ]
    }
  }
}
```

字段含义：

- `status=pass`：至少有一个可核验字段，且所有已检查字段与返回图片一致。
- `status=warning`：至少一个可核验字段与实际输出不一致。
- `status=not_checked`：没有返回图片，或当前协议没有可比较的请求字段；不能将其理解为通过。
- `checked_fields`：实际进行比对的字段列表。
- `requested`：本节点提交的选项，不代表服务端确认执行。
- `images`：从真实返回字节解码得到的格式、尺寸、模式、Alpha 和字节数。
- `warnings[].images[].index`：从 1 开始的图片序号。

## 协议差异

核验器会尊重协议报告中的 `ignored_options`，不会对明确不支持的选项发出误导性警告。例如 Chat Completions 适配路径把 size 写入提示词而非严格图像尺寸参数；旧 Codex OAuth 路径也明确标记了其忽略的 background/output_format 字段。

CLIProxyAPI Codex OAuth 路径若把 Images API 的选项传入代理，但实际响应仍未兑现，则会出现 warning。这正是该报告要捕获的情况。

## 重要边界

- 核验发生在图片已经返回之后，不能退款、取消上游任务或撤销额度消耗。
- warning 不会自动重试，避免重复生成和重复扣费。
- 这不是上游能力探测，也不能证明服务未来会继续支持相同参数。
- PNG/WebP 的 Alpha 元数据只证明返回图片含有透明像素，不证明透明边缘质量、抠图准确度或模型遵守了特定视觉要求。
- 请求格式与本地保存格式是两个层次；本核验检查的是 API 返回字节。若随后使用本地 JPEG/WebP 保存节点，那个节点的编码结果另行测试。

如果 warning 持续出现，应先保存脱敏 `request_report`、核对代理版本和上游模型，再决定是否调整参数。不要用本地插值或重新编码把不符合请求的结果标成原生尺寸/格式通过。
