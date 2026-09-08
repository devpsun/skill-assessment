# 参考资料与借鉴范围

调研基线：2026-09-07。本文件固定参考仓库 commit，避免后续把 main 的变化混入当前设计。网页资料记录查阅日期；实现阶段采用新资料时更新此记录。

## Skill 规格与静态检查

- [Agent Skills specification](https://agentskills.io/specification)，查阅于 2026-09-07：格式与元数据要求、资源组织建议和渐进加载。用于制定规则，硬性要求与建议分开处理。
- [skills-ref README](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref/README.md)：官方定位是演示参考实现，不面向生产。
- [skills-ref validator.py](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref/src/skills_ref/validator.py)：参考元数据校验与错误处理，不能假定它覆盖全部规格。

参考仓库：`agentskills/agentskills`，commit `69ef37e9424c0a7ea9dd2293b559e43ec8176379`。

观察：spec 名称说明同时出现 Unicode 与 a-z/0-9 表述；validator 使用 Unicode 规范化与 isalnum。字段检查也不能据参考代码直接推断规范是否允许扩展。因此，本项目将规则 profile 和差异测试作为明确实现项，不静默追随上游。

## skill-up

参考仓库：`alibaba/skill-up`，commit `ebc7aa0ad9d352c1b677429b496f3cd22f83e640`。

| 资料 | 借鉴内容 |
| --- | --- |
| [README.zh.md](https://github.com/alibaba/skill-up/blob/ebc7aa0ad9d352c1b677429b496f3cd22f83e640/README.zh.md) | CLI + Skill 的产品形式、声明式用例、评分、报告和对话改进流程。 |
| [skill-upper](https://github.com/alibaba/skill-up/blob/ebc7aa0ad9d352c1b677429b496f3cd22f83e640/skills/skill-upper/SKILL.md) | 建例、校验、执行、解读、用户要求后的改进；保留有效断言。 |
| [Custom Engine](https://github.com/alibaba/skill-up/blob/ebc7aa0ad9d352c1b677429b496f3cd22f83e640/docs/design/custom-engine.md) | 输入输出契约、local/http 传输分离、显式产物。 |
| [Windows 指南](https://github.com/alibaba/skill-up/blob/ebc7aa0ad9d352c1b677429b496f3cd22f83e640/docs/zh/guide/windows.md) | Windows Agent 引导、解释器、路径和 shell 限制。 |
| [构建配置](https://github.com/alibaba/skill-up/blob/ebc7aa0ad9d352c1b677429b496f3cd22f83e640/.goreleaser.yaml) | 已有多平台构建目标；编译支持不等同于完整流程验收。 |
| [eval 模板](https://github.com/alibaba/skill-up/blob/ebc7aa0ad9d352c1b677429b496f3cd22f83e640/skills/skill-upper/assets/eval.yaml.tmpl) | 套件、用例与评分的组织方式。 |
| [case 模板](https://github.com/alibaba/skill-up/blob/ebc7aa0ad9d352c1b677429b496f3cd22f83e640/skills/skill-upper/assets/case.yaml.tmpl) | 输入、fixtures、断言和约束的结构。 |

该版本 Windows 指南已有支持说明，而 skill-upper 安装段仍写仅支持 macOS/Linux，存在文档不同步。借鉴流程时需核对实际实现与版本，不复制这一矛盾。

本阶段是公开资料调研与独立设计，没有导入上游代码、Skill 或模板。以后复用时逐文件记录来源和保留声明，不能仅添加一个项目链接就当成完成来源管理。

## 运行与分发

以下官方文档查阅于 2026-09-07，用于验证候选实现路径，不表示本项目已通过相应平台验收。

- [Claude Code 非交互使用](https://code.claude.com/docs/en/headless)：已安装 CLI 的编程调用和结构化输出能力。
- [pip 从本地包安装](https://pip.pypa.io/en/stable/user_guide/#installing-from-local-packages)：离线 wheelhouse 与禁止索引查询的安装路径。
- [Python venv](https://docs.python.org/3/library/venv.html)：在目标机器创建专用 Python 环境，运行时使用环境中的解释器。
- [npm package.json](https://docs.npmjs.com/cli/v11/configuring-npm/package-json/)：包内文件、命令入口、平台依赖及发布配置。该页面已在需求调研阶段查阅。


## v0.1 实现补充资料（2026-09-08 核对）

- [Claude CLI reference](https://code.claude.com/docs/en/cli-reference)：独立 session、JSON 输出、--settings 与 --safe-mode。后者保留认证/模型/权限，并禁用自定义上下文；不等同于 OS 沙箱。
- [Claude 嵌套启动限制问题记录](https://github.com/anthropics/claude-code/issues/25803)：官方仓库的问题记录用于识别已知运行限制，不作为所有版本行为保证。
- [Windows ResumeThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread)：进程先加入 Job，再恢复线程。
- [GitHub runner 范围](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)：Windows x64、Ubuntu x64 / ARM64 CI 标签。
- [Wheel 格式](https://packaging.python.org/en/latest/specifications/binary-distribution-format/) 与 [pip 本地安装](https://pip.pypa.io/en/stable/user_guide/#installing-from-local-packages)：离线纯 Python 分发。
