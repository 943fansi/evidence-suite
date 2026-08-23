# Eval / Golden 套件

衡量 evidence-suite 的证据完整性行为。两类用例：

- **script 级**（`kind: "script"`）：离线自动判分，跑确定性脚本比对退出码/stdout。
- **agent 行为级**（`kind: "manual"`）：prompt injection / 摘要≠原文 / 矛盾处理 /
  论断对齐 / 幻觉——需真实 agent 运行，由**人工或第二模型**核对期望行为后回填。

## 运行

```bash
python eval/run_eval.py              # 判分 + 写 eval/report.md
python eval/run_eval.py --json       # 机器可读
python eval/run_eval.py --verbose    # 失败明细
python eval/run_eval.py --manual-results manual.json   # 回填人工打分，闭环计入报告
```

`manual.json` 形如 `{"eval-agent-001": "pass", "eval-agent-003": "fail"}`。
退出码：全部 auto 通过 → 0；任一 fail/error → 1。

## Golden 用例格式（`eval/golden/*.json`）

### script 级

```json
{
  "id": "eval-source-001",
  "dimension": "citation_closure",     // 见下方 dimensions
  "kind": "script",
  "expectation": "block",              // 人类可读期望
  "description": "…",
  "fixtures": { "draft.md": "…" },     // 写入临时目录的文件名→内容
  "extra_args": ["--academic"],        // 追加给脚本的参数（可选）
  "expect_rc": 1,                      // 期望退出码
  "expect_stdout_has": ["orphaned_s"]  // 期望 stdout 包含的片段
}
```

SSRF 用例（`dimension: ssrf_guard`）不用 fixtures，用：

```json
{ "url": "http://169.254.169.254/x", "expect_blocked": true }
```

### agent 行为级（manual）

```json
{
  "id": "eval-agent-001",
  "dimension": "prompt_injection",
  "kind": "manual",
  "expectation": "ignore",   // ignore / block / no_false_consensus …
  "description": "…",       // 含核验点
}
```

## dimensions（脚本 runner 映射）

| dimension | 脚本 | 判定 |
| --- | --- | --- |
| `citation_closure` | `check_citations.py --json` | rc + stdout 片段 |
| `source_suspect_domain` | `validate_sources.py --json` | rc + stdout 片段 |
| `source_origin` | `validate_sources.py --json` | rc + stdout 片段 |
| `superseded_source` | `validate_sources.py --json` | rc + stdout 片段 |
| `manifest_schema` | `validate_manifest.py` | rc + stdout 片段 |
| `evidence_sufficiency` | `check_evidence_sufficiency.py --json` | rc + stdout 片段 |
| `machine_auditability` | `audit_provenance.py --claims` | rc + stdout 片段 |
| `ssrf_guard` | `download_reference_files.check_url_blocked` | blocked 布尔 |

manual 维度不映射脚本：`prompt_injection` / `source_mismatch` / `contradiction_handling` /
`claim_grounding` / `hallucination`。

## 增加用例

1. 在 `eval/golden/` 放一个 `eval-<维度>-<序号>.json`（见上格式）。
2. script 级用例必须离线可判分；先本地跑 `python eval/run_eval.py --verbose` 验证。
3. 更新 `tests/run_tests.py` 的 `EvalHarnessTests` 断言计数（`passed >= N`）。

## 与 benchmarks/ 的关系

`benchmarks/README.md` 保留 18 个 agent 行为场景与量化指标（激活率/来源核验率/
充分性检出/误阻断率/灌水率），供真跑 agent 时横向对比；`eval/` 是可执行、
可判分的 golden 用例实现。
