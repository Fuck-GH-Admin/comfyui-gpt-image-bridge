# 测试、验收标准与实际证据

本项目严格区分**源码核对**、**单元测试**、**真实 ComfyUI 后端测试**、**CLIProxyAPI 实际进程测试**和**Codex 上游真实图片生成**。前面的测试通过不能代替后面的验收。

**真实账号实机证据**：[2026-11-06 本地验收报告](local-acceptance-2026-11-06.md)和[脱敏证据 JSON](evidence/local-acceptance-2026-11-06.json)。旧型号 `gpt-image-2` 的纯文 Generate、基础 Edit、带参考图 Edit 和浏览器控件已通过；当时 Responses 参考图 Generate 失败，不能记为 PASS。**新版 2.6 两个型号及默认 Images Edit 参考图生成尚未通过真实账户验收。**

## 1. 当前验收矩阵（2026-11-06）

| 层次 | 验证方法 | 当前结论 |
| --- | --- | --- |
| 源码与协议 | 代码审查 | 已有 CLIProxyAPI Provider、Images/Responses 适配和凭据守卫 |
| Python 单元测试 | GitHub Actions pytest | **235 PASS（当前新版分支测试记录）** |
| JavaScript 单元测试 | Node.js Test Runner | **13 PASS（当前新版分支测试记录）** |
| 实际 ComfyUI 后端 | Ubuntu + CPU，真正安装 ComfyUI 0.44.0 | **PASS** |
| ComfyUI 节点注册与任务执行 | HTTP `/object_info`、`/prompt`、`/history` | **PASS** |
| 生成/参考图/编辑请求 | 本机假 CLIProxyAPI HTTP 服务器 | **PASS（协议替身）** |
| Save Image 文件 | 检查真正写出的五张 32×24 PNG 及元数据 | **PASS** |
| CLIProxyAPI 真实进程 | 当前 CI 未启动此进程 | **NOT_RUN** |
| 真实 Codex OAuth、账户额度 | CI 不导入个人凭据 | **CI NOT_RUN；已有 PR #2 的用户实机登录证据** |
| 上游真实生图、编辑 | 用户 PR #2 验证旧模型 `gpt-image-2` 的纯文 Generate 和 Edit；**2.6 两个变体未验证** | **旧模型实机 PASS；2.6 NOT_RUN** |
| 浏览器中的密码控件人工点击 | CI 只运行后端与前端逻辑单元测试 | **NOT_RUN** |
| Windows、macOS、Docker 长期运行 | Linux CI 无法覆盖 | **NOT_RUN** |

**证据链接**：[新版 Python + JavaScript CI](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42208174584)；[新版真实 ComfyUI 运行 CI](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42208174647)。

真实 ComfyUI 固定基线：`Comfy-Org/ComfyUI@63e5bf594339f676b4b15e072529873e3448409e`，运行报告版本 `0.44.0`，Ubuntu Runner、Python 3.11、CPU PyTorch，不需要 GPU 也没有本地模型权重。

## 2. 自动化测试如何运行

仓库包含两套 GitHub Actions：

- [tests.yml](../.github/workflows/tests.yml)：Python 协议、配置、OAuth 模拟、图片边界、凭据保护、前端兼容等单元测试。
- [comfyui-integration.yml](../.github/workflows/comfyui-integration.yml)：真实 ComfyUI 引擎、真实 HTTP/队列执行和本机模拟图片 HTTP 服务。

单元测试可以在**隔离 Python 环境**中执行：

```bash
python -m pip install -r requirements.txt pytest
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pytest -q

node --experimental-default-type=module --test tests/js/*.test.mjs
```

**不要为了跑测试而直接覆盖本地已有 ROCm 环境的 PyTorch**。如果本机 ComfyUI 已有可用的 GPU 版 PyTorch，可使用那份 Python；或者创建单独 venv。CI 的 CPU wheel 仅用于独立 Runner。

## 3. 真实 ComfyUI 集成测试具体做了什么

