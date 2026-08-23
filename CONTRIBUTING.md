# Contributing

感谢参与 `evidence-suite`。这是一个公开的「研究 Agent 证据校验与溯源层」Skill 套件。
本文件说明如何贡献——**先读 `docs/architecture.md` 与 `THREAT_MODEL.md` 再动手**。

## 开发环境与检查

```bash
python tests/run_tests.py          # 回归测试（唯一硬性要求：提交前必须全绿）
python eval/run_eval.py            # Eval/Golden 自动判分（script 级必须 0 fail）
python shared/scripts/probe_capabilities.py --human   # 运行时能力探测
```

- 核心脚本**只用 Python 标准库**（`shared/scripts/rule_profile.py` 的内置 YAML
  子集解析器保证 `rules.yaml` 无需 pyyaml 也能读）。新脚本尽量不引入第三方依赖；
  确需依赖时加到 `shared/requirements.txt` 并标注 optional。
- 跨平台：Windows（PowerShell）/ macOS / Linux 都要能跑；不要写死绝对路径或
  `D:\evidence-suite` 之类。

## 目录速览

```
evidence-writer/ evidence-reviewer/  两个对抗 skill（SKILL.md + prompts）
shared/scripts/   确定性工具        shared/config/   规则（rules/source_ranking）
shared/schemas/   manifest 契约     shared/references/ 参考指南
shared/templates/ 文档模板          examples/quickstart/ 最小 demo
eval/  eval golden + harness        tests/  回归测试
runtime/ 能力配置                    docker/ 沙箱        docs/ 架构文档
```

## 各类扩展怎么做

### 1. 加/改规则（`shared/config/rules.yaml` 或 `source_ranking.yaml`）

- 保持**块式 YAML**（无行内 `{…}` flow mapping），否则内置最小解析器读不了。
- 改阈值默认值请在 CHANGELOG 注明"默认档变更"；业务覆盖应走
  `config/rules.user.yaml` 或 `--profile`，不写死进默认档。
- 新增 `scenario_profiles` 时同步 `docs/architecture.md` 的扩展点说明。

### 2. 改 manifest 契约（`shared/schemas/*.schema.json`）

- **必须递增 `schema_version`**（`shared/scripts/validate_manifest.py` 顶部的
  `SCHEMA_VERSION`），旧版解析器据此拒绝而非静默误读。
- 同步 `validate_manifest.py` 的校验逻辑 + `tests/` 的正/负例 +
  `examples/quickstart/expected/`（`run_demo.ps1` 重生成）。

### 3. 加 golden 用例（`eval/golden/*.json`）

格式见 `eval/README.md`。脚本级用例要能**离线自动判分**（不依赖网络/真实 agent）；
agent 行为级用例标 `kind: "manual"` 并写清核验点。

### 4. 新脚本 / 改脚本

- 跟随现有风格：`_ensure_utf8_streams()` 开头、`argparse`、退出码约定
  （0 通过 / 1 失败 / 2 用法错误）、stdout 纯净（信息行走 stderr，不污染 `--json`）。
- 涉及网络/文件写入的脚本必须遵循 `SECURITY.md` 的 SSRF / 路径 / 大小上限约束，
  并在 `THREAT_MODEL.md` 对应条目登记。
- 为脚本加 `tests/run_tests.py` 用例。

### 5. 文档

- 改 SKILL / 规则 / 脚本行为时，同步 `README.md`、`shared/README.md`、`CHANGELOG.md`。
- 安全相关变更必须同步 `SECURITY.md` 与 `THREAT_MODEL.md`。

## 提交规范

- 提交信息用 `scope: 中文描述` 前缀，scope ∈ {P0..P6, feat, fix, docs, chore, security, eval}。
  示例：`fix: check_framework_depth.py --json 不返回非零的门禁失效`。
- 提交前跑一遍 `python tests/run_tests.py` 与 `python eval/run_eval.py`。
- 一次提交只做一个主题；大功能拆多个原子提交。

## PR 检查清单

- [ ] `tests/run_tests.py` 全绿（含新用例）
- [ ] `eval/run_eval.py` script 级 0 fail
- [ ] 未引入非白名单脚本执行 / 未放宽安全约束
- [ ] 契约变更已升 `schema_version` 并更新 expected
- [ ] CHANGELOG 已记录
