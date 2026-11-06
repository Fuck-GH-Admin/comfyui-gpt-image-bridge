# CLIProxyAPI 安装、Codex 登录与 ComfyUI 本机接入

本文对应本 fork 的专用 `GPT Image Bridge · CLIProxyAPI Provider`。它将真实的图片请求交给一个独立运行的 **CLIProxyAPI v8** 服务。ComfyUI 插件不是 CLIProxyAPI 的安装器，也不会替它执行登录。

## 0. 先判断当前进度

**可以本机验收**：插件已经在一套真实 ComfyUI CPU 环境中启动、注册并执行图像工作流，详见 [测试与验收](testing.md)。

**仍需你本人验证**：本机 CLIProxyAPI 二进制是否能启动、Codex OAuth 是否登录成功、实际账号是否能生成图片、使用哪些模型，以及真实生成结果是否满足预期。

当前 fork 代码在 `feat/cliproxyapi-native-provider`，没有合并到 `main`；从 Registry 安装原作者版本没有此 Provider。不要同时安装同一个包的两个副本，否则可能出现节点 ID 重复。

## 1. 环境要求

- 一套能运行的 ComfyUI；插件使用其 Python 环境，无须本地部署生图模型。
- 用于客户端的 Python 依赖：`numpy>=1.24`、`Pillow>=10.0`；运行 ComfyUI 所需的 PyTorch 由 ComfyUI 安装。
- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 的 **v8 版**可执行文件、配置文件，以及可以交互登录 Codex 的浏览器/设备。
- ChatGPT/Codex 账号有资格使用对应生图能力。**订阅额度不是 OpenAI 公共 API 额度**；插件不保证任意账号、任意模型都能生图。
- ComfyUI 和 CLIProxyAPI 应能通过 HTTP 连接。初次测试建议都运行在同一台电脑上。

### 选择 CPU 还是 ROCm？

本插件主要执行字符串处理、HTTP 请求及返回图片的解码，不在本地运行 GPT 图片生成模型。本地 ComfyUI 可用 CPU 模式（例如 `python main.py --cpu`），因此这条工作流**不要求 AMD ROCm 才能调用云端生图**。其他 ComfyUI 工作流中的本地推理、放大或模型采样节点仍可能需要 ROCm/GPU。

## 2. 安装本 fork 的 ComfyUI 插件

**Ubuntu / Linux，务必检出开发分支**：

```bash
cd /path/to/ComfyUI/custom_nodes

git clone --branch feat/cliproxyapi-native-provider --single-branch \
  https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge.git \
  comfyui-gpt-image-bridge

cd comfyui-gpt-image-bridge
# 这里要调用启动 ComfyUI 使用的同一个 Python；若已激活其 venv：
python -m pip install -r requirements.txt
```

如果 `custom_nodes/comfyui-gpt-image-bridge` 已存在，**不要再嵌套 clone**；先检查旧插件的仓库和未提交修改，选择备份后替换或在 Git 仓库中切换分支。完成后**完全重启** ComfyUI 后端，不只是刷新网页。

Windows、Docker、便携版的目录和 Python 可执行文件可能不同；原则不变：将插件目录放进实际运行实例的 `custom_nodes`，并由该实例的 Python 安装依赖。已安装相同包的 Registry 版本时，先禁用或移除重复副本。

检查 ComfyUI 节点搜索：`GPT Image Bridge · CLIProxyAPI Provider`、`GPT Image Bridge · Generate`、`GPT Image Bridge · Edit`。不存在时先看 [故障排查](troubleshooting.md)。

## 3. 安装 CLIProxyAPI

