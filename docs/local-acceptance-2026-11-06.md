# 本地验收记录（2026-11-06）

本次使用真实 ComfyUI、CLIProxyAPI 进程和本人授权的 Codex 账号执行了实际请求。结论：**纯文生图、基础图编辑、基础图加参考图编辑通过；参考图 Generate 的 Responses 路径未通过**。不能据此宣称全部功能可用。

## 环境与边界

| 项目 | 实测值 |
| --- | --- |
| 插件分支 / 提交 | `feat/cliproxyapi-native-provider` / `c7c334ad180586affaa8eba962604c3bfe762974` |
| ComfyUI | `0.44.0` / `6b203164749929ab2ed01c9fd4638381ba78de71` |
| CLIProxyAPI | 官方 Linux amd64 `8.0.57` / `c2f402b4`；发行包 SHA-256 已核对 |
| 系统 / Python | Ubuntu Linux x86-64 / Python `3.12.16` |
| PyTorch | `2.15.0+cpu`，ComfyUI 使用 `--cpu`；没有本地生图模型 |
| 其他依赖 | torchvision `0.29.2+cpu`，torchaudio `2.11.1+cpu`，NumPy `2.5.4`，Pillow `13.0.0` |
| 网络 | ComfyUI 与代理同机，均只监听 `127.0.0.1` |
| 代理配置 | v8 `access.api-keys`，独立 OAuth 目录；图片功能开启，额外重试轮数为 0 |
| 图片模型 | `gpt-image-2` |
| Responses 模型 | 默认 `gpt-5.4-mini`；另测目录中存在的 `gpt-6.1-sol` |
| 认证 | Codex 设备登录成功；插件仅持有代理客户端 Key |

公开记录不包含账号标识、认证文件、客户端 Key、Token、私有目录或含密钥的工作流。图片素材均为测试用合成图；下面的 JPG 是去除 PNG 工作流元数据后的缩略图。原 PNG 的校验值见证据 JSON。

## 本地结果

| 验证项 | 结果 | 证据 / 限制 |
| --- | --- | --- |
| Python 单元测试 | PASS | `222 passed` |
| JavaScript 单元测试 | PASS | Node 22，`12 passed` |
| 真实 ComfyUI + 假代理集成 | PASS | 六个节点注册；文生图 n=2、参考图 Generate、参考图 Edit；四次协议请求和四张 PNG；`COMFYUI_SMOKE_PASS` |
| CLIProxyAPI 真实进程及客户端鉴权 | PASS | `/v1/models` 返回 200，18 个条目，含 `gpt-image-2` |
| 真实纯文本 Generate | PASS | 一次 n=1；保存 1536×1024 PNG |
| 真实基础图 Edit | PASS | `/v1/images/edits` 200；一次请求，约 19.18 秒；1536×1024 PNG |
| 真实 Edit + Reference List | PASS | `/v1/images/edits` 200；一次请求，约 19.03 秒；1536×1024 基础图 + 256×192 参考图分别编码，角色和顺序保留 |
| 真实参考图 Generate，默认模型 | FAIL | `/v1/responses` 400，`model_not_found`：当前代理未提供 `gpt-5.4-mini`；一次尝试 |
| 真实参考图 Generate，目录内模型 | BLOCKED | 改为已列出的 `gpt-6.1-sol` 后返回 500；代理报告解析 `chatgpt.com` 失败，上游请求未能建立；一次尝试 |
| 空客户端 Key | PASS（预期失败） | ComfyUI 执行返回 `credential_missing`，约 1 秒 |
| 无效代理客户端 Key | PASS（预期失败） | 代理 401，约 1 秒；未进行有效上游生成 |
| 不存在的临时句柄 | PASS（预期失败） | `session_credential_missing`，约 1 秒；未声称实际等待了 600 秒过期 |
| 已消费句柄重放 | PASS（预期失败） | 重放 401 用例已消费的句柄，返回 `session_credential_missing`，约 0.27 秒 |
| 不可达代理 | PASS（预期失败） | 使用未监听的本机端口，返回 `network_error`，约 1 秒；没有停止正在运行的服务 |
| 历史和输出 PNG 凭据检查 | PASS | 本轮各队列历史不含真实客户端 Key；成功输出的 PNG 元数据也不含该 Key |

