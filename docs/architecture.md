# 实现架构

本文件描述 v0.1 实际代码。需求与范围见 requirements.md，实际平台证据见 progress.md。

## 职责

| 模块 | 职责 |
| --- | --- |
| npm/skill-assessment.js | 查找 Python、启动 bootstrap、转发协作取消 |
| npm/bootstrap.py | 校验 wheel、互斥创建专用 venv、从包内离线安装、启动 CLI |
| build_backend.py / scripts/build_npm.py | 标准库 PEP 517 wheel 构建、npm staging/tgz；不自动发布 |
| cli.py | 参数、doctor、Skill 安装、schema 导出和退出码 |
| yamlio.py / validation.py / config.py | 受限 YAML、静态规则、严格配置及路径校验 |
| contracts.py | 可离线导出的 JSON Schema 2020-12 契约 |
| workspace.py / runner.py | 快照、试验工作区、执行生命周期、证据和父运行 |
| process.py / engines.py | Windows/POSIX 进程树、Claude Code 和 local 协议 |
| judges.py | 独立进程规则、Python 脚本、独立 Agent 评分 |
| reporting.py | 统计、对照、结果一致性检查、Markdown/HTML/JUnit |
| resources/skills/skill-assessment | 随包分发的对话操作 Skill |

Python 模块位于 src/skill_assessment。宿主 Agent 负责编例和对话解释；CLI 负责可记录的执行与评分。没有额外聊天服务、数据库或自动演进守护进程。

## 一次运行

1. 加载 eval 与 case，校验类型、约束、路径和唯一 ID。
2. 分配 run_id，预列所有 case × variant × repeat，落盘 initial result 与事件。
3. 静态检查失败则阻断，生成带原因的结果，不调用 Agent。
4. 快照目标 Skill、用例、fixtures 和独立 grader；记录哈希与配置指纹。
5. 为每个试验创建 workspace，仅注入任务输入和声明的 Skill。
6. 执行 Agent、归档显式产物，再向独立 grader 提供原始任务、标准和证据。
7. 每个试验后原子更新结果；结束时统计、记录父运行比较、生成阅读视图。

JSON 是事实记录。run 只写自己的运行目录；init 和宿主建例流程单独写 eval。源码改进不在 runner 中发生。

## Agent 与隔离

Claude 使用已安装 CLI 的 -p / --output-format json / 独立 --session-id；执行版本由 --version 记录。权限和服务来自 Agent，项目设置可通过显式 settings_file 传递。任务与评分可以同款或不同款 Agent，每次都是新会话。非交互不代表自动取得所有工具权限。

默认 inherited 保留用户配置，对照可能受外部 Skill/上下文影响，标为无效。controlled 对 Claude 使用其 --safe-mode 并显式提示读取被测 Skill；对 local 是接入方声明。报告不会把这种配置隔离当作 OS 沙箱或自然触发证据。

为避免意外共享会话，工具不移除 Claude 的嵌套启动保护；具体版本拒绝时需要独立终端运行。模型配置无需传给评测工具开发者。

## Windows 与分发

Python 核心不拼接 shell 命令。普通 npm shim 和 npm/npx 自身 wrapper 均解析到 Node JavaScript 入口，保留参数字面值；不识别的 bat/cmd 拒绝执行并给出改配入口说明。

Windows 子进程先 suspended 创建，再加入 kill-on-close Job Object，使用文档化的线程 API 恢复。正常结束、超时、超量日志与取消都关闭 Job，清理后代进程。POSIX 使用独立进程组。Node 通过每次启动独有的取消文件通知 Python，留出落盘时间，超时后才强制清理。

npm 包只有 JavaScript 启动器、Python bootstrap、纯 Python wheel、文档和样例；PyYAML 6.0.3 的纯 Python 实现在独立 vendor 命名空间中，无 C 扩展或运行时第三方下载。venv/pip 使用 Python 自带 ensurepip，再用 --no-index / --require-hashes / --no-deps 安装包内 wheel。构建机不需要联网下载构建依赖。

缓存按 bundle 和解释器区分，Windows msvcrt / POSIX flock 提供初始化互斥。升级创建新环境；现有环境不会改变正在运行的旧版本。

## 契约与比较

schema_version / protocol_version 当前均为字符串 "1"。配置严格拒绝未知字段；响应和报告容许兼容性扩展字段，但必需字段和状态必须有效。schema 命令输出完整本地定义，不引用远端业务 schema。文件存在、评分逻辑和路径边界由运行时额外校验。

manifest 保存 Skill 文件哈希和整体摘要、用例指纹、fixtures 摘要、Python/平台/工具版本。用例指纹包含输入、grader、脚本哈希、fixtures、执行配置、约束与工具版本。变动 Skill 的效果可以用父运行比较；修改评分标准不会被当成同条件提升。外部执行器实现、模型服务和环境变化的全部内容无法冻结，因此可比只表示已记录条件一致。

quality 统计目标组，summary 统计全部试验，对照单独呈现。每个评分有断言与证据；未评分不算通过。报告支持移动目录后离线重建，HTML 使用转义、本地链接和 CSP，无脚本/CDN。

## 实际边界

v0.1 串行执行单轮用例。默认限制：YAML/SKILL.md 2 MiB；Skill 快照 64 MiB/2000 文件；每用例 fixtures 32 MiB/100 文件；产物 32 MiB/100 文件；JSON 输入 16 MiB；进程 stdout/stderr 各最多保留 8 MiB。正则在有超时的子进程中执行。

不保证任意不可信代码的安全执行、模型输出确定性、全量 Markdown 语法检查或自动跨 Agent 适配。真实模型测试不在无认证的公共 CI 中假装通过。
