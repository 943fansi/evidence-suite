## 变更内容

（这段是给维护者的简洁摘要，中文）

- [ ] 对应 PR 改进提纲编号（docs/roadmap.md 中的 PR-XX），或说明不在提纲内

## PR 检查清单（必填）

- [ ] `python tests/run_tests.py` 全绿（含新增用例）
- [ ] `python eval/run_eval.py` script 级 0 fail
- [ ] 未引入非白名单脚本执行 / 未放宽安全约束（SSRF、路径、大小上限）
- [ ] 契约变更（`shared/schemas/*.schema.json` / `validate_manifest.py`）已递增 `schema_version`，提供 `migrate_manifest.py` 迁移（如需），并更新 `examples/quickstart/expected/`
- [ ] 新增/修改脚本时更新了 `SECURITY.md` 白名单表（如涉及联网/写盘）与 `THREAT_MODEL.md` 对应条目
- [ ] `CHANGELOG.md` 已记录
- [ ] README / 术语速查 `shared/references/glossary.md` 已同步（如涉及枚举取值）

## 验证方式

```bash
python tests/run_tests.py
python eval/run_eval.py
```

## 需要评审者重点确认

（改动有安全/契约影响时必填：为什么安全边界没被放宽、迁移为什么是幂等的、旧 manifest 会怎样）
