# ComfyUI GPT Image Bridge

在 ComfyUI 中通过 **CLIProxyAPI** 调用 Codex 图片生成与编辑接口，支持纯文生图、参考图生成和已有图片编辑。也保留通用 API Provider 与旧的 Codex OAuth Provider。

> 本 fork 的 **CLIProxyAPI Provider 目前在开发分支 `feat/cliproxyapi-native-provider`**（[PR #1](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/pull/1)），尚未合入 `main` / 发布到 ComfyUI Registry。**不要使用 Registry 安装本 fork 的新功能。**

## 1. 安装插件

关闭 ComfyUI，在其 `custom_nodes` 目录中执行：

```bash
git clone --branch feat/cliproxyapi-native-provider --single-branch \
  https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge.git \
  comfyui-gpt-image-bridge
cd comfyui-gpt-image-bridge

# 使用启动 ComfyUI 所用的同一 Python 环境
python -m pip install -r requirements.txt
```

重启 ComfyUI。节点在 **GPT Image Bridge** 分类下。已有同名插件请先备份并避免同时装两个副本。

## 2. 配置并启动 CLIProxyAPI

从 [CLIProxyAPI Releases](https://github.com/router-for-me/CLIProxyAPI/releases) 获取适合系统的 v8 版本。在独立的 `config.yaml` 中配置客户端 Key 和本机监听，例如：

```yaml
config-version: 8
server:
  host: "127.0.0.1"
  port: 8317
access:
  api-keys:
    - "REPLACE_WITH_YOUR_RANDOM_LOCAL_CLIENT_KEY"
oauth:
  auth-dir: "~/.cli-proxy-api"
multimedia:
  disable-image-generation: false
```

**必须替换示例 Key**。按 CLIProxyAPI 文档完成 Codex OAuth 登录；其可执行文件支持如下参数（请换成实际程序路径）：

```bash
/path/to/CLIProxyAPI -config /path/to/config.yaml -codex-login
/path/to/CLIProxyAPI -config /path/to/config.yaml
```

第二条命令启动服务，生图时应保持运行。Codex OAuth Token 留在 CLIProxyAPI；**ComfyUI 只填写配置中 `access.api-keys` 的客户端 Key**。

详细步骤、Ubuntu/CPU/ROCm、Docker 网络与版本说明：[安装与登录](docs/setup-cli-proxy-api.md)。

## 3. 在 ComfyUI 中使用

添加并连接：

```text
GPT Image Bridge · CLIProxyAPI Provider
                  │ provider
                  ▼
GPT Image Bridge · Generate
                  │ image
                  ▼
Save Image
```

也可以直接[下载无密钥的 ComfyUI 文生图示例工作流](example_workflows/CLIProxyAPI-Text-to-Image.json)，拖入画布后填写客户端 Key。

Provider：

| 输入 | 初始值 |
| --- | --- |
| `api_key` | CLIProxyAPI `access.api-keys` 里的客户端 Key |
| `base_url` | `http://127.0.0.1:8317/v1` |
| `image_model` | `gpt-image-2` |
| `responses_model` | `gpt-5.4-mini`（参考图生成时使用） |

第一次用 Generate：设置一句提示词，`n=1`，其余先保持 `auto`、`output_format=png`，点击 Queue。

- **参考图生成**：`Load Image.IMAGE` → `Generate.reference_1`，依次可连更多参考图。
- **编辑图片**：`Load Image.IMAGE` → `Edit.base_image（Image 1）`；可选将更多参考图接到 `Edit Reference List`，再接 Edit 的参考图入口。
- **保存图片**：Generate 或 Edit 的 `image` → ComfyUI 原生 `Save Image`。

有参考图的 Generate 走 Responses；纯文生图和 Edit 使用 Images API。`n>1` 会发出多次独立请求，可能分别消耗额度。模型名是可调默认值，实际是否可用以你的 CLIProxyAPI 和 Codex 账号为准。

## 文档与问题排查

- [文档目录](docs/README.md)
- [CLIProxyAPI 安装、登录及本机连接](docs/setup-cli-proxy-api.md)
- [节点参数、Generate/Edit 与参考图工作流](docs/nodes-and-workflows.md)
- [故障排查](docs/troubleshooting.md)
- [凭据保护与分享工作流](docs/security.md)
- [协议与代码实现](docs/protocol-reference.md)
- [通用 API Provider 与异步任务](docs/compatibility-and-async.md)
- [测试证据与本机验收清单](docs/testing.md)

**安全提醒**：画布上的 Key 是掩码，但本地保存的工作流 JSON 中仍可能包含客户端 Key。分享前清空 Key。初次使用建议 CLIProxyAPI 只监听本机地址。

[LICENSE](LICENSE) · [上游插件](https://github.com/Liu-Bot24/comfyui-gpt-image-bridge) · [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
