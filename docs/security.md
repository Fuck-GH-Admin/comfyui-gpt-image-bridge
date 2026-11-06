# 凭据、安全边界和分享工作流

此文档解释插件**实际如何处理密钥**，以及它不能替用户解决的安全问题。若只想运行，先看 [本机安装](setup-cli-proxy-api.md)；真实节点行为见 [协议与实现](protocol-reference.md)。

## 1. 三种凭据不要混用

| 凭据 | 持有者/用途 | 是否输入 ComfyUI |
| --- | --- | --- |
| CLIProxyAPI **客户端 Key** | `config.yaml` 的 `access.api-keys`；授权 ComfyUI 调用代理的 HTTP API | **是**，填专用 Provider 的 `api_key` |
| Codex **OAuth Token** | CLIProxyAPI 登录后的上游账户授权；由代理自身存放、刷新 | **否**，不要粘贴给插件 |
| OpenAI **公共 API Key** | 公共 API 平台独立计费凭据，只用于对应公共 API | 使用通用 API Provider 时可填；**不代表 Codex 订阅额度** |

本 fork 新的 CLIProxyAPI Provider 不读取 `~/.codex/auth.json`，也不直接访问 ChatGPT 的 Codex 私有接口。它只知道代理的 HTTP 地址和客户端 Key。

原生 Codex OAuth Provider 是保留的**另一条旧路径**：它会尝试从 `CODEX_HOME/auth.json` 或 `~/.codex/auth.json` 读取 OAuth 状态，并按实现需要刷新/写回。选用哪条路径必须自觉区分。

## 2. 客户端 Key 从输入框到队列的流程

```text
ComfyUI 浏览器前端（工作流中可以保存明文 Key）
   │  用户编辑 API Key 密码控件
   │  启动生成时调用 POST /gpt-image-bridge/session-credential
   ▼
ComfyUI 服务器进程内存
   │  存入短期凭据表，返回随机不可预测的句柄
   ▼
ComfyUI /prompt 队列
   │  收到句柄而不是原始 Key
   │  提交前还有 /prompt 守卫校验
   ▼
ProviderConfig / 执行阶段
   │  消耗句柄，取出 Key，执行 HTTP 请求
   ▼
CLIProxyAPI: Authorization: Bearer <client key>
```

实际实现文件：

- [session_credentials.py](../gpt_image_bridge/session_credentials.py)：句柄生成与消耗。
- [routes.py](../gpt_image_bridge/routes.py)：临时凭据端点、队列守卫、工作流元数据清理。
- [api_key_widget.js](../gpt_image_bridge/web/api_key_widget.js)：密码输入控件、序列化时换成句柄。

### 句柄的已实现限制

| 项目 | 源码约束 |
| --- | --- |
| 保存位置 | 当前 ComfyUI Python 进程的内存字典，**不是持久化数据库** |
| 有效期 | 10 分钟（600 秒） |
| 进程内上限 | 128 条，会清理过期值并在满额时淘汰较旧值 |
| 生成方式 | `secrets.token_urlsafe(32)` 随机句柄 |
| 使用次数 | **消费一次后删除** |
| 重启 ComfyUI | 内存句柄全部失效 |
| 最大 Key 长度 | 16 KiB 字符串上限；普通客户端 Key 远远小于此值 |

如果提交任务后排队过久、服务器重启、前端扩展未加载或句柄已经被消费，运行时可能提示 `session_credential_missing`、`session_credential_required`。这时候重新 Queue 并输入 Key，不要把明文 Key 接到普通 STRING 节点绕过守卫。

### /prompt 保护

队列守卫只针对本插件定义的两类 API Provider：

- `GPTImageBridgeAPIProvider`
- `GPTImageBridgeCLIProxyAPIProvider`

如果发现 `api_key` 既不是空值，也不是格式正确的临时句柄，就**拒绝整个 prompt**，而不是让某个未选中的懒执行分支带着原始 Key 进入历史。

对排队携带的工作流元数据，守卫还会清除相应 Provider 的 `widgets_values[0]`，防止它作为 PNG 工作流元数据写出。

这是一层面向**正常 ComfyUI 前端与队列路径**的保护，不应被理解为能保护所有第三方插件、恶意浏览器扩展或本机管理员。

