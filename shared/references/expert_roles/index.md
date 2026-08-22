# Expert Role Index

Stage 8（审查门 r5）loads 1-2 role files matching `{topic}` domain keywords.
Each file contains 3-5 expert personas with distinct review perspectives.

## Selection by domain keywords

| If `{topic}` contains... | Load this file |
|------------------------|---------------|
| 人工智能/机器学习/深度学习/神经网络/大模型/算法/数据/传感信号/智能监测 | `ai.md` |
| 幼儿/教育/教学/课程/学习/学生/教师/体育/游戏/学前 | `education.md` |
| 工程/设备/传感器/系统/架构/安全/核/电缆/老化 | `engineering.md` |
| 材料/能源/动力/电池/电力/化工/冶金 | `engineering.md` |
| 经费/预算/资金/资助/财政/投资/采购 | `social_science.md`（另补 1 名科研管理/基金评审视角，见下方说明） |
| 临床/疾病/药物/流行病/卫生/患者/健康/医学 | `medical.md` |
| 政策/法规/经济/社会/治理/管理/市场 | `social_science.md` |

> **funding 域专项**：命中 funding 关键词时，除加载 `social_science.md` 外，评审组应额外加入一名「科研管理/基金评审专家」视角（关注立项必要性、预算合理性、指标可验收性、与资助方向契合度）。该视角不单独成文件，由 LLM 在评审组中虚拟一个专家角色（标注 `domain=funding_management`），避免与社会科学专家视角雷同。

## If multiple keywords match

Load 2 files (e.g., a health education topic loads `education.md` + `medical.md`).
Run reviews in parallel, label each expert with their domain.

## If no keyword matches

Load `education.md` + `engineering.md` as the two most broadly applicable domains.

## Token budget

- `index.md` (this file): always loaded, ~33 lines
- Domain files: loaded on demand, ~28-56 lines each (<1K tokens)
- Stage 8 (r5) total overhead: ≤ 3 files, ≤ 170 lines
