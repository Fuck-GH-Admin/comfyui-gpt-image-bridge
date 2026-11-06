# Main 0.7.0 全功能验收（2026-11-06）

基线为合并 PR #1/#2/#3 后的 `main@2340796`。三个旧分支 `docs/local-acceptance-20261106`、`feat/cliproxyapi-native-provider`、`feat/image26-images-first-reference-mode` 均确认已合并并删除。

本轮为每个公开功能建立了验证条目，**不等于全部远端功能通过**。真实 2.6 Flare/Sunburst 和 Images 参考图已能生成图片；当前服务链路未兑现自定义/2K/4K 尺寸与 JPEG/WebP，透明输出也有节点层 Alpha 丢失问题。Responses 的网络和当前图片模型的 Chat Completions 限制仍存在。

## 环境和证据

- Ubuntu x86-64，Python 3.12.16，ComfyUI 0.44.0 / `6b203164`，CPU PyTorch 2.15.0+cpu。
- CLIProxyAPI 官方 Linux amd64 8.0.57 / `c2f402b4`，Codex OAuth 已登录；两个服务均在本机回环地址。
- 图片使用合成几何素材；没有上传用户复刻项目的图片。真实请求逐项排队，不自动重试。
- [完整脱敏证据 JSON](evidence/main-acceptance-2026-11-06.json)包含队列 ID、耗时、请求报告、原 PNG 的尺寸/格式/模式/哈希、浏览器结果和本机 HTTP 协议记录，不含客户端 Key、OAuth 文件或账号标识。
- 原基线：Python 235 PASS、JS 13 PASS。补测/修复后：**Python 291 PASS + 1 XFAIL；JS 14 PASS**。XFAIL 是明确记录的透明输出缺陷，不能算作通过。
- 单元测试覆盖：语句约 86.5%，分支约 77.1%，综合约 83.7%。图像编解码约 97%，短期凭据管理 100%。真实 HTTP/浏览器测试不计入该覆盖率，也未声称所有代码路径覆盖。

## 功能矩阵

