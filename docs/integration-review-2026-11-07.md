# ComfyUI GPT Image Bridge｜2026-11-07 主线整合核验记录

本记录是对旧交接快照的补充。旧 `docs/handoff/2026-11-07-context.md` 仅代表 2026-11-07 00:32 的状态，不能当作当前 HEAD。

## 一、四个 PR 的审查与合并

| PR | Squash 合并 SHA | 结论 |
| --- | --- | --- |
| [#6](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/pull/6) | `5e1438475601d53842e48fb94935ae0135c0c7b1` | 第七个 Save Image 节点：PNG、JPEG、WebP，本地输出目录、批次编号、RGBA 及 JPEG matte；通过 ComfyUI CPU 集成 |
| [#8](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/pull/8) | `2e3e982221854d4323afda3d2f5dabf5ef44a95d` | 增加 API 返回字节的尺寸、编码、Alpha 核验；`pass/warning/not_checked`；补足 Responses/Chat/OAuth 协议回归 |
| [#9](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/pull/9) | `5de6c3f59c9a150980cff2ec7e6ec47763150311` | CLIProxyAPI v8.0.57 Codex Images 不转发 `complexity`；修正文档和 tooltip |
| [#7](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/pull/7) | `6a35bcc8936c76ab58a88d8f2383447a5b090ec5` | 一次真实 Codex `background=transparent` 请求保存 RGBA PNG 1536×1024，Alpha extrema 0–254，仅证明单样例成功 |

合并顺序为 #6 → #8 → #9 → #7。重叠文档经过合并核对，保留七节点、输出兑现核验、CLIProxyAPI 参数边界及透明 Alpha 单样例限制。

## 二、自动化验证

- [合并四个 PR 后的 main 单测](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42265470712)，精确代码提交 `74b963205fc40679c5402dc89d24b513421c71a1`：**313 项 Python 通过、无 warning；14 项 JavaScript 通过**。这次提交仅将 Saver 测试里废弃的 Pillow `getdata()` 替换为 `getpixel()`。
- [四 PR 组合完整树的真实 ComfyUI 0.44.0 CPU + fake API 集成](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42264786784)：**PASS**。七节点注册、文本 Generate、Images Edit 参考图生成、可选 Responses、Edit、无损 WebP Alpha、本地 JPEG matte、7 次代理请求均通过。
- [main push 自动集成的首次执行](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42266430279)：**PASS**，在 `949ebc928a8f3354f9e230c69d2389ad1a514b45` 触发。现已让 `comfyui-integration.yml` 对 main push 自动运行，并加入并发去重，后续需核查最新 HEAD 对应的运行。
- **ComfyUI 进程是真实的，图像服务是模拟的**。CI 不能代替真实 CLIProxyAPI + Codex OAuth 账号验收；本次整合没有消耗用户生图额度。

## 三、重要能力边界

1. 默认：无参考图走 Images Generate，有参考图的 Generate 走 Images Edit，Edit 走 Images Edit；Responses 仅为手动可选模式。
2. 输出兑现报告检查的是**上游返回图片字节**的宽高、格式、透明像素；`pass` 不代表质量或视觉语义验证。被协议忽略、不可比较的参数应为 `not_checked`，不误报 `pass`。
3. 本地 Save Image 重新编码 PNG/JPEG/WebP，不证明上游原生 JPEG/WebP 或 2K/4K 输出已兑现。历史真实测试中的 Custom/2K/4K、上游 JPEG/WebP 仍有未达标记录。
4. CLIProxyAPI v8.0.57 默认 Codex Images 转换层丢弃 `complexity`，推荐 `auto`；SVG、GIF、markup-guided editing 尚未实现。
5. 单次真实透明背景请求的 RGBA 成功不能推广至所有请求；Responses 路由历史上有 DNS 失败，Chat Completions 图片路由历史上返回过 503。
6. Windows/macOS、本机 GUI 交互、真实账户当前最新提交的端到端运行、长时间使用和异构部署均未在本轮新增验证。

## 四、安全与历史分支

没有在本次整合中提交 OAuth token、`auth.json`、真实图片 Base64、Bearer Header、Cookie 或私有配置。工作流分享前必须清空客户端 Key；CLIProxyAPI 默认仅监听 `127.0.0.1`。

#6–#9 的 PR 均已合并关闭。[GitHub Actions 42266944295](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42266944295) 先核对六个旧分支完整 SHA，再成功删除四个 PR 源分支和两个历史 fix 分支；删除后重新枚举远端，**只剩 `main`，开放 PR 为零**。清理时使用了一次性、白名单化的临时工作流，完成后移除该工作流文件以避免保留不必要的写权限入口。