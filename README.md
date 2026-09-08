# skill-assessment

以 Python 为核心的 Skill 质量评估工具。通过 CLI 和配套 Skill，完成静态检查、任务评测、结构化报告，以及用户主动发起的改进回归。

**v0.1 已实现，Windows x64、Linux x86_64 / ARM64 的自动化测试已跑通。** 真实 Claude Code 模型调用仍需在已有 Agent 配置的机器验收；内部 npm 尚未发布。准确的版本、CI 和验收边界见[当前进度](docs/progress.md)。

## 可以做什么

- 按 Agent Skills 规格检查 SKILL.md、元数据、名称、目录匹配和本地 Markdown 引用，静态错误前置阻断动态执行。
- 使用已安装的 Claude Code，或符合本地 JSON 文件协议的自定义 Agent。宿主、执行器和评分器可以采用同款或不同款 Agent。
- 使用规则断言、自定义 Python 脚本、独立 Agent 会话评分。
- 输出 JSON、Markdown、离线 HTML、JUnit，保留输入快照、哈希、原始输出、产物和失败证据。
- 按用例筛选、重复评测、有/无 Skill 对照、失败重跑、父运行比较。
- 配套 Skill 通过对话建例、运行和解释报告；只有用户要求改进时才修改目标 Skill。

## 在 Windows 构建并发布内部 npm

需要预装 **Python 3.11+（包含 venv/ensurepip）和 Node.js 20+ / npm**。核心不要求 Bash、PowerShell、WSL 或 Docker；以下命令可在 Git Bash、CMD、PowerShell 或 Linux shell 中运行。Git Bash 路径建议用正斜杠并加引号。

在源码仓库根目录：

```bash
python scripts/build_npm.py
npm install -g "./dist/skill-assessment-0.1.0.tgz" --offline --no-audit --no-fund
skill-assessment --version
skill-assessment doctor
```

构建仅使用 Python 标准库和本机 npm。包内包含纯 Python wheel、离线 YAML 依赖、配套 Skill、文档及演示用例；首次启动只从包内安装到专用 venv，不访问 PyPI 或 GitHub。

如果内部 npm 使用 scope：

```bash
python scripts/build_npm.py --name @your-scope/skill-assessment
npm publish "./dist/your-scope-skill-assessment-0.1.0.tgz" --registry https://npm.example.internal
```

将 scope 和示例 registry 替换为你实际使用的值，认证沿用本机 npm 配置。**构建不会发布。** 源码根 package.json 设置了 private，发布目标应是构建后的 tgz。

普通使用者只需从已配置的内部 registry 安装：

```bash
npm install -g @your-scope/skill-assessment
skill-assessment skill install
```

默认将配套 Skill 安装到 `~/.claude/skills/skill-assessment`。自定义 Agent 可以指定技能父目录：

```bash
skill-assessment skill install --dest "./agent-skills"
```

命令只复制包内资源。自定义 Agent 作为对话宿主只需能读取 Skill、操作文件和调用 CLI；作为被测执行器则需实现[执行协议](docs/usage.md#自定义-agent)。

## 开始一次评测

对已有的本地 Skill：

```bash
skill-assessment check "./my-skill"
skill-assessment init "./my-skill"
skill-assessment validate "./my-skill"
skill-assessment run "./my-skill" --json
```

`init` 创建的是起步模板。正式评测前，通过配套 Skill 把模板改成真实任务、fixtures 和独立评分标准。已有 evals 时不会覆盖。

安装配套 Skill 后，可以在宿主 Agent 中说：

> 使用 skill-assessment 评测 C:/skills/my-skill。先读取能力并补充代表性用例，再执行评测，解释失败证据和报告；暂时不要修改 Skill。

随后主动要求：

> 根据这次报告改进 Skill，保留有效评分标准，先重跑失败用例，再完整回归，并说明前后差异。

CLI 返回本次 `result.json` 的路径。同目录下有 `report.md` 和 `report.html`；HTML 可离线打开，无 CDN。

## 先跑一个不调用模型的演示

在源码根目录，构建并安装工具后：

```bash
skill-assessment run "./examples/text-normalizer" --benchmark --repeat 2
skill-assessment run "./examples/sales-summary"
skill-assessment run "./examples/sum-numbers"
```

这些用例使用确定性模拟执行器，分别演示结构化文本、CSV 文件处理和 Skill 脚本调用。它们证明工具流程可用，不能用于宣称真实模型效果。

## 文档

| 文档 | 用途 |
| --- | --- |
| [使用指南](docs/usage.md) | eval/case 示例、三类评分、Claude 与自定义 Agent、报告、复测、故障处理 |
| [架构](docs/architecture.md) | 实际模块、分发、进程、隔离与数据契约 |
| [进度与验收](docs/progress.md) | 测试证据和未完成的真实环境验收 |
| [开发路线图](docs/roadmap.md) | 后续演进阶段与验收目标 |
| [工程决策](docs/decisions.md) | 选型原因、范围和调整记录 |
| [需求](docs/requirements.md) | 用户要求及验收场景 |
| [参考资料](docs/references.md) | 固定版本的上游资料 |
| [CI 使用](docs/ci.md) | Windows/Linux 流水线门禁与报告归档 |

## 开发与许可

```bash
python -m unittest discover -s tests -v
python scripts/build_npm.py
```

产品流程参考 [skill-up](https://github.com/alibaba/skill-up)，静态规则依据 [Agent Skills 规格](https://agentskills.io/specification)。这是独立 Python 实现，**不直接兼容 skill-up 配置**。当前只承诺单轮用例、本地文件协议及已记录的平台范围。

代码采用 [Apache-2.0](LICENSE)，随包携带的 PyYAML 纯 Python 部分采用 MIT，固定版本及哈希见 [第三方声明](THIRD_PARTY_NOTICES.md)。本工具不提供安全认证或“生产就绪”综合评分。
