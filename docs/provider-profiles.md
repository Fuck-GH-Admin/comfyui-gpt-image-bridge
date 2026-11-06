# 服务商配置（CLIProxyAPI 和第三方中转站）

推荐 **GPT Image Bridge · Provider Profile** 节点。画布中不再输入 API Key 和 Base URL；插件后端读取本机 JSON 配置。节点只会把服务商名称、模型和参考图模式写入工作流。

## 1. 创建本机配置

在插件根目录执行：

```bash
cp providers.example.json providers.local.json
chmod 600 providers.local.json
```

编辑 `providers.local.json`：

```json
{
  "profiles": {
    "local_codex": {
      "base_url": "http://127.0.0.1:8317/v1",
      "api_key": "REPLACE_WITH_CLIPROXY_CLIENT_KEY",
      "model": "gpt-image-2.6-flare",
      "api_protocol": "auto",
      "reference_mode": "images_edit",
      "use_async": false
    },
    "third_party": {
      "base_url": "https://your-gateway.example/v1",
      "api_key": "REPLACE_WITH_GATEWAY_KEY",
      "model": "YOUR_ACTUAL_IMAGE_MODEL_ID",
      "api_protocol": "images",
      "reference_mode": "images_edit",
      "use_async": false
    }
  }
}
```

替换示例 Key 和模型名称。CLIProxyAPI 使用配置中的客户端 Key；第三方中转站使用其提供的 API Key。不是 Codex OAuth Token。

服务商配置支持 `api_protocol` = `auto`、`images`、`responses`、`chat_completions`，以及 `reference_mode` = `images_edit` / `responses` / `legacy`。可选高级字段还包括 `use_custom_endpoints`、`generate_endpoint`、`edit_endpoint`、`use_async` 及异步映射。对普通 OpenAI 兼容中转站，建议从 `images`、标准端点、`use_async=false` 开始。

修改配置后刷新 ComfyUI 节点定义以更新下拉框；运行时读取的是本机配置。还可在启动 ComfyUI 前设置 `GPT_IMAGE_BRIDGE_PROVIDERS_FILE` 环境变量指定该 JSON 的本机路径。新的服务商配置文件已加入 `.gitignore`。Linux/macOS 要求权限 0600。

## 2. 节点参数

| 控件 | 默认值 | 用途 |
|---|---|---|
| `profile` | 首个已配置服务商 | 选择服务商 |
| `image_model` | 空 | 可覆盖该服务商默认图像模型 |
| `reference_mode` | `profile` | 跟随配置，或指定 `images_edit` / `responses` |
| `responses_model` | 空 | 可覆盖 Responses 主模型，仅用于 Responses 路径 |

连线：`Provider Profile.provider` → `Generate.provider` 或 `Edit.provider`，后续连普通 ComfyUI 图片处理与保存节点。

## 3. 边界和迁移

只支持相应接口真正兼容 OpenAI 的服务。中转站可能只支持文生图、不支持编辑、MASK、透明图片、高分辨率或原生 JPEG/WebP 输出。初次测试 `n=1`，检查 `request_report.output.conformance`。自定义宽高已经隐含比例，不必另加比例参数。

新的 Provider Profile 不把 API Key 放进工作流 JSON；请仍然保护本机配置文件、ComfyUI 后端和日志。旧 `API Provider`、`CLIProxyAPI Provider` 和 `Codex OAuth Provider` 已标记 DEPRECATED / DEV_ONLY，默认不在新建节点菜单显示，保留注册仅为了旧工作流能继续打开。旧工作流可能含 Key，分享前必须清空。把旧工作流的 provider 连线改接新的 Provider Profile；原生 OAuth 不再作为推荐使用路线。
