# CI/CD 使用

仓库自测在 .github/workflows/ci.yml 中，覆盖 Windows x64、Ubuntu x86_64 / ARM64 与 Python 3.11/3.12。流水线运行标准库 unittest、构建 tgz、离线安装、并发初始化、进程树与完整模拟评测，保留可安装 npm 包。

## 在自己的 Windows/Linux 流水线评测 Skill

预先准备 Python、Node/npm、已配置好的 Agent，以及内部 npm registry 访问。任何能够运行以下命令并归档目录的流水线平台都可接入：

```bash
npm install -g @your-scope/skill-assessment
skill-assessment doctor --require-agent
skill-assessment run "./my-skill" --output "./assessment-runs" --format json --format html --format junit --json
```

使用 shell 的失败门禁机制保留 run 的退出码；不要用后续的归档命令覆盖它。无论成功失败都保留 assessment-runs，包括 result、manifest、原始输出和 junit.xml。0/1/2/130 的含义见[使用指南](usage.md)。

模型认证沿用流水线 Agent 的既有配置和秘密注入机制。不要在 eval 文件中写密钥，公开 CI 默认只跑自造数据与模拟执行器。

## 内部 npm 发布

构建与发布分离：

```bash
python scripts/build_npm.py --name @your-scope/skill-assessment
npm publish "./dist/your-scope-skill-assessment-0.1.0.tgz" --registry https://npm.example.internal
```

发布使用当前 npm 账号的授权。源码根包为 private，避免误将不完整源码包发布。包没有安装脚本，从 tgz 安装可使用 --offline --ignore-scripts；首次运行的工具依赖同样只从包内准备。

CI artifact 是经过该 job 构建的安装包，不表示已经发布到内部 npm。Windows 构建的纯 Python/npm 包也可以在目标 Linux 架构使用；新增任何 native 依赖后必须重新评估此声明。

## 真实 Claude 验收

在已经配置 Claude Code 的源码机器运行：

```bash
python scripts/verify_claude.py --output "./claude-acceptance"
python scripts/verify_claude.py --output "./claude-acceptance" --agent-judge
```

第一条验证真实 Agent 读取 Skill 和规则评分；第二条另启独立 Agent 评分。它们实际调用模型服务，结果与 CI 模拟测试分开保存。可选 --controlled 验证支持 --safe-mode 的 Claude 版本。该小样例不能代替真实业务 Skill 验收；随后应运行项目的代表性用例。

目前公共 CI 没有用户模型配置，因此没有执行上述真实模型测试，也没有发布内部 npm。
