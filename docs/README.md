# GPT Image Bridge：文档目录

本目录面向使用者、部署者、维护者，**所有操作以本 fork 的 `feat/cliproxyapi-native-provider` 分支为准**。目前 [PR #1](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/pull/1) 尚未合并到 `main`；ComfyUI Registry 仍提供原作者版本，**安装 Registry 版本不会得到 CLIProxyAPI Provider**。

## 文档导航

| 文档 | 面向 | 内容 |
| --- | --- | --- |
| [CLIProxyAPI 安装与登录](setup-cli-proxy-api.md) | 初次本机部署 | v8 配置、客户端 Key、Codex 登录、进程启动、连通性检查、Docker/网络差异 |
| [节点及工作流手册](nodes-and-workflows.md) | 使用者 | 六种节点、全部重要参数、生成/编辑/参考图、保存、请求数量及输出 |
| [协议与实现](protocol-reference.md) | 调试/开发 | Images/Responses 路由、模型角色、请求字段、响应解析、错误与兼容范围 |
| [兼容 API 与异步任务](compatibility-and-async.md) | 非 CLIProxyAPI 用户 | 原通用 API Provider、异步任务协议、JSON 映射、自定义端点、回退 |
| [凭据与安全](security.md) | 部署/分享工作流 | 授权边界、一次性队列句柄、本地工作流明文、网络暴露、错误脱敏 |
| [故障排查](troubleshooting.md) | 遇到失败时 | 按错误类别定位登录、网络、模型、图片编辑、前端、额度 |
| [测试与验收](testing.md) | 实机验收/开发 | 真实 ComfyUI CI 证据、自动化测试、手工验收、限制与结果记录 |

## 示例工作流

- [CLIProxyAPI 纯文生图（无凭据，推荐首次本地验收）](../example_workflows/CLIProxyAPI-Text-to-Image.json)
- [上游 OAuth / 通用 API 图片编辑示例](../example_workflows/GPT-Image-Bridge-Edit-Example.json)

## 目前有哪些证据？

- **已通过**：Python + JavaScript 测试；Ubuntu GitHub Runner 上真正启动 ComfyUI 0.44.0，注册插件节点，通过 `/prompt` 执行三种工作流、检查生成的 PNG 与队列/历史脱敏。
- **未通过真实验收**：CLIProxyAPI 的真实进程 + Codex OAuth 授权 + 上游真实图片生成；测试中的代理是实现相同 HTTP 返回格式的本机替身。两者不可混为一谈。
- **未声称覆盖**：Windows/macOS 图形界面、Docker 组合、所有第三方兼容 API、长时间持续运行、上游额度/计费及内容审核行为。
- **原生 Codex OAuth**：保留旧节点以兼容旧工作流，但新部署优先使用专用 CLIProxyAPI Provider。

完整证据和可复现命令见 [测试与验收](testing.md)。

## 上游源码与更新策略

- 插件上游：[Liu-Bot24/comfyui-gpt-image-bridge](https://github.com/Liu-Bot24/comfyui-gpt-image-bridge)
- 本 fork：[Fuck-GH-Admin/comfyui-gpt-image-bridge](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge)
- 协议参考：[router-for-me/CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)（主要参考 v8 的 `config.example.yaml`、`internal/runtime/executor/codex_openai_images.go`、`sdk/api/handlers/openai/openai_images_handlers.go`）
- ComfyUI：[Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI)

上游代码、模型名称及非公开 Codex 生图接口会变化。需要区分**源码中已有实现**、**本仓库自动测试的观察**和**本机真实账号的验收结果**。测试通过不能推出接口永久稳定或订阅永远可用。