| 功能 | 本轮验证 | 结论 |
| --- | --- | --- |
| 六个节点注册、类型与工作流队列 | 原集成脚本 + 真实服务 + 浏览器 | PASS |
| CLIProxyAPI Provider 新默认模型/空 Responses 模型/模式/复杂度 | 浏览器、配置单测、真实生成 | PASS；默认参考图无需文本主模型 |
| API Provider Images | 真实 CLIProxyAPI + 本机 HTTP 替身 | PASS |
| API Provider Responses JSON / SSE | 真实 ComfyUI + 本机 HTTP 替身 | PASS；真实 Responses 见阻塞项 |
| API Provider Chat Completions 图片响应 | 本机兼容服务返回 image_url data URI | PASS；真实 CLIProxyAPI 该图片模型拒绝此端点 |
| 自定义同步端点和开关 | 本机 HTTP 自定义路径 + 配置/同源检查单测 | PASS |
| 异步默认任务提交/查询 | 本机 HTTP 返回任务 ID 后完成 | PASS，一次 POST 后 GET 查询 |
| 自定义异步端点/JSON Pointer 映射/修订提示词 | 本机 HTTP 自定义提交及查询路径 | PASS |
| 异步不支持时安全同步回退 | 真实 CLIProxyAPI 404 后同步结果 | PASS；不把它误记为真实异步任务支持 |
| 异步终态失败、30 秒超时、用户取消 | 本机 HTTP 替身 + 实际 ComfyUI `/interrupt` | PASS（预期失败），无重新 POST |
| 401 / 429 / 异常成功响应 | 本机 HTTP | PASS（预期失败），每个任务只 POST 一次 |
| 图片结果 Base64 / URL、MIME、重定向与私网地址检查 | 现有单测 + 本机 HTTP 私网 URL 拒绝 | PASS；允许的公网 URL 下载未额外访问真实外部站点 |
| 原生 Codex OAuth Provider | 配置、JSON/SSE 协议、临时目录凭据读取/刷新/CAS/进程锁单测 | Mock PASS；未调用用户标准 Codex auth 文件做新真实请求 |
| 真正 CLIProxyAPI OAuth | 既有设备登录 + 本轮真实生成 | PASS；不能代替上一行旧直连 Provider 的真实兼容性验证 |
| 单图 Generate / Edit / Images 参考图生成 | 真实 2.6 服务 | PASS，蒙版编辑可见目标形状变更；未保证蒙版外逐像素不变 |
| Generate 16 图 / Edit 基础图+15参考图 | 各一次真实请求 + 单测角色/排序 + 浏览器插口扩展 | PASS：编码/受理数量正确；不声称复杂人物身份的一致性已验收 |
| n=1/2/8 与非法 0/9 | 真实 n=2、单测 n=1/2/8、0/9 不发请求 | PASS；CLIProxyAPI 每张独立请求 |
| 所有质量档位、背景、输出格式、moderation | 配对参数的 JSON/multipart 请求体回归测试 | PASS：转发正确；高质量/复杂度实际效果不以 HTTP 200 为证明 |
| Custom 范围/步长/比例/像素数，常规/2K/4K 预设 | 单测 + 真实 Custom、2K、4K | 本地解析 PASS，当前服务返回尺寸不符合要求（见下表） |
| 不同图片格式/尺寸/通道/无效字节/解码限额 | 新增图像边界单测 | PASS，透明输出另列 XFAIL |
| 空/无效/重放/过期句柄，容量和长度限额 | 单测模拟时钟/容量 + 上轮真实队列边界 + 本轮 HTTP 请求体边界 | PASS；没有实际等待十分钟来测试 TTL |
| 凭据端点非法 JSON/非对象/空/过长/超大请求体 | 真实 ComfyUI HTTP | PASS，400/413，Cache-Control no-store |
| 明文 Key 排队守卫、历史与 PNG 脱敏 | 原集成 + 本机 HTTP + 真实成功结果 | PASS |
| 密码保存/取消、旧控件迁移、重新加载、参考插口扩展/删除与顺序 | 实际浏览器图对象/DOM 操作，非秘密占位值 | 修复后 17/17 PASS |

原集成脚本在实际 ComfyUI 中再次返回 `COMFYUI_SMOKE_PASS`，校验五次模拟服务请求。扩展的本机 HTTP 矩阵为 **19/19**，另加非法 JSON 与超长 Key 两项 **2/2**。所有模拟图片明确为 32×24 固定测试图，不能当作实际生图证据。

## 真实服务逐项结果

共 16 次工作流：14 次队列执行成功、2 次错误。成功执行并不表示所有参数达标。

| 用例 | 请求要点 | 实际结果 |
| --- | --- | --- |
| Flare 默认生成 | gpt-image-2.6-flare，auto | PNG 1536×1024 |
| Sunburst 默认生成 | gpt-image-2.6-sunburst，auto | PNG 1536×1024 |
| 新默认参考图模式 | 两张不同尺寸参考图，images_edit，空文本模型 | PNG 1536×1024 |
| Edit + Mask | Sunburst，complexity high，局部变更形状 | PNG 1254×1254，目标形状变更 |
| Custom + JPEG + xhigh | 1024×768，JPEG，complexity low | **PNG 1536×1024，尺寸/格式未达标** |
| Custom + WebP + max | 1024×1024，WebP，complexity medium | **PNG 1536×1024，尺寸/格式未达标** |
| 透明 PNG | transparent background | **保存为 RGB，无 Alpha；未达标** |
| 2K + n=2 | 2048×1152，两个独立请求 | 两张 PNG，但都为 **1536×1024** |
| 4K 预设 | Sunburst，3840×2160 | **PNG 1536×1024，不是 4K** |
| Generate 16 参考图 | 连续 reference_1–16 | PNG 1536×1024，输入报告 16 图 |
| Edit 基础图+15参考图 | Image 1 身份保留，15 独立参考图 | PNG 1254×1254，输入报告共 16 图 |
| 手动 Responses 参考图 | gpt-6.1-sol + 2.6 Flare | **500，代理解析 chatgpt.com 失败**，一次尝试 |
| 通用 API Images | Images 同步路径 | PNG 1536×1024 |
| 通用 API Chat Completions | 2.6 Flare | **503，代理明确限制该型号只能用 Images Generate/Edit** |
| 通用 API 异步开关 | 默认 async 路由后安全回退 | 返回 PNG；报告记录同步回退 |
| moderation 修复后回归 | 真实提交 low，quality low | HTTP 200，PNG；只证明字段传输兼容，不代表已比较内容审核政策差异 |

