# 故障排查：从 ComfyUI 到 CLIProxyAPI，再到 Codex

优先按请求发生顺序排查。出现错误时**不要首先无脑重复 Queue**：图片请求可能在服务端成功执行，只是本机没收到响应；尤其是 `n>1` 时，前面若干张已经产生独立请求。

## 0. 四层定位法

```text
A. ComfyUI 加载层  → 是否能搜索到插件节点？
B. ComfyUI 队列层  → /prompt 是否接受？前端一次性 Key 是否正常？
C. CLIProxyAPI 层 → 代理进程是否运行？客户端 Key、端点、模型路由对不对？
D. Codex 上游层 → OAuth 是否有效？服务端模型是否可用？额度/审核是否允许？
```

仅当 A、B、C 均正常时才排查 D；把所有 401/404 都理解为「模型被封」通常会浪费时间。

## 1. 常见故障速查

| 症状/提示 | 优先检查 | 处理 |
| --- | --- | --- |
| ComfyUI 搜不到 `CLIProxyAPI Provider` | clone 到了 `main`/Registry 原版、错误的 `custom_nodes` 目录、没重启后端 | `git branch --show-current` 应是 `feat/image26-images-first-reference-mode`；检查 `__init__.py` 存在且后端启动日志没有 import error |
| 只看到 API Provider 或 Codex OAuth Provider | 安装了原作者版或另一个 ComfyUI 实例 | 禁用重复包，使用 fork 当前开发分支 |
| ComfyUI 节点是红色/报 missing node | Python 环境依赖、目录嵌套、节点包导入失败 | 用启动 ComfyUI 的**相同 Python**安装 `requirements.txt`；检查日志 |
| Queue 立即返回 400 或 Key 守卫拒绝 | 前端 JS 未正确加载，明文 Key 进入 `/prompt` | 完全重启 ComfyUI，浏览器强制刷新，重新输入 Key；不要通过普通 STRING 节点传明文 |
| `session_credential_required` | 没有使用受保护的密码控件提交 | 确认插件前端扩展加载成功；重新输入 Key 再 Queue |
| `session_credential_missing` | 句柄使用超时/已被消耗/进程重启 | 重新 Queue，必要时重输 Key；勿复用旧排队 JSON |
| Connection refused / timeout | CLIProxyAPI 没运行、监听地址/端口不对、容器网络隔离 | 确认 `server.host`、`server.port`、`base_url`；同环境用 curl 测试 |
| HTTP 401（代理层） | ComfyUI 传的客户端 Key 与 `access.api-keys` 不同 | 重输客户端 Key；**不要换成 OAuth Token** |
| HTTP 401/403（代理上游） | Codex OAuth 登录过期、权限受限、上游拒绝 | 看 CLIProxyAPI 日志区分；重新按 CLIProxyAPI 文档登录 |
| HTTP 404（某路由） | Base URL、代理版本、模型别名、功能禁用 | 检查 `/v1`、当前版本、`multimedia.disable-image-generation` |
| HTTP 400/422 | 请求参数或模型不兼容 | 先 `size=auto`、`quality=auto`、`output_format=png`，`n=1` |
| HTTP 429 | 并发/配额/限流 | 停止并发，确认实际额度；不要立刻批量重试 |
| HTTP 5xx / 断线 | 代理、上游或网络故障 | 看代理日志与 request ID，确认请求是否可能已完成后再重试 |
| 纯文生图成功，但参考图 Generate 失败 | 先检查 `reference_mode`、`/v1/images/edits` | 默认 `images_edit` 无须文本主模型；只有手动切到 `responses` 时才排查 `responses_model`、工具路由及 DNS |
| Generate 可以，Edit 失败 | multipart 支持、图片数量、Mask、编辑模型权限 | 用「单张基础图 + 无 Mask + n=1」先做最小 Edit |
| 输出为空或报无图片 | 上游返回了文字/拒绝、SSE 不符合接口、Base64/URL 解析失败 | 记录脱敏的报告、代理的模型/HTTP 状态；不要把空输出称作成功 |
| 保存后找不到 PNG | 没连接 Save Image、输出目录另设、其他 ComfyUI 实例 | 确认 Generate/Edit 的 `image` 接到 Save Image、检查当前实例输出目录 |
| 参考图顺序不对 | `reference_*` 或 `image_*` 中间有空洞 | 按数字连续连接，每个插口只放一张 IMAGE，不用 IMAGE batch |
| CPU 可以云生图，本地放大失败 | 其他节点需要 GPU/ROCm | 插件不负责本地采样；排查对应模型或后处理节点的硬件需求 |

## 2. 检查仓库和运行实例

在插件目录：

```bash
git status --short
git remote -v
git branch --show-current
git log -1 --format='%H %s'
```

当前开发分支应是 `feat/image26-images-first-reference-mode`，并且在实际 ComfyUI 的 `custom_nodes` 里。若仍为 `main`，这份 fork 的 CLIProxyAPI Provider 很可能根本没安装进去。

完全停止 ComfyUI，再启动。需要看控制台中是否出现加载该包的成功记录以及 Python 报错。**浏览器重新打开画布不会自动重载服务器端 Python 插件**。

如 CPU 模式排障（仅作独立对照测试）：

```bash
cd /path/to/ComfyUI
python main.py --cpu --listen 127.0.0.1 --port 8188
```

其中 `python` 必须是 ComfyUI 对应的 Python 环境，避免误用系统 Python。若你日常运行的是独立进程、Docker、便携包或其他端口，请对照实际实例改命令；不要同时启动两套占用同端口的 ComfyUI。