纯文本 Generate 的 prompt ID 为 `da27fe0d-0af9-4d48-afb0-259b12483184`；PNG SHA-256 为 `da4a3bc8a113f38f55e4283ddadec6dd543a0b452b4b5be535ffeef54017ef72`，922894 字节。其余队列 ID、原 PNG 大小、校验值、输入角色和安全错误摘要见[机器可读证据](evidence/local-acceptance-2026-11-06.json)。这份 JSON 是本机验收摘要，不是 CI 自动运行结果。

## 实际图像内容

初始生成提示词：`A simple test illustration: one bright orange circle centered on a clean blue background.`

基础编辑提示词：`Keep the blue background and orange circle. Add a small red triangle in the top left corner.` 实际保留了蓝底和橙色圆，并在左上角增加红色三角形。

![真实基础编辑缩略图](images/local-acceptance-edit-base.jpg)

带参考图编辑使用一张白底红色三角形合成参考图（256×192），提示词为：`Preserve the blue background and the orange circle. Add a small red triangle in the top left corner, using the reference triangle for its color and shape.` 实际输出符合这些可见要求。这个简单测试不能证明复杂人物身份、构图或多参考图的一致性。

![真实带参考图编辑缩略图](images/local-acceptance-edit-reference.jpg)

## 浏览器实测

在本机真实 ComfyUI 页面加载扩展，使用非秘密占位字符串执行了以下检查：

- 页面能创建全部六个节点；Provider 的密码编辑器使用真正的 `input[type=password]`。
- 点击 Save 保存占位值；点击 Cancel 关闭编辑器；节点画布绘制固定掩码，未绘制占位原文。
- 调用实际控件的 `serializeValue()` 能从后端获得 `gpt-image-bridge-session:` 临时句柄，句柄不含占位原文。
- 工作流序列化仍保留占位 Key：**导出本地工作流不是无密钥导出**，分享前仍需清空 Key。
- 重新配置节点后密码控件仍受保护。
- Generate 初始显示三个参考入口，依次连接三个 IMAGE 输出后增加第四个空入口。

这些检查结合了实际浏览器点击、DOM 检查和图对象操作，没有在浏览器输入真实 Key，也没有通过这些 UI 检查追加付费请求。

## 复现与后续处理

先按 [testing.md](testing.md) 运行现有 Python、JavaScript 和假代理集成测试。真实测试通过 ComfyUI 的 HTTP 队列执行：

1. 使用已配置客户端 Key 调用 `/gpt-image-bridge/session-credential`，仅将返回句柄填入 `GPTImageBridgeCLIProxyAPIProvider.api_key`。
2. 连接 Provider → Generate/Edit → SaveImage；本次另将 `request_report` 接到原生 `PreviewAny`，从 `/history/{prompt_id}` 获取脱敏请求报告。
3. Generate/Edit 设置 `size/quality/background/moderation=auto`、`output_format=png`、`n=1`、`timeout_sec=300`。一次排队后轮询历史，不自动重新排队。
4. 基础 Edit 连接原生成图；带参考图 Edit 再经 Reference List 连接独立合成参考图。参考图 Generate 将基础素材接到 `reference_1`。
5. 检查执行状态、PNG 解码和尺寸、请求协议/输入角色，以及历史和 PNG 元数据中是否存在客户端 Key。

参考图 Generate 有两个独立待处理项：先把 `responses_model` 改为本机 `/v1/models` 实际列出的普通 Responses 模型；再解决代理进程访问 `chatgpt.com` 的 DNS/网络问题，之后重新验收 Responses 真实返回图像。模型列表成功不能证明该模型的图像工具可用。本次没有修改默认模型或机器全局 DNS，也没有把该路径记作 PASS。

尚未覆盖：真实 Mask、JPEG/WebP、真实 n>1、多参考图超过两张、并发、真实 429/上游超时后的任务核对、真正的 600 秒句柄过期、服务重启后的 UI 恢复，以及 Windows/macOS/Docker/长期运行。当前成功结论限于本表列出的环境和工作流。
