# 来源路由表（Domain Routing）

把题目域（topic_domain）映射到 `source_registry.json` 中的 category 白名单，再由 `scripts/select_sources.py` 展开为具体检索指令。路由目的：**Stage 1 只把相关权威源注入检索范围，避免广撒网与无关源污染。**

## 路由规则

1. Stage 0 建立 Topic Card 时，确定 `topic_domain`（下表之一）。
2. 运行 `python scripts/select_sources.py --domain <topic_domain>` 输出该域命中的来源清单与检索指令。
3. 若 `--domain` 未指定或无法判定，默认走 `general`（全部权威源），脚本会提示人工确认。

## domain → category 映射

| topic_domain | 命中的 categories | 说明 |
|---|---|---|
| `nuclear` 核电/核安全 | international_regulator, international_industry, industry_technical, nuclear_data, china_regulator, china_standard, technical_report_library, international_standard | 含 IAEA/NRC/EPRI/OECD-NEA/NNSA、核数据与安全标准 |
| `materials` 材料/腐蚀/老化 | materials_data, materials_engineering_data, materials_scientific_database, international_standard, china_standard, nuclear_data, technical_report_library, cross_technical_report_library | 含 NIST/NIMS/ASTM/COD/MatWeb，及 NTRL/NTRS 历史试验报告 |
| `energy` 能源/电力 | energy_international, energy_data, government_agency, national_lab, china_regulator, china_technical, industry_technical | 含 IEA/EIA/IRENA/REN21/EI Review/WNA/NEA/CEC |
| `education` 教育 | education_statistics, education_research, china_regulator, scholarly_index | 含 UIS/OECD Education/World Bank/ERIC/NCES/教育部 |
| `ai` 人工智能/大模型 | ai_research, ai_index, ai_policy, ai_standard, ai_china_standard, china_technical, scholarly_index | 含 arXiv/ACL/NeurIPS/Stanford AI Index/OECD.AI/SC42/TC260 |
| `funding` 基金/科研管理 | china_funding_repository, china_tech_report_system, cross_technical_report_library, scholarly_index | 含 NSFC-NPD/NSTRS/NTRL 等结题与科技报告库 |
| `engineering` 通用工程 | international_standard, china_standard, technical_report_library, cross_technical_report_library, materials_engineering_data, china_funding_repository | 跨领域工程标准、技术报告、物性数据与国内基金结题/成果（工程监测、水利、土木、能源类选题建议启用 china_funding_repository 获取 NSFC 结题报告） |
| `general` 跨域/未定 | 全部 authoritativeSources | 兜底：全量注入 + scholarly_index 优先做引文核验 |

## 检索指令生成规则（在 select_sources.py 中实现）

对每个命中 source 生成一条 `search_directive`：

- `allowFullText: true` → 检索指令为 `site:<domain> <query>`，允许 webfetch 全文 / 批量下载 PDF。
- `allowFullText: false` → 仅允许获取题录/摘要与文档编号，禁止虚构全文内容；对应 rule3。
- 把 `usageHint` 并入指令作为检索词模板（如 INIS 子库、ADAMS、MatNavi、openstd）。
- 标准类（category 含 `standard` 或 id 属 std_samr/openstd_samr）强制先核现行有效性。
- 统计类来源（energy_data/education_statistics）要求回原始统计机构，禁止智库/媒体图表替代。

## 使用注意

- `source_registry.json` 为用户本地权威来源主清单（`writing_source_list.extended.json`，由用户维护）的快照；若用户提供更新版主清单，优先读取用户提供的路径（`select_sources.py --registry <path>`）。
- 每份文档的 `04_validated_sources.json` 中，命中清单的来源须写 `registry_id`；不在清单内的来源须在 `audit_report` 记录补充理由。