尺寸和格式不符已由节点解码前的 `request_report.output.images` 证实，**并非仅仅 SaveImage 把 JPEG 又保存成 PNG**。JSON/multipart 请求体回归测试确认客户端发送了要求的 size/output_format；当前还不能将责任精确归于代理或上游，因此记录为“真实服务链路未兑现”。即使上游日后按要求返回 JPEG/WebP，ComfyUI 的标准 SaveImage 仍会保存 PNG，这是张量输出与文件编码的另一层语义。

## 本轮发现及处理

### 1. 已修复：新版 Provider 重新载入参数错位

新版 CLIProxyAPI Provider 有六个控件，原通用迁移逻辑把它误认为旧 API Provider 的六控件布局，将参考图模式/复杂度当成自定义端点迁移。实际浏览器重新配置检查失败（16/17）。现在仅跳过 CLIProxyAPI Provider 的这套旧 API 布局迁移；保留 API Provider 的原有迁移。新增 JS 回归测试，真实浏览器复测 17/17。

### 2. 已修复：Images 路径漏传 moderation

界面参数能传到 execute_operation，但 Images Generate JSON 和 Edit multipart 未携带该字段。新增端到端请求体测试先得到六项失败，修复后对两种 moderation、全部六个质量档位、三种文件格式/背景组合及生成/编辑/参考生成验证通过。原生旧 OAuth 的非标准路径未新增不受支持字段。

### 3. 未修复：透明图片在 IMAGE 边界丢失 Alpha

`image_bytes_to_tensor` 强制 RGB，独立 RGBA 测试可以确定性复现。回归测试以 strict XFAIL 留存，真实透明请求的保存结果也是 RGB。本轮没有擅自改变既有三输出接口或新增 MASK 输出；需要明确 Alpha/MASK 输出契约后处理。

### 4. 外部链路问题仍未解决

自定义/2K/4K 尺寸、JPEG/WebP 返回不符；Responses DNS 失败；CLIProxyAPI 的图片型号不支持 Chat Completions。这些不能靠前端控件存在就标成通过，也没有通过重试或修改全局 DNS 掩盖。

## 复现

在插件目录，用 ComfyUI 所用 Python 执行：

```bash
python -m pytest -q
node --experimental-default-type=module --test tests/js/*.test.mjs
python tests/integration/comfyui_server_smoke.py /abs/path/to/ComfyUI
```

需要本人真实额度和已运行代理时，单项执行可复用矩阵工具；必须明确选择 case，不会自动跑全量或重试。工具只读取显式传入的私有配置，不把凭据写入记录。

```bash
python tools/real_acceptance_matrix.py \
  --comfy-root /abs/path/to/ComfyUI \
  --proxy-config /private/path/to/cliproxyapi/config.yaml \
  --output-dir /private/path/to/results \
  --case flare_default --case reference_images_default
```

本轮覆盖了公开节点、控件、协议、任务生命周期和凭据保护的功能条目；没有宣称任意供应商、任意型号、长期并发、所有参数笛卡尔组合或全部代码分支都已验证。继续图像复刻时，应使用已通过的 Images 路径，并通过 ComfyUI 原生处理节点明确完成尺寸、图层、蒙版和色彩处理，避免依赖未兑现的远端参数。
