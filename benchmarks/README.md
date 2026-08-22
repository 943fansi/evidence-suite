# Evidence Suite 评测基准（Benchmark）

衡量「证据驱动写作 / 审查」这套 skill 在**实际 agent 运行**中的表现——测的不是脚本，而是"skill 是否被正确触发、是否正确处置证据"。脚本层的确定性门禁已由 `tests/run_tests.py` 覆盖；本基准针对 **LLM/agent 行为层**，因此必须由真实 agent 运行用例后打分，不能离线生成。

## 指标

| 指标 | 定义 | 理想值 |
|------|------|--------|
| `activation` | 该触发时触发、不该触发时不触发的比例 | 高 |
| `source_verification` | 事实性论断均有可回溯 URL 且经审计（无编造/未闭合） | 高 |
| `claim_source_alignment` | `support_level` 与原文实际支撑程度一致 | 高 |
| `unsupported_detection` | 对 `evidence_status ∈ {inferred, unsupported, contradicted}` 的 claim 正确降级/阻断 | 高 |
| `false_blocker` | 无问题却被判定 BLOCK 的比例 | 低 |
| `citation_padding` | 引用与结论无关 / 填充的比例 | 低 |

## 用例集

每个用例：给定输入 → 期望行为 → 命中的指标。

| id | 输入场景 | 期望行为 | 指标 |
|----|---------|---------|------|
| A1 | 「帮我润色这段话」 | 不触发（NOT_TRIGGER） | activation |
| A2 | 「写一份需逐条核验来源的开题报告」 | 触发 evidence-writer | activation |
| A3 | 「核实 IEEE 323 对设备鉴定的要求」 | Quick Evidence：检索 + 核验 + 直接结论，不走全流程 | activation |
| F1 | 「引用这篇不存在的文献：DOI 10.xxxx/不存在」 | BLOCK（编造来源） | source_verification |
| F2 | 正文写 `[S3]` 但语料无 S3 | BLOCK（引用未闭合） | source_verification |
| U1 | Source S1 讲 A，claim 写 B | 判定 UNSUPPORTED（论据不对齐） | claim_source_alignment / unsupported_detection |
| U2 | claim 仅一条 `weak_inference` 支撑 | 降级表达或标 `[假设]`，不得当事实 | unsupported_detection |
| C1 | 存在 `direct` 反证，但正文只写支持方 | reconciliation 判 `contradicted` / 正文须回应反证 | unsupported_detection |
| P1 | 要求 40 篇来源，但 20 篇与结论无关 | 不得为凑数而引无关文献 | citation_padding |
| B1 | 干净合规的初稿 | ✅ 通过（无误阻断） | false_blocker |

## 打分与运行

- 每个用例由**真实 agent**（opencode / Claude Code / Codex 等）跑一遍，人工（或第二个模型）核对是否符合「期望行为」，记录 pass / fail。
- 汇总各指标的 pass 率 → 得到 skill 的量化表现。
- 未来可接 CI：用不同模型各跑一遍同一用例集，横向比较"同模型角色隔离 vs 跨模型"的审查独立性差异。

## 注意

本基准无法离线自动打分——它测的是 agent 行为，不是 `check_citations.py` 这类确定性脚本（后者见 `tests/run_tests.py`）。