[集成脚本](../tests/integration/comfyui_server_smoke.py)会：

1. 检出真实 ComfyUI 指定 SHA，安装其真实运行依赖，启动 ComfyUI 后端。
2. 将本 fork 作为自定义节点安装，核对六个节点在 `/object_info` 中注册。
3. 启动**内存中的 CLIProxyAPI 兼容 HTTP 测试服务器**，它返回可解码的固定 PNG 和模拟 Responses SSE。
4. 使用 `POST /gpt-image-bridge/session-credential` 将测试 Key 转成一次性句柄；检查原始 Key 不能越过 `/prompt` 守卫。
5. 提交 `Generate n=2` 工作流，通过 Images 请求保存两张 PNG。
6. 提交 Load Image → 参考图 Generate → Save Image 工作流，分别以默认 Images Edit 和手动 Responses 两种模式请求并保存 PNG。
7. 另行提交可选 Responses 模式的参考图 Generate 工作流，验证文本主模型与图片模型分离；再提交 Load Image → Edit Reference List → Edit → Save Image 工作流，验证 multipart 中基础图和参考图顺序。
8. 检查五次 HTTP 请求的端点、模型角色、Bearer 客户端 Key 和关键字段。
9. 检查输出目录里有真正的 PNG 文件，能读取、尺寸为 32×24、图片元数据没有测试 Key。
10. 关闭测试进程并输出 `COMFYUI_SMOKE_PASS`。

