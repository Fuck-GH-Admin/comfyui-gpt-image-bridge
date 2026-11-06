# ComfyUI GPT Image Bridge

在 ComfyUI 中通过 **CLIProxyAPI 或 OpenAI 兼容第三方中转站** 调用图片生成与编辑接口，支持纯文生图、参考图生成和已有图片编辑。也保留通用 API Provider 与旧的 Codex OAuth Provider。

> 本 fork 包含 **Provider Profile、CLIProxyAPI 支持、第三方 OpenAI 兼容接口、GPT Image 2.6 和参考图模式**。ComfyUI Registry 若仍指向上游原作者发布版本，则不包含本 fork 的新功能；请从此仓库安装。

## 1. 安装插件

关闭 ComfyUI，在其 `custom_nodes` 目录中执行：

```bash
git clone --branch main --single-branch \
  https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge.git \
  comfyui-gpt-image-bridge
cd comfyui-gpt-image-bridge

# 使用启动 ComfyUI 所用的同一 Python 环境
python -m pip install -r requirements.txt
```

重启 ComfyUI。节点在 **GPT Image Bridge** 分类下。已有同名插件请先备份并避免同时装两个副本。

## 2. 配置服务商（推荐，不在画布中保存 Key）

从 [服务商配置示例](providers.example.json) 复制一份本机 `providers.local.json`，填写 CLIProxyAPI 或第三方 OpenAI 兼容中转站的 `base_url`、`api_key` 和图像模型，Linux/macOS 执行 `chmod 600 providers.local.json`。画布使用 **GPT Image Bridge · Provider Profile**，只需要选择服务商名称，必要时覆盖图像模型。配置不会随该节点的工作流 JSON 导出。

完整说明与第三方服务支持边界见 [服务商配置手册](docs/provider-profiles.md)。旧 API、CLIProxyAPI、Codex OAuth Provider 保留注册供旧工作流使用，但已在默认新建菜单中隐藏并弃用。

## 3. 配置并启动 CLIProxyAPI（本地 Codex 方案）

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

第二条命令启动服务，生图时应保持运行。Codex OAuth Token 留在 CLIProxyAPI；**将 CLIProxyAPI `access.api-keys` 的客户端 Key 填入本机 `providers.local.json` 的相应 profile**。

详细步骤、Ubuntu/CPU/ROCm、Docker 网络与版本说明：[安装与登录](docs/setup-cli-proxy-api.md)。

## 4. 在 ComfyUI 中使用

推荐添加并连接（Profile 节点）：

```text
GPT Image Bridge · Provider Profile
                  │ provider
                  ▼
GPT Image Bridge · Generate
                  │ image
                  ▼
Save Image
```

也可以直接[下载无密钥的 ComfyUI 文生图示例工作流](example_workflows/CLIProxyAPI-Text-to-Image.json)，拖入画布后选择已经在本机配置好的服务商。

Provider Profile 不含 Key 和 `base_url`。`profile` 选择服务商，`image_model` 留空时使用配置的默认模型，`reference_mode` 默认跟随服务商配置。第一次用 Generate：填写提示词、`n=1`，其他项保持 `auto`、`output_format=png`，然后点击 Queue。旧版 Provider 参数已转移到[旧工作流手册](docs/nodes-and-workflows.md)。

- **参考图生成**：`Load Image.IMAGE` → `Generate.reference_1`，依次可连更多参考图。
- **编辑图片**：`Load Image.IMAGE` → `Edit.base_image（Image 1）`；可选将更多参考图接到 `Edit Reference List`，再接 Edit 的参考图入口。
- **保存图片**：Generate 或 Edit 的 `image` → 本插件 `GPT Image Bridge · Save Image`，可选择 PNG/JPEG/WebP；也可以继续使用 ComfyUI 原生 `Save Image`。

**推荐本地 Codex 配置默认走 Images API**：纯文本生成用 `/images/generations`，有参考图的 Generate 使用 `/images/edits` 作参考图引导生成（不是严格意义的从零生图），Edit 同样使用 `/images/edits`。需要多轮文本模型协调时，手动将 `reference_mode` 改成 `responses` 并填写可用的 `responses_model`。`n>1` 会发出多次独立请求，可能分别消耗额度。

**OpenAI 已正式发布 GPT Image 2.6 Flare / Sunburst**；本仓库的 [Main 0.7.0 实机报告](docs/main-acceptance-2026-11-06.md)已在一套真实账户上验证两者生成和默认参考图链路。插件侧 RGBA 保留已修复，修复后的一次真实透明背景复测已保存 RGBA（不保证所有请求）；自定义尺寸和 JPEG/WebP 上游响应也仍有未达标记录。参见[模型兼容与版本边界](docs/model-support.md)。

### 高级画质与参考图

新的 Generate / Edit 支持 2.6 的 `xhigh`、`max` 画质档、2K/4K 尺寸预设和 `size=Custom` 自定义宽高（16 的倍数、大小与比例有校验）；最多可为 Generate 连接 16 张参考图、Edit 使用 1 张基础图加 15 张参考图。旧模型可能不接受某些选项，请先用 `auto` 测试。

本地文件编码与透明通道处理见[本地图片导出](docs/local-image-export.md)。完整参数与限制见[节点手册](docs/nodes-and-workflows.md)；[官方节点对照](docs/official-node-comparison.md)解释哪些高级能力是故意保留或未实现的。

## 文档与问题排查

- [文档目录](docs/README.md)
- [本机服务商配置与第三方中转站](docs/provider-profiles.md)
- [官方 ComfyUI 云端生图节点能力对照](docs/official-node-comparison.md)
- [OpenAI 官方 GPT Image 模型、2.6 能力与代理兼容](docs/model-support.md)
- [CLIProxyAPI 安装、登录及本机连接](docs/setup-cli-proxy-api.md)
- [节点参数、Generate/Edit 与参考图工作流](docs/nodes-and-workflows.md)
- [本地 PNG/JPEG/WebP 保存与 Alpha 处理](docs/local-image-export.md)
- [故障排查](docs/troubleshooting.md)
- [凭据保护与分享工作流](docs/security.md)
- [协议与代码实现](docs/protocol-reference.md)
- [通用 API Provider 与异步任务](docs/compatibility-and-async.md)
- [测试证据与本机验收清单](docs/testing.md)
- [Main 0.7.0 全功能实机验收报告](docs/main-acceptance-2026-11-06.md)

**安全提醒**：新的 Provider Profile 不在画布/工作流中保存 Key；`providers.local.json` 是机密文件，不要分享。旧 Provider 工作流可能含 Key，分享前必须清除。CLIProxyAPI 首次使用请仅监听本机地址。

[LICENSE](LICENSE) · [上游插件](https://github.com/Liu-Bot24/comfyui-gpt-image-bridge) · [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
