# 当前进度

更新日期：2026-09-08。

## 当前交付

P0 基线已通过 PR #1 合并。v0.1 的 Python CLI、静态校验、执行器、评分、报告、复测与对照、配套 Skill、离线 npm 分发均已有实现。当前正在 feat/evaluation-cli 分支完成跨平台验收和使用文档。

- Python 3.11+，Node 20+；纯 Python wheel 随 npm 包交付。
- 内置 Claude Code CLI 适配器和 local JSON 文件协议。
- rule / script / agent 三类评分，JSON / Markdown / HTML / JUnit。
- 输入与 Skill 快照、文件哈希、逐试验证据、事件日志、父运行和标准变化识别。
- 评测不自动改写目标 Skill；配套 Skill 指导用户主动要求后的改进。
- Windows Job Object 子进程管理、npm cmd shim 的直接 Node 调用、取消记录。
- 三个确定性演示 Skill 和模拟执行器，不代表真实模型质量。

## 当前验证证据

Linux x86_64 / Python 3.12.13 / Node 24.19.0 / npm 11.9.0：

    python3 -m unittest discover -s tests -v

30 项：29 通过，1 项 Windows 专用 shim 测试在 Linux 跳过。包含并发首次初始化、无法连接的 registry 配置下 npm --offline 安装、包内 pip --no-index 初始化、校验和失败、缓存修复、安装后 Skill 与示例评测、超时/正常退出/取消后子进程清理。

配套 Skill 通过 skill-creator quick_validate。npm tgz 已构建。

## 尚在验证

- GitHub Actions Windows x64 Python 3.11/3.12、Linux x86_64 Python 3.11/3.12、Linux ARM64 Python 3.12 矩阵已编写，实际结果待记录。
- 当前环境没有 Claude Code 和模型认证，真实 Agent 调用、用户 Windows 桌面/Git Bash 行为尚未验证。无需用户提供凭据。
- 内部 npm 发布尚未执行；没有取得 registry 地址、包名 scope 或发布凭据。构建与发布独立，不默认发布到 npmjs.org。
- 架构文档、协议 schema 和完整中文使用文档正在同步到实际实现。

## 后续演进

真实 Agent 验收后再声明完整 Windows 产品支持。HTTP 适配器、32 位 Linux、skill-up 配置导入、复杂多轮、OS 沙箱和并发评测仍为后续能力，不属于当前兼容承诺。