打开 [CLIProxyAPI Releases](https://github.com/router-for-me/CLIProxyAPI/releases)，下载与你的系统及 CPU 架构匹配的官方发布包。以普通 Linux x86-64 为例，选择名称带 `linux_amd64` 的包。不同发行版/压缩包的可执行文件名可能不同；以下以 `/path/to/CLIProxyAPI` 表示你解压后的可执行程序。

也可以从源码构建，但注意 CLIProxyAPI 的 Go 版本和依赖以其当前 `go.mod` 为准，不要默认发行版自带的旧 Go 能构建。

建议使用**独立目录**保管 CLIProxyAPI 配置、OAuth 文件和日志，不要把登录凭据或 `config.yaml` 提交进本插件 Git 仓库。

### 配置示例（v8 格式）

以 [CLIProxyAPI 官方 config.example.yaml](https://github.com/router-for-me/CLIProxyAPI/blob/main/config.example.yaml) 为准。下面是方便初次本机试用的最小化示意，**必须把客户端密钥替换为自己生成的随机值**：

```yaml
config-version: 8

server:
  host: "127.0.0.1"
  port: 8317

access:
  api-keys:
    - "replace-with-a-unique-strong-local-client-key"

oauth:
  auth-dir: "~/.cli-proxy-api"

multimedia:
  disable-image-generation: false
```

`access.api-keys` 是 **ComfyUI → CLIProxyAPI 的客户端访问密钥**，不是 OpenAI API Key，也不是 Codex OAuth 的 Access Token。CLIProxyAPI 负责持有、刷新和使用 Codex OAuth 账户授权。

`multimedia.disable-image-generation` 支持如下模式（具体以对应版本源码为准）：

| 值 | 对图片节点的影响 |
| --- | --- |
| `false` | 允许 Images API 和非 Images 的 image_generation 路径；建议初次验收使用 |
| `true` | 禁止全部图片生成，包括 `/v1/images/*` |
| `"chat"` | 禁止非 Images 请求注入图片工具；纯文生图与 Images Edit 仍可用，但参考图 Generate 的 Responses 路径可能受影响 |
| `"passthrough"` | 不在非 Images 请求自动注入/剥离图片工具；具体依赖客户端原始请求和服务端兼容性 |

如果你已有完整 `config.yaml`，**只合并必要的字段**，不要用这个最小例子覆盖其他正常配置。

### 登录 Codex

CLIProxyAPI 自身提供 Codex OAuth 交互登录，启动方式依其发布包为准。源码的服务入口提供 `-config`、`-codex-login`、`-codex-device-login` 等参数。示例：

```bash
/path/to/CLIProxyAPI -config /path/to/config.yaml -codex-login
# 或根据你的登录环境使用设备码流程：
# /path/to/CLIProxyAPI -config /path/to/config.yaml -codex-device-login
```

按终端/浏览器提示完成授权，并确认 CLIProxyAPI 的账户列表或输出显示成功。登录失败应在代理侧排查；**不要把 `~/.codex/auth.json` 的内容、OAuth Token 或任何浏览器 Cookie 粘贴到 ComfyUI**。

### 启动服务

```bash
/path/to/CLIProxyAPI -config /path/to/config.yaml
```

另开终端启动 ComfyUI。CLIProxyAPI 服务必须在 ComfyUI 生图时保持运行；只安装、只登录但服务未运行，节点会连接失败。

Docker 用户需要注意：**ComfyUI 容器中的 `127.0.0.1` 是 ComfyUI 容器自身**，不是宿主机，也不是另一个容器。让服务通过可信 Docker 网络名/端口可达，并进行访问控制；不要为了省事把代理管理面板或 OAuth 端口开放到公网。

## 4. 先测试代理是否能被 ComfyUI 访问

在**运行 ComfyUI 的同一个网络环境中**执行：

```bash
# 在本地 shell 中输入 CLIProxyAPI 的客户端 Key，不写进命令文本
read -rsp 'CLIProxyAPI client key: ' CPA_KEY
echo

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer ${CPA_KEY}" \
  http://127.0.0.1:8317/v1/models
```

返回 JSON 的 `data` / 模型条目，说明 HTTP 和客户端鉴权至少已打通。**它不等于图片生成验证**，也不证明某个型号真正可用；代理可能返回别名或合并多个供应商的模型列表。请不要把包含私有服务地址、Key 或 Token 的完整响应发到公开 Issue。

若返回连接拒绝，检查服务启动与监听地址；返回 401 检查 `access.api-keys`；返回模型路由错误或 404，检查代理的登录状态、配置和模型兼容性。

> 如果要用 `curl` 再做真实图像生成请求，可能消耗 Codex/ChatGPT 订阅额度，而且失败时不要盲目自动重试。建议先在 ComfyUI 中执行 `n=1` 的简单工作流。

## 5. 第一次在 ComfyUI 画布上生图

可以直接下载[本 fork 的 CLIProxyAPI 纯文生图工作流](../example_workflows/CLIProxyAPI-Text-to-Image.json)，拖入 ComfyUI 画布后填写客户端 Key。示例里的 `api_key` 是空字符串，不包含任何 OAuth 凭据。

也可以手动依次添加：

```text
GPT Image Bridge · CLIProxyAPI Provider
                │ provider
                ▼
GPT Image Bridge · Generate
                │ image
                ▼
Save Image
```

Provider 的字段：

| 控件 | 初始值 | 要填什么 |
| --- | --- | --- |
| `api_key` | 空 | 刚才配置的 **CLIProxyAPI 客户端 Key** |
| `base_url` | `http://127.0.0.1:8317/v1` | ComfyUI 能访问的代理地址，含 `/v1` |
| `image_model` | `gpt-image-2` | 当前代理实际提供的图片模型/别名 |
| `responses_model` | `gpt-5.4-mini` | 参考图 Generate 时使用的普通 Responses 主模型；首次纯文生成暂不会用到 |

Generate 初次建议：`prompt` 用一句简短提示词；`size=auto`、`quality=auto`、`background=auto`、`output_format=png`、`moderation=auto`、`n=1`、`timeout_sec=300`。点击 Queue 执行。若模型不支持某个参数，按错误信息逐一调整，不要认定所有 GPT 图片模型具备完全相同选项。

保存结果可在 ComfyUI 输出目录找到。想测试参考图，请把一张 `Load Image` 的 `IMAGE` 连接到 Generate 的 `reference_1`；要编辑已有图片，请改用 `Edit`（基础图为 `base_image（Image 1）`，参考图经 `Edit Reference List`）。完整接线与参数见 [节点及工作流手册](nodes-and-workflows.md)。

## 6. 更新与回退

在插件目录：

```bash
git fetch origin
git switch feat/cliproxyapi-native-provider
git pull --ff-only origin feat/cliproxyapi-native-provider
```

更新后重启 ComfyUI。**不要直接 `git pull` 到主分支**：此 PR 还没有合并，`main` 尚无专用 Provider。

如果需要回滚，保存自己修改的工作流并记录当前版本 SHA 后，通过 Git checkout 指定旧提交恢复；同时保持 CLIProxyAPI 版本与所需模型路径一致。升级代理后如突然失败，应先检查代理的 Changes、`config.example.yaml` 和 [故障排查](troubleshooting.md)。

## 7. 安全提醒

- 请让 `server.host` 在初次验收时保持 `127.0.0.1`，不应无认证暴露公网。
- 本地保存的 ComfyUI 工作流 JSON 中，**API Key 仍可能以明文保存**；密码控件只遮挡画布显示。分享前必须清空。
- CLIProxyAPI Provider 不读取 Codex 登录文件；但 CLIProxyAPI 自身会在指定的 `oauth.auth-dir` 保存凭据，应限制文件权限并注意备份安全。
- 不要把客户端 Key 和真实账号 OAuth Token 混用；也不要把后者输入插件的 `api_key`。
- Codex 图像服务属于供应商的演进中的接口，实际可用性和使用权限以服务端为准。

继续阅读：[安全与凭据](security.md) · [故障排查](troubleshooting.md) · [测试与验收](testing.md)。