## 3. 重要：本地工作流仍然可能明文保存 Key

**密码输入控件 ≠ 端到端加密存储。**

本插件的前端为方便用户重新打开工作流，保留 Key 的本地序列化行为；导出的工作流 JSON 和浏览器中的工作流配置**可能含有明文客户端 Key**。保护的是提交执行时的 `/prompt` 内容和后续工作流历史，不是把本地文件变成无密钥配置。

分享工作流、截图、创建 Issue、上传 PNG 之前应：

1. 打开所有通用 API Provider 与 CLIProxyAPI Provider，清空 `api_key`。
2. 检查 `base_url`、自定义端点、模型别名及异步 JSON 映射里是否包含内部服务信息。
3. 另存为一份**用于分享**的副本，检查 JSON 文本中不包含 Key、Token、私有地址。
4. 任何已经被公开暴露的客户端 Key 都应在 CLIProxyAPI 侧撤销/更换。

同一工作流中的非本插件节点（例如任意运行 Shell/脚本的节点）可能能够读取本机文件或访问代理，本插件无法防止它们行为不当。

## 4. 网络与代理的安全边界

初次本机部署：

```yaml
server:
  host: "127.0.0.1"
  port: 8317
```

这样可把 CLIProxyAPI 的 HTTP API 限定在本机环回接口。注意：

- `127.0.0.1` 仅限制网络访问来源，不等于本机所有进程都可信。
- ComfyUI / CLIProxyAPI 处于不同容器、虚拟机或远程设备时，环回地址不跨环境，需要明确配置可达地址。
- 若把代理暴露到非可信网段，至少应使用 TLS/受信任的反向代理、ACL/防火墙、随机高强度客户端 Key；管理接口与 OAuth 登录回调应独立保护。
- 不建议在公网暴露未认证的 ComfyUI 服务器。任何有权提交 ComfyUI 工作流的人，可能触发已配置的外部服务调用与额度消耗。
- **不要把私有 Codex Token 放在 HTTP 查询参数、工作流提示词、Issue、控制台截图里。**

客户端 Key 发送给哪个服务由 `base_url` 决定；只填写你控制且信任的 CLIProxyAPI 地址。第三方中转站可能接触你的客户端访问、提示词与图片，因此即使它声称兼容 API，也不代表隐私和凭据有保障。

## 5. HTTP 与图像下载边界

当前实现具备以下保护（以源码为准）：

- 授权请求采用 Bearer Header，不对带 Authorization 的请求盲目跟随重定向。
- 图片结果可来自 Base64 或 URL；URL 下载做协议、地址、MIME、文件尺寸/字节数等校验，并**不把代理 Bearer Key 转发给图片 URL**。
- 诊断和异常信息通过脱敏逻辑处理，尽量不记录 Authorization、原始 Token、完整图片 Base64 或敏感查询参数。
- 请求 `timeout_sec` 并不等于能取消上游已受理的任务。因不确定响应而盲目重试可能增加使用量。

这些是既有边界，不是完整安全审计。大型多媒体输入还会占用 CPU/RAM、ComfyUI 内存和网络带宽；受限终端可通过限制服务暴露和上游请求体大小进行额外管控。

## 6. 为什么不建议直接用真实 OAuth 做 CI？

CI 和公开仓库不应持有个人 ChatGPT/Codex OAuth Token。项目目前使用：

- 单元测试：模拟 HTTP 响应与临时句柄，验证具体请求语义。
- 集成测试：真实运行 ComfyUI，但后端使用本机假代理，检查图像保存及历史脱敏。
- 真实账户生图：只能由拥有账号与适当授权的使用者在本地环境完成。

任何测试报告都应分别标记**真实 ComfyUI 运行成功**和**真实 CLIProxyAPI + OAuth 上游生图成功**，后者尚无自动化证据。

## 7. 订阅和服务接口的限制

CLIProxyAPI 使用的 Codex 图片请求路径涉及不断演进的服务接口；这不是 OpenAI 公共 API 针对 ComfyUI 的正式兼容保证。服务端可能调整模型名称、额度、验证或协议；不能把现阶段的源码行为写成永久可用或无限制生图。

继续：[故障排查](troubleshooting.md) · [测试与验收](testing.md)。
