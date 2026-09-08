# skill-assessment

以 Python 为核心的 Skill 质量评估工具。通过 CLI 和配套 Agent Skill，完成静态检查、用例评测、结构化报告与用户主动发起的改进回归。

**当前状态：P0 需求与架构基线，尚无可安装版本或业务实现。** 本仓库文档中的命令、模块和数据字段均为设计约定，不能据此认为功能已经可用。

## 产品方向

- Windows x64 优先，随后扩展 Linux x86_64 / ARM64；Linux 的具体发行版与架构范围在对应阶段验证。
- 核心逻辑使用 Python，npm 负责分发，允许少量 JavaScript、TypeScript 和 shell 辅助代码。
- 使用者可自行安装 Python；安装和初始化从内部 npm 仓库及包内资源获取工具依赖。
- 提供 CLI 和配套 Skill，在 Claude Code 或具备文件与命令工具的自定义 Agent 中通过对话使用。
- 编排、执行和评分可采用同款或不同款 Agent；测试与评分使用独立会话。
- 默认复用 Agent 已有模型及认证配置，不要求用户重新提供模型服务配置。
- 评测输出结构化证据；用户主动要求演进后，才指导 Agent 修改目标 Skill、补充用例并回归。

## 文档入口

| 文档 | 用途 |
| --- | --- |
| [需求与产品边界](docs/requirements.md) | 已确认需求、使用流程、首版范围和验收目标 |
| [架构设计](docs/architecture.md) | 模块职责、Agent 协议、数据流、报告、Windows 与分发设计 |
| [阶段计划](docs/roadmap.md) | 分阶段任务、退出条件及验证方法 |
| [工程决策](docs/decisions.md) | 默认方案、选择理由和可调整项 |
| [当前进度](docs/progress.md) | 当前完成情况、下一步任务和已知限制 |
| [参考资料](docs/references.md) | 固定版本的上游资料及借鉴范围 |
| [开发约定](AGENTS.md) | 后续人工或 Agent 开发的协作约定 |

建议先阅读需求与阶段计划。继续开发时，先读取当前进度，再核对实际分支、提交和工作区变化。

## 首个可用版本的目标

在 Windows 上，从内部 npm 安装工具和配套 Skill，为本地目标 Skill 创建用例，执行静态检查和真实 Agent 评测，生成 JSON、Markdown、HTML 报告；用户要求改进后，利用上一轮证据完成修改与回归。

首版包含规则、Python 脚本和按需启用的 Agent 评分，支持重复运行与有／无 Skill 对照。具体交付拆分见阶段计划。

## 参考与许可证

产品流程参考 [alibaba/skill-up](https://github.com/alibaba/skill-up)，静态规则依据 [Agent Skills 规格](https://agentskills.io/specification)，并参考 [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref)。这是独立的 Python 实现计划，配置兼容范围将显式记录。

本仓库沿用初始提交中的 [Apache License 2.0](LICENSE)。引入上游代码或资源时，记录来源及版本并保留适用的许可证和声明。
