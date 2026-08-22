# evidence-suite · 证据驱动写作 / 审查对抗套件

一套「证据驱动（evidence-driven）」的学术 / 技术文档生产流水线，按「编写 / 审核」职责拆分为两个**相互对抗**的 skill，共用一套资产库。核心不变：**所有事实性/争议性论断都挂载 `[Sx]` 来源标记**，没有来源的论断显式降级为 `[假设]` / `[待内部确认]`。

## 组件

| 目录 | 角色 | 入口 |
|------|------|------|
| `evidence-writer/` | **生产**（w1–w9）：文档适配 / 来源检索 / 验证语料 / 证据图谱 / 起草 / 修订 / 导出 | `evidence-writer/SKILL.md` |
| `evidence-reviewer/` | **审查**（r1–r5 + 终审门）：来源审计 / 诚实性自评 / 框架深度门 / 初稿审查 / 外部专家评审 / 终审门 | `evidence-reviewer/SKILL.md` |
| `shared/` | **共享资产库**：`scripts/`（14 个工具）· `references/`（按需加载参考指南）· `templates/`（13 类文档模板） | `shared/README.md` |

## 路径常量（SUITE_ROOT）

本套件所有共享资产与跨 skill 引用统一以 `${SUITE_ROOT}` 开头，**当前取值 `SUITE_ROOT = D:\evidence-suite`**。迁移整个目录时，全量把 `${SUITE_ROOT}` 替换为新根路径即可（Windows 下为 `D:\evidence-suite\…` 反斜杠形式）。

## 对抗循环

```
提交 → 审查 → 判决 → 修订 →（最多 2 轮）→ 终审门 → 导出
```

- **写作方**：负责生产，不自我放行；每个「提交给审核方」的阶段未经判决不得前进。
- **审查方**：有罪推定、只找失败、不写正文、严重即阻断；判决词表见 `evidence-reviewer/README.md`。
- 共用工作区 `proposal_workspace/`（`00_topic.md` … `14_专家修订稿.md`）与共享资产库。

## 快速开始

- **写作方**触发词：开题报告 / 论文写作 / 期刊投稿 / 专利交底书 / GF 报告 / 实施方案 / 调研报告 / 可行性报告 / 白皮书 / evidence-driven / source-grounded / 证据驱动写作 / 学术写作流水线。
- **审查方**触发词：审查 / 评审 / 对抗 / 判决 / evidence-driven / source-grounded / 证据审计 / 红队 / source audit / draft review。
- 详细流程见 `shared/README.md` 的 Pipeline 概览与各 SKILL.md 的阶段编译器。

## 许可

MIT（见仓库根 `LICENSE`）。
