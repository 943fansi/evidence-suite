# Anti-Marketing & Narrative Detection Rules

Use this reference during Stage 6 (Self-Review) to detect inflated language and hidden narratives.

## I. Trigger Words (反营销触发词)

These words signal marketing language rather than evidence-bound writing. When detected, force one of:
- **Give evidence**: provide the specific data/source behind the claim
- **Downgrade expression**: replace with a quantified, bounded alternative

### High Severity (severity: critical)

| 触发词 | 降级示例 | 说明 |
|--------|---------|------|
| 国际领先 | →"在以下指标上达到国际已报道水平：[指标1] [指标2] [Sx]" | 需要benchmark数据 |
| 填补空白 | →"现有文献中未发现对X问题的Y方法论研究，本项目将尝试...(需验证)[Gx]" | 需要文献检索证据 |
| 革命性突破 | → 删除或改为具体的性能提升数据 | 必须量化 |
| 颠覆性 | → 删除或改为具体的替代方案对比 | 必须对比 |
| 首创 | →"据检索[X范围]内未见同类方法报道[Sx]，但以下相关方法存在：[Sy]" | 缩小范围 |
| 开辟新领域 | → 删除或在严格限定下使用 | 几乎无法验证 |
| 划时代 | → 删除 | 无法验证 |
| 根本性解决 | →"可将X问题从Y水平改善至Z水平[Sx]" | 必须量化 |

### Medium Severity (severity: high)

| 触发词 | 降级示例 |
|--------|---------|
| 重大意义 | →"意义在于：...(具体机制)，体现在X群体面临Y问题的解决路径上[Sx]" |
| 广阔前景 | →"在X条件下，若Y假设成立，可应用于Z领域[假设]，规模受限于A约束" |
| 显著提升 | →"在实验条件下，X指标提高Y%[Sx]；在Z条件下效果未验证[待验证]" |
| 极大改善 | → "X指标从A改善至B[Sx]，改善幅度C%，适用条件为D" |
| 突破瓶颈 | →"突破了X瓶颈，具体表现为将Y指标从A提升至B[Sx]" |
| 完美解决 | → 禁止使用，替换为"在X条件下对Y问题提供Z改进方案" |
| 必将推动 | → 禁止使用，替换为"若X条件成立，可能对Y领域产生Z影响[假设]" |

### Low Severity (severity: medium)

| 触发词 | 降级策略 |
|--------|---------|
| 具有重要意义 | 提供具体意义而非模板表述 |
| 有效促进 | 量化促进效果 |
| 明显提高 | 量化提升幅度 |

## II. Downgrade Templates (降级表达模板)

### Without Evidence → With Evidence

```
Original:  本方案将显著提升设备可靠性。
Downgrade: 在实验条件下，本方案将故障检出率从 82% 提高至 94% [Sx]。
           在工业现场条件下的表现尚未验证 [待验证]。
```

### Without Scope → With Scope

```
Original:  本项目具有广阔应用前景。
Downgrade: 本项目适用于 X 类场景（占总市场 Y%），
           对 Z 类场景的适用性需进一步验证 [待验证]。
```

## III. Narrative Pattern Detection (叙事检测)

### Recognized Narrative Patterns

| Pattern ID | 结构 | 示例 | risk_level |
|------------|------|------|------------|
| `N1: Hero's Journey` | 行业存在痛点 → 本项目解决痛点 → 未来广泛应用 | 传统方法不足[Sx] → 本项目创新方案 → 展望产业升级 | high |
| `N2: Gap Slippage` | 事实A(有证据) → 推断B(弱证据) → 结论C(无证据) | 市场增长[Sx] → 本领域必然受益(无) → 项目价值巨大(无) | critical |
| `N3: Future Certainty` | 将假设/预期写成确定事实 | 项目完成后将形成新产业(→事实是:项目尚在计划阶段) | high |
| `N4: Single Solution` | 将一种方案写成唯一方案 | 只有本项目的方法能解决X(→事实是:可能存在其他路径) | medium |

### Detection Rules

When reviewing draft, scan for:

1. **N2: Gap Slippage** — most common in market/impact sections
   - Signal: strong `[Sx]` on observation, no citation on conclusion
   - Action: mark the conclusion as `[假设]` or `type: narrative`

2. **N1: Hero's Journey** — most common in significance/background
   - Signal: "传统方法" + "本项目" + "未来/前景/趋势" in proximity
   - Action: break the journey, insert counter-evidence, add scope constraints

3. **N3: Future Certainty** — most common in expected outcomes
   - Signal: future tense + absolute language + no "if" clause
   - Action: prefix with "在X条件成立的前提下" or add `[假设]`

4. **N4: Single Solution** — most common in technical route
   - Signal: "只有"/"唯一"/"必须" + no comparison table
   - Action: add alternative approach comparison or explain why alternatives are excluded

### Narrative Flagging Format in Review

```markdown
| 位置 | Pattern | 当前表述 | narrative_risk | 建议 |
|------|---------|---------|---------------|------|
| §3.2 | N2: Gap Slippage | "市场增长→项目价值" | critical | Observation有Sx支撑但Conclusion无，标记为[假设] |
| §1.1 | N1: Hero's Journey | "传统不足→本项目→广泛应用" | high | 插入反方证据[S5]，添加应用边界条件 |
```

## IV. Quality Gate Rule

After review, if any claim:
- Uses a high-severity trigger word **without** accompanying evidence → **block** finalization
- Contains a detected narrative pattern of risk_level critical → **block** finalization
- Uses a medium-severity trigger word → flag for downgrade but can proceed

The anti-marketing scan is not a style suggestion — it is a **content integrity check**.

## V. Token Budget

This file (~100 lines) is loaded on demand in Stage 6 (Self-Review) only.
