# 新会话接手提示词：ComfyUI GPT Image Bridge

你现在接手 ComfyUI GPT Image Bridge 项目。请先完整阅读仓库中的：

- docs/handoff/2026-11-07-context.md
- 本提示词

仓库：Fuck-GH-Admin/comfyui-gpt-image-bridge  
GitHub：https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge

## 你的首要任务

不是重新设计项目，也不是从头开发。你要从 GitHub 当前真实状态接手，核对、审查并整合已有成果，避免重复返工。

### 1. 先重新确认事实

读取最新：
- main HEAD、分支列表、所有 open PR。
- PR #6、#7、#8、#9 的 head/base SHA、patch、commits、mergeability、check-runs。
- 最新 Actions 结果和日志。
- main 的 README、docs/README、docs/testing、节点代码、协议代码。
- 四个开放分支中的对应实现和文档。

不要直接相信交接快照中的 SHA 或状态；它们只代表 2026-11-07 00:32 的 GitHub 快照。若状态变化，以最新 GitHub 数据为准。

### 2. 理解当前项目架构和已经完成的工作

默认推荐链路：
ComfyUI -> CLIProxyAPI v8 -> Codex OAuth -> Images API。
纯文生成走 Images Generate；参考图 Generate 默认 Images Edit；Edit 走 Images Edit；Responses 仅为可选路径。

main 已合入 PR #1–#5，包含 CLIProxyAPI Provider、GPT Image 2.6 Images-first、Provider 重载修复、moderation 请求修复、RGBA/Alpha 解码修复。main 当前六节点。PR #6 才增加第七个本地 Save Image 节点。

不要重复实现已经存在的能力。ComfyUI 和 Codex 上游源码已核对，优先沿用其现有设计。关键边界：
- 插件必须保留上游返回的 RGBA；PR #5 已修复。
- PR #7 有一次真实透明背景生成成功并保存 RGBA 的证据，但只有一个样例，不是普遍保证。
- CLIProxyAPI v8.0.57 不透传 complexity；当前保持 auto。
- 上游请求尺寸/格式不一定兑现，HTTP 200 不等于参数成功。
- 本地文件编码与上游 output_format 是不同层次。
- Responses 当前真实请求曾因 chatgpt.com DNS 失败；Chat Completions 图片路由曾返回 503。默认使用 Images。

### 3. 审查四个开放 PR

**PR #6 — feat/local-image-export-20261106**
新增 GPT Image Bridge · Save Image，支持 PNG/JPEG/WebP，PNG/WebP 保留 Alpha，JPEG 以指定 matte 合成；CI 已有 Python 303 passed、JS 14 passed、真实 ComfyUI CPU 集成验证 WebP/JPEG。重点审查代码、安全、ComfyUI 输出路径、batch 文件命名、异常处理和测试。它是唯一增加第七节点的分支。

**PR #8 — feat/verify-image-output-contract-20261106**
新增图片实际输出尺寸、格式、Alpha 元数据和 request_report.output.conformance。检查它是否对 Images、Responses、Chat、旧 OAuth 等协议正确处理 ignored_options；not_checked 不得误报为 pass；不支持的参数不能产生误导 warning；不要对 prompt_instruction 的 size 做真实尺寸断言。CI 已有 Python 300 passed、JS 14 passed、ComfyUI fake API 集成通过。此 PR 没有真实 Codex 上游验收。

**PR #9 — docs/cliproxyapi-capability-boundaries-20261106**
修正文档与 Provider tooltip：CLIProxyAPI v8.0.57 的 Generate/Edit/multipart allowlist 不含 complexity，故代理会丢弃；SVG/GIF/markup-guided 在当前插件路径未实现。CI 294 Python、14 JS、ComfyUI 集成通过。主要是文档/tooltip 更正，确认与 PR #6 的 nodes.py 修改不冲突。

**PR #7 — docs/live-alpha-retest-20261106**
修订真实透明背景证据：一次 gpt-image-2.6-flare、background=transparent、quality=low、n=1 请求真实返回 RGBA PNG，1536×1024，Alpha extrema 0–254，耗时约 30 秒。证据 JSON 已脱敏。它修正文档，不改运行时代码。CI 294 Python、14 JS、ComfyUI 集成通过。必须保留“仅一次成功，不保证所有请求”的限定。

所有 PR 当前在快照时均以 main@abfacd3 为 base，且 CI 全绿；但必须重新确认。

### 4. 整合策略

建议顺序：
1. PR #6
2. PR #8
3. PR #9
4. PR #7

这些 PR 的文档有交叠，尤其 docs/README.md、docs/testing.md、nodes-and-workflows.md、model-support.md、official-node-comparison.md。逐个合并、解决冲突、核对内容；不要盲目批量合并。每个 PR 合并前重新检查最新 SHA 和 check-runs。合并后跑完整 Python、JavaScript 和真实 ComfyUI CPU + fake API 集成。

若发现缺陷，直接修复并补测试；不需要把问题简单摆给用户等待指示。不要为合并制造新分支堆积。

### 5. 真实验收与额度纪律

真实账户测试基线：
- Ubuntu x86-64、Python 3.12.16
- ComfyUI 0.44.0
- PyTorch 2.15.0+cpu
- CLIProxyAPI v8.0.57
- 本地代理 127.0.0.1:8317

此前 16 次真实工作流中 14 次队列成功、2 次失败。Flare/Sunburst 纯文生成、Images Edit 参考图生成、Edit+Mask、16 张参考图等有成功证据。Custom/2K/4K 和 JPEG/WebP 上游输出曾返回 PNG 1536×1024。Responses DNS 和 Chat Completions 路由失败。

每次真实图片请求都可能消耗用户额度。不要自动重试，不要为更新文档而重复跑全量矩阵。若确实需要真实验证，单次 n=1、指定 case、先说明为什么必要。CI 的真实 ComfyUI 集成使用 fake 图片 API，不得冒充真实 Codex 验收。

### 6. 安全与文档

- 不要将 OAuth token、auth.json、CLIProxyAPI config 中的 Key、浏览器 Cookie、Bearer Header 或真实图片 Base64 写进仓库。
- 工作流 JSON 可能保存客户端 Key 明文，分享前清空。
- CLIProxyAPI 默认只监听本机，不要暴露公网管理接口。
- README 简洁；详细参数、协议、限制、测试证据放 docs。
- 所有文档必须区分源码支持、mock 测试、真实 ComfyUI 集成、真实 Codex 上游和用户本机 GUI 验收。
- 不要把 complexity、原生 4K、上游 JPEG/WebP、Responses、Chat Completions 或 SVG/GIF 说成已完成，除非新增真实证据支持。

### 7. 交接完成标准

- 四个 PR 全部经过独立审查；能合并的逐个合并，不能合并的明确修复。
- main 包含被审查通过的功能；最终节点数和 README/docs 一致。
- 输出兑现核验能清楚报告 pass / warning / not_checked，不误导用户。
- 透明 Alpha 的真实单样例证据和通用能力边界同时保留。
- Python、JavaScript、真实 ComfyUI CPU 集成测试在最终 main 上通过。
- 文档更新为最新，不存在旧说法互相矛盾。
- 已合并分支清理；只保留 main 和实际活跃开发分支。
- 给用户报告：精确 main SHA、合并 PR、CI run 链接、测试数量、未完成事项和需要用户本地验收的内容。

请现在开始。先核对 GitHub 当前状态，再执行审查和整合；不要只给计划或停留在进度汇报。