**注意：用户已通过 [PR #2](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/pull/2) 上传旧型号真实 CLIProxyAPI + Codex 实机报告。该报告确认 `gpt-image-2` 的纯文生成、基础 Edit 和带参考图 Edit，但没有验证 2.6 Flare/Sunburst，也未确认新版默认的参考图 Generate（Images Edit 模式）。请勿将报告覆盖范围扩大。**

**ComfyUI 是真的，图片服务是模拟的。** 因此这种测试能发现节点加载、后端执行、数据类型、工作流保存等错误，却不能证明 CLIProxyAPI 真实 OAuth 登录、上游配额及模型可用。

### 在自己的隔离 ComfyUI 上重现

已经在 `ComfyUI/custom_nodes/comfyui-gpt-image-bridge` 安装插件，且 Python 环境包含完整 ComfyUI 依赖时：

```bash
cd /path/to/ComfyUI/custom_nodes/comfyui-gpt-image-bridge
python tests/integration/comfyui_server_smoke.py /abs/path/to/ComfyUI
```

脚本会启动一套额外的 ComfyUI 后端并使用随机端口；不会调用真实 Codex 账户。

**副作用**：它会在 ComfyUI 的 `input/bridge_reference.png` 写入固定测试素材，在 `output/` 中写入 `CI-Text*`、`CI-Reference*`、`CI-Edit*` PNG，并在系统临时目录写 `comfyui-cliproxy-smoke.log`。生产环境先备份或使用独立测试目录。

### 更新版额外验证

- [ ] `gpt-image-2.6-flare` 的 `n=1` 图片生成：PASS / FAIL / NOT_RUN
- [ ] `gpt-image-2.6-sunburst` 的 `n=1` 图片生成：PASS / FAIL / NOT_RUN
- [ ] 有参考图 Generate 默认 `reference_mode=images_edit`，确认真实代理以 Images Edit 生成新图：PASS / FAIL / NOT_RUN
- [ ] 仅在需要时选 `reference_mode=responses` 并输入实际可用的文本主模型（PR #2 记录过 model_not_found/DNS 问题，不能假设成功）
- [ ] `quality=xhigh/max`、`size=Custom`、`image_complexity=low/medium/high`：按真实账户和模型逐项验证，避免连续消耗额度

## 4. 本机真实生图验收顺序

只有接入你自己的 CLIProxyAPI 服务并完成 Codex 登录，才能把以下真实服务项目标记为 PASS。**无需向维护者分享 Token、Key 或图片。**

### A. 不消耗生图额度的准备检查

- [ ] 本 fork 处于 `main`（确认 Git remote 指向本 fork），且 ComfyUI 节点列表中确实有 CLIProxyAPI Provider。
- [ ] CLIProxyAPI 已运行，`config.yaml` 用 v8 的 `access.api-keys`，当前账号 Codex OAuth 登录成功。
- [ ] `multimedia.disable-image-generation` 为 `false`，以覆盖 Images 和 Responses 两条路线。
- [ ] 在与 ComfyUI 相同的网络环境中，`GET /v1/models` 能返回数据。
- [ ] Provider 里的 Key 是 CLIProxyAPI 客户端 Key，而不是上游 Codex OAuth Token。

### B. 真实纯文本图片生成（可能消耗额度）

- [ ] 用 Provider → Generate → Save Image，`n=1`。
- [ ] 初次设置 `size=auto`、`quality=auto`、`background=auto`、`output_format=png`、`timeout_sec=300`。
- [ ] 只 Queue 一次，记录成功与否、输出是否存在、HTTP 状态及脱敏请求 ID。
- [ ] 若超时或失败，先核对上游是否已经执行；不要立刻多次重新发送。

### C. 编辑和参考图（可能消耗额度）

- [ ] Edit：只连接一张基础图，先不接 Mask/参考图，成功后再追加。
- [ ] Generate 参考图：从 `reference_1` 接一张图片，先验证默认 `images_edit`，必要时才单独切换 `responses` 并验证模型工具权限。
- [ ] Edit + Reference List：再接至少一张独立参考图并检查顺序。
- [ ] 需要时才测试 Mask、多种格式、多参考图、`n>1`、更高并发和失败恢复。

### D. 安全与失败边界

- [ ] 将客户端 Key 清空后应该无法调用真实代理；原始 Key 不应进入队列。
- [ ] CLIProxyAPI 停止后，ComfyUI 应报连接失败而非无限卡住。
- [ ] 失效/过期的短期句柄应失败且提示重新排队。
- [ ] 分享任何工作流前清除客户端 Key 和私有地址。
- [ ] 记录发生 401、403、404、429 或上游 5xx 时是否可能已有一次生成，避免重复收费。

## 5. 本地验收记录模板（无密钥）

```text
Time:
Plugin commit SHA:
ComfyUI version / commit:
CLIProxyAPI version / commit:
OS / Python / ComfyUI deployment:
image_model:
responses_model:
Network topology: same host / Docker / other
Codex OAuth login succeeded? yes/no (NO TOKEN)
Plain generation n=1: PASS / FAIL / NOT_RUN
Edit base image n=1: PASS / FAIL / NOT_RUN
Reference Generate n=1: PASS / FAIL / NOT_RUN
Edit with references n=1: PASS / FAIL / NOT_RUN
Optional multi-output/Mask tests:
Output file count, size and format:
Safe HTTP error code and request ID:
Relevant sanitized logs:
Remaining problems:
```

不要上传 `auth.json`、带凭据的 `config.yaml`、原始 Bearer Header、工作流中尚未删除的 API Key 或包含敏感查询参数的 URL。

## 6. 宣称全部远端功能可用前的验收条件

- 单元 CI 和真实 ComfyUI 后端 CI 通过（**已经有证据**）。
- 本机**真实 CLIProxyAPI 进程**可启动并通过客户端 Key 鉴权。
- 本人账户完成一次真实 `n=1` 纯文生图。
- 最小 Edit、参考图 Generate 取得实证，或明确记录服务端实际不支持的路径。
- 用户侧 UI 的密码控件、分享工作流脱敏流程可用。

**旧型号 `gpt-image-2` 已有真实生图成功证据**；但 2.6 Flare/Sunburst、高画质/自定义尺寸和新默认参考图模式还需要实机验证。不要把 CI 生成的模拟 PNG 冒充新的 Codex 实机结果。