### 检查节点是否被后端注册

```bash
curl --silent --show-error \
  http://127.0.0.1:8188/object_info/GPTImageBridgeCLIProxyAPIProvider
```

返回一个包含 `GPTImageBridgeCLIProxyAPIProvider` 的 JSON 对象，说明 Python 类和 `INPUT_TYPES` 已被实际后端注册；它**不能证明前端密码控件和真实生图服务都正常**。

## 3. 检查 CLIProxyAPI HTTP 服务

在与 ComfyUI 同一网络位置运行：

```bash
# Linux：查看 8317 端口是否有监听
ss -lntp | grep ':8317' || true

# 不把密钥直接写入 Shell 历史
read -rsp 'CLIProxyAPI client key: ' CPA_KEY
echo

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer ${CPA_KEY}" \
  http://127.0.0.1:8317/v1/models
```

若配置不是本机 8317，修改 URL。网络检查不要把真实客户端 Key 作为 URL 查询参数。收到模型列表表示客户端访问层大体正常，**不保证实际图像生成可用**。

若是 Docker/虚拟机：

- ComfyUI 和代理位于不同容器时，`127.0.0.1` 不能互通。
- 应先确保可信内部网络与 DNS/路由连通，再用对应服务名或地址填写 `base_url`。
- 不要为了排障而直接将 CLIProxyAPI 的 API、管理接口或 OAuth 回调暴露公网。

## 4. 分类检查生图路径

### A：纯文生图

让图像模型保持代理明确支持的名称，`n=1`、其余使用 `auto`。期待端点：

```text
POST /v1/images/generations
```

若该路径返回 404：

- 确认使用的是较新 CLIProxyAPI v8，而不是旧版本/其他服务。
- 检查 `multimedia.disable-image-generation` 是否为 `true`。
- 确认代理的 Codex OAuth 已登录且路由到具有图片功能的账户。
- 不要仅凭 `/v1/models` 列表有图片模型名就认定上游已经生成成功。

### B：带参考图的 Generate

**默认 `reference_mode=images_edit`**：实际向 `POST /v1/images/edits` 发送 multipart，首张参考图是 Image 1，提示词要求生成新图。与无图 Generations 语义不同。

1. 先用 `reference_1` 一张图、`image_complexity=auto`、`n=1` 验证 Images Edit。
2. 图片模型为 `gpt-image-2.6-flare` 或 `gpt-image-2.6-sunburst` 时，确认代理 v8.0.57+ 源码能识别，并确认**你的账号确实有权限**；不行先退回本机已通过的 `gpt-image-2`。
3. 如果手动切换了 `reference_mode=responses`，才需要设置 `responses_model` 并检查 `POST /v1/responses`。之前默认 `gpt-5.4-mini` 返回 `model_not_found`，所以新 Provider 不再强制填它。
4. 如代理返回 `lookup chatgpt.com: no such host`，应先排查 CLIProxyAPI 自身 DNS / 上游代理配置；这是网络故障，不是图片模型错误。

### C：图片编辑

期待：

```text
POST /v1/images/edits
multipart/form-data
image[] = image-1-base.png
image[] = image-2-reference.png ...
```

最小化排障：只连基础图（Image 1）、不接任何参考图、不接 Mask、`n=1`，先确认可用。之后依次添加参考图、Mask 和高级输出参数。如果基础 Edit 成功而 Mask 失败，优先确认代理和模型是否支持 Mask。

## 5. 额度、超时与重复执行风险

CLIProxyAPI 专用 Provider：

- `n=1` 为一次上游生成/编辑调用；
- `n=4` 为**四次**独立请求，不是只扣一次；
- 失败后不擅自跨协议重试可能创建付费图片的 POST；
- 但**已提交并被上游接受的请求可能仍在执行**，本地超时不代表成功取消。

如果在第二张之后发生故障，不要直接把 `n=4` 整轮重试。先看 CLIProxyAPI 的请求日志和已产生的输出。

## 6. 安全地收集故障证据

建议报告最小信息：

```text
插件 commit SHA：
ComfyUI commit / version：
CLIProxyAPI release / commit：
系统与安装方式：Ubuntu / Docker / Windows 等
Provider 类型：CLIProxyAPI / API / OAuth
操作类型：Generate plain / Generate references / Edit
image_model 与 responses_model（若不敏感）：
n、size、quality、output_format：
端点路径（不含私人域名/查询参数）：
HTTP 状态 / request ID / 脱敏后的错误码：
是否经过真实 Codex OAuth 账户：
是否复现（避免用大量真实生图去反复验证）：
```

绝对不要上传完整 `auth.json`、`config.yaml`（若含 Key）、浏览器 Cookie、Bearer Header、含个人图片的 Base64、未清密钥的工作流 JSON 或带敏感参数的原始日志。具体见 [安全与凭据](security.md)。

## 7. 恢复顺序

推荐由最便宜、最可定位的检查逐步升级：

1. Git 分支/插件注册；
2. 纯节点、前端控件与 `/prompt`；
3. 本机代理 TCP/HTTP 鉴权；
4. `/v1/models`（仍不调用生图）；
5. 真实账号 **`n=1` 的最简纯文生成**；
6. 单张基础图 Edit；
7. Generate 单张参考图；
8. 多图、Mask、高级选项、多次请求及长期可靠性。

这有助于把前端问题、插件代码缺陷和远端服务问题区分开，而不是靠不断重试碰运气。
