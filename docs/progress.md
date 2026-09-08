# 当前进度

更新日期：2026-09-08。

## 当前交付

P0 基线已通过 PR #1 合并。v0.1 的 Python CLI、静态校验、执行器、评分、报告、复测与对照、配套 Skill、离线 npm 分发均已有实现。[实现 PR #2](https://github.com/devpsun/skill-assessment/pull/2) 完成最终跨平台验证后合并。

- Python 3.11+，Node 20+；纯 Python wheel 随 npm 包交付。
- 内置 Claude Code CLI 和 local JSON 协议；七类 JSON Schema 可离线导出。
- rule / script / agent 三类评分，JSON / Markdown / HTML / JUnit。
- 输入与 Skill 快照、文件哈希、逐试验证据、事件日志、父运行和标准变化识别。
- 评测不自动改写目标 Skill；配套 Skill 指导用户主动要求后的改进。
- Windows Job Object、npm cmd shim 直接 Node 调用、协作取消。
- 三个确定性示例与中文使用/构建/CI 文档；真实 Claude 验收脚本。

## 验证证据

本地 Linux x86_64 / Python 3.12.13 / Node 24.19.0 / npm 11.9.0：

    python3 -m unittest discover -s tests -v

38 项：37 通过，1 项 Windows 专用 shim 测试在 Linux 跳过。包括静态阻断、非法数据、隐藏断言隔离、产物、三类评分、报告、比较、假 Claude CLI 参数及权限拒绝、并发首次初始化、离线安装、校验和失败、缓存修复、超时/正常结束/取消后后代进程清理。

安装验证使用无法连接的 registry 配置、npm --offline、包内 pip --no-index 和 --require-hashes。它证明此工具安装路径不依赖 registry/PyPI 在线解析，不代表用网络抓包验证了整个 Agent 的所有外部访问。

配套 Skill 通过 quick_validate，文档相对链接和 git whitespace 检查通过。测试无需安装额外 Python 库。

[已通过的五组 CI](https://github.com/devpsun/skill-assessment/actions/runs/34180665034) 对应提交 5023132，执行当时的 30 项测试：

| 平台 | Python | 结果 |
| --- | --- | --- |
| Windows Server 2025 x64 | 3.11 | 30 通过 |
| Windows Server 2025 x64 | 3.12 | 30 通过 |
| Ubuntu x86_64 | 3.11 | 29 通过，Windows 专用项跳过 |
| Ubuntu x86_64 | 3.12 | 29 通过，Windows 专用项跳过 |
| Ubuntu 24.04 ARM64 | 3.12 | 29 通过，Windows 专用项跳过 |

最终 38 项测试与新增 Windows Git Bash smoke 正在送入相同矩阵，完成后更新此记录。此前 Windows 首轮失败源于 npm 自身 wrapper 与普通 npm 包 shim 格式不同，已修复并在上述矩阵重跑通过。

## 需求验收边界

| 场景 | 状态 |
| --- | --- |
| A01 安装、中文/空格路径 | Windows/Linux CI 通过；没有将 Server runner 等同于用户桌面环境 |
| A02-A03 静态检查及动态阻断 | 自动化通过 |
| A04 真实 Claude Code 代表业务用例 | 未执行；当前环境无 Claude/模型认证 |
| A05 通用自定义执行器 | 模拟协议及三个示例通过；具体私有 Agent 需自己的适配器 |
| A06 超时、异常、取消、评分失败 | Windows/Linux 自动化通过 |
| A07 重复与对照 | 模拟执行器通过；真实 Claude safe-mode 的对照仍需验收 |
| A08 评测不改源 Skill | 自动化通过 |
| A09 主动改进闭环 | 配套 Skill、父运行、失败/全量回归已实现；真实对话演进尚未实测 |
| A10 移动报告后离线阅读 | 自动化通过 |

## 尚未发生的外部动作

- 没有执行真实 Claude 模型调用，也不需要用户向开发者提供模型凭据。可在已有 Agent 的机器执行 scripts/verify_claude.py，并继续运行真实业务用例。
- 内部 npm 尚未发布。构建产物和命令已具备；发布需实际 registry、scope、授权账号，沿用用户本机 npm 配置。没有发布到 npmjs.org。
- Claude 嵌套启动保护、项目专属配置、全局 Skill 暴露等行为有明确入口和限制，但模型环境的最终验收不能由模拟测试代替。

## 后续演进

P1-P4 功能完成；P5 的 Linux、P6 的 CI 基础提前完成。真实 Agent 验收后再声明整个用户环境已验收。HTTP 适配器、32 位 Linux、上游配置导入、复杂多轮、OS 沙箱及并发评测为后续能力。
