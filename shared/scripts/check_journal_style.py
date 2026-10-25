#!/usr/bin/env python3
r"""Journal paper style scorecard (期刊文风评分卡, w5/r4 期刊专项).

Distilled from ~50 real CN journal papers on cable aging / condition monitoring
(top tier: 《电力工程技术》2024 TFDR, 9 pages / 26 bilingual refs / 10 figs;
mid tier: 《绝缘材料》2016, 4 pages / 14 refs). Measures how close a draft is to
that genre's conventions — deterministic items are machine-scored (0/1/2 each),
rhetorical items are printed as a manual checklist for human/LLM review.

Scored items (top tier defaults; --tier mid relaxes thresholds):
  S1  摘要字数 150–350        S2  摘要四要素（目的/方法/量化结果/结论）
  S3  关键词 5–6 分号分隔      S4  中图分类号+文献标志码
  S5  英文题名/Abstract/Key words
  S6  「0 引言」编号           S7  正文章节编号连续 1..N
  S8  末章为结论/结语          S9  结论编号式 (1)(2)(3)
  S10 参考文献数量 ≥20         S11 文献类型标记 [J]/[S]/[D]… 覆盖率
  S12 中文文献双语对照率       S13 图/表顺次编号
  S14 图题中英双语             S15 公式编号 + 「式中：」符号说明
  S16 禁用词（众所周知/我们/摘要自我拔高）
  S17 正文字数 ≥8 000

Exit codes: 0 score ≥ --threshold and no hard item at 0; 1 otherwise; 2 usage.

Usage:
  python scripts/check_journal_style.py 11_定稿.md                 # top tier
  python scripts/check_journal_style.py 08_初稿.md --tier mid
  python scripts/check_journal_style.py paper.md --min-refs 12 --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TIERS = {
    "top": {"min_refs": 20, "min_chars": 8000, "bilingual_ratio": 0.5,
            "need_figs": True, "need_eqs": True},
    "mid": {"min_refs": 10, "min_chars": 6000, "bilingual_ratio": 0.2,
            "need_figs": False, "need_eqs": False},
}
HARD_ITEMS = ("S1", "S3", "S6", "S8", "S10", "S11", "S17")  # 结构性硬项，0 分即 fail
CJK = re.compile(r"[\u4e00-\u9fff]")
REF_TYPE_TAG = re.compile(r"\[(?:J|M|S|D|C|R|N|EB|DB|CP|A)/?[^\]]*\]")
EQUATION_NUM = re.compile(r"[（(](\d{1,2})[)）]\s*(?:$|[^)）])", re.M)


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gb18030", errors="replace")


def split_sections(text: str) -> dict:
    """Return abstract / keywords / body / conclusion / references blocks.

    Front matter (title/authors/中图分类号) lands in "front"; the English
    abstract block lands in "abs_en" so 中文摘要字数 is not inflated.
    """
    lines = text.splitlines()
    blocks: dict[str, list[str]] = {k: [] for k in
                                    ("front", "abs", "kw", "abs_en", "kw_en", "body", "concl", "refs")}
    mode = "front"
    marker = re.compile(
        r"^[#*\s]{0,10}(摘\s*要|Abstract\s*[:：]?|关\s*键\s*词|Key\s*words|"
        r"参\s*考\s*文\s*献|References|【参\s*考\s*文\s*献】)\*{0,2}\s*[:：]?\s*", re.I)
    heading = re.compile(r"^#{1,6}\s")
    for ln in lines:
        s = ln.strip()
        m = marker.match(s)
        if m:
            head = re.sub(r"[\s:：]", "", m.group(1)).lower()
            rest = s[m.end():]
            mode = {"摘要": "abs", "abstract": "abs_en", "关键词": "kw",
                    "keywords": "kw_en"}.get(head, "refs")
            if rest:
                blocks[mode].append(rest)
            continue
        if heading.match(s):
            if re.match(r"^#{2,6}\s", s) and mode in ("front", "abs_en", "kw_en", "kw", "abs"):
                mode = "body"
            if mode == "body" and re.match(r"^#{1,6}\s*\d+(\.\d+)*\s*.*(结论|结语)", s):
                mode = "concl"
        if re.match(r"^(中图分类号|文献[标志标识码别])", s):
            blocks["front"].append(s)
            continue
        if mode in ("kw", "kw_en") and not ("；" in s or ";" in s) and len(s) > 40:
            mode = "front" if "引言" not in s else "body"
        if mode == "abs" and not CJK.search(s) and len(re.findall(r"[A-Za-z]", s)) > 30:
            mode = "abs_en"
        blocks[mode].append(ln)
    body_joined = "\n".join(blocks["body"])
    body_joined = re.split(r"^#{1,6}\s*附\s*录.*$", body_joined, flags=re.M)[0]
    out = {k: "\n".join(v) for k, v in blocks.items()}
    out["body"] = body_joined
    return out


def nsp(s: str) -> int:
    """Non-whitespace char count (CJK counts as 1 each — 中文正文字数口径)."""
    return len(re.sub(r"\s", "", s))


def ref_entries(refs_block: str) -> list[str]:
    """Reference entries; continuation lines (bilingual EN translations, wraps)
    are merged into the preceding entry so bilingual pairing is detectable."""
    raw = [ln for ln in refs_block.splitlines() if ln.strip()]
    out: list[str] = []
    new_entry = re.compile(r"^\[?\d+\]?[\s.、]|^\[S[-_]?\d+\]")
    for ln in raw:
        s = ln.strip().lstrip("#*- ").strip()
        if new_entry.match(s) or not out:
            out.append(s)
        else:  # 缩进续行：双语对照英文/换行包裹
            out[-1] += " " + s
    return out


def score(draft: str, tier: str, min_refs: int, min_chars: int) -> tuple[list[dict], list[str]]:
    cfg = TIERS[tier]
    sec = split_sections(draft)
    abstract = sec["abs"]
    body = sec["body"]
    concl = sec["concl"]
    refs = ref_entries(sec["refs"])
    items: list[dict] = []

    def add(sid: str, name: str, sc: int, note: str) -> None:
        items.append({"id": sid, "item": name, "score": sc, "max": 2, "note": note})

    # S1 摘要字数（中文摘要，按 CJK 字符计）
    n = len(CJK.findall(abstract))
    add("S1", "摘要字数(150–350)", 2 if 150 <= n <= 350 else 1 if 100 <= n < 150 or 350 < n <= 450 else 0,
        f"{n} 字")
    # S2 摘要四要素
    purpose = bool(re.search(r"针对|为了|为明确|为解决|旨在", abstract))
    method = bool(re.search(r"提出|构建|建立|采用|基于|设计|开发", abstract))
    result = bool(re.search(r"(\d+(\.\d+)?\s*[%％])|(≤|≥|误差|精度.{0,6}\d|下降\s*\d|提升\s*\d|降低\s*\d)", abstract))
    concl_w = bool(re.search(r"表明|验证|证实|结果|可得出|可用于", abstract))
    got = sum([purpose, method, result, concl_w])
    add("S2", "摘要四要素", 2 if got == 4 else 1 if got >= 2 else 0,
        f"目的{int(purpose)}/方法{int(method)}/量化结果{int(result)}/结论{int(concl_w)}")
    # S3 关键词（仅中文关键词行）
    kw = [k.strip() for k in re.split(r"[;；]", sec["kw"]) if k.strip() and CJK.search(k)]
    add("S3", "关键词5~6个", 2 if 5 <= len(kw) <= 6 else 1 if 3 <= len(kw) <= 8 else 0, f"{len(kw)} 个")
    # S4 中图分类号 + 文献标志码
    clc = bool(re.search(r"中图分类号", draft))
    doc_code = bool(re.search(r"文献标志码|文献标识码", draft))
    add("S4", "中图分类号+文献标志码", clc + doc_code, f"分类号{int(clc)}/标志码{int(doc_code)}")
    # S5 英文块
    has_abs_en = bool(sec["abs_en"].strip())
    has_kw_en = bool(sec["kw_en"].strip())
    has_title_en = bool(re.search(r"^[#*\s]{0,6}\**[A-Z][A-Za-z0-9,\-() ]{15,}\**\s*$", draft, re.M))
    n_en = sum([has_abs_en, has_kw_en, has_title_en])
    add("S5", "英文题名/Abstract/Key words", 2 if n_en == 3 else 1 if n_en == 2 else 0,
        f"题名{int(has_title_en)}/Abstract{int(has_abs_en)}/Keywords{int(has_kw_en)}")
    # S6 0 引言
    zero_intro = bool(re.search(r"^#{1,6}\s*0\s*引\s*言", draft, re.M))
    plain_intro = bool(re.search(r"^#{1,6}\s*引\s*言", draft, re.M))
    add("S6", "「0 引言」", 2 if zero_intro else 1 if plain_intro else 0,
        "编号从0开始" if zero_intro else "引言未编号" if plain_intro else "缺引言")
    # S7 章节编号连续（仅一级标题：## N 空格；引言的 0 不计入）
    nums = [int(m.group(1)) for m in re.finditer(r"^##\s*(\d+)\s+[^\d.]", draft, re.M)
            if int(m.group(1)) > 0]
    seq = nums == list(range(1, len(nums) + 1)) if nums else False
    add("S7", "章节编号连续1..N", 2 if seq and len(nums) >= 2 else 1 if nums else 0,
        f"{nums}")
    # S8 末章结论
    add("S8", "末章为结论/结语", 2 if re.search(r"结论|结语", (re.findall(r"^##\s*\d+[\s、.].*$", draft, re.M) or [""])[-1]) else 0,
        "")
    # S9 结论编号式
    pts = re.findall(r"[（(](\d)[)）]|([①②③④⑤⑥⑦])", concl)
    add("S9", "结论编号式(1)(2)(3)", 2 if len(pts) >= 3 else 1 if len(pts) >= 1 else 0, f"{len(pts)} 条")
    # S10 文献数量
    need = min_refs or cfg["min_refs"]
    add("S10", f"参考文献≥{need}", 2 if len(refs) >= need else 1 if len(refs) >= 0.7 * need else 0,
        f"{len(refs)} 条")
    # S11 类型标记
    tagged = sum(1 for r in refs if REF_TYPE_TAG.search(r))
    ratio = tagged / len(refs) if refs else 0
    add("S11", "文献类型标记[J]/[S]…", 2 if ratio >= 0.9 else 1 if ratio >= 0.6 else 0,
        f"{tagged}/{len(refs)}" if refs else "无文献")
    # S12 双语文献（中文条目附英文对照）
    cn_refs = [r for r in refs if CJK.search(r)]
    bilingual = [r for r in cn_refs if re.search(r"[\u4e00-\u9fff].*[.]\s*[A-Z][a-z]+.{20,}", r)
                 and re.search(r"[A-Za-z]{4,}[\s,:].*[A-Za-z]{4,}", r.split("—")[-1] if "—" in r else r)]
    br = len(bilingual) / len(cn_refs) if cn_refs else 0
    add("S12", "中文文献双语对照", 2 if br >= cfg["bilingual_ratio"] else 1 if br >= 0.1 else 0,
        f"{len(bilingual)}/{len(cn_refs)}")
    # S13 图表顺次
    figs = [int(m) for m in re.findall(r"图\s*(\d+)", draft)]
    tabs = [int(m) for m in re.findall(r"表\s*(\d+)", draft)]
    def seq_ok(xs: list[int]) -> bool:
        u = list(dict.fromkeys(xs))
        return u == list(range(1, len(u) + 1))
    fig_ok, tab_ok = seq_ok(figs), seq_ok(tabs)
    has_fig = bool(figs) if cfg["need_figs"] else True
    add("S13", "图/表顺次编号", 2 if fig_ok and tab_ok and has_fig else 1 if fig_ok or tab_ok else 0,
        f"图{sorted(set(figs))}表{sorted(set(tabs))}")
    # S14 图题双语（图N 行与紧随的 Fig.N 行配对）
    raw_lines = [l.strip() for l in draft.splitlines() if l.strip()]
    captions = []
    for idx, l in enumerate(raw_lines):
        if re.match(r"^图\s*\d+", l):
            nxt = raw_lines[idx + 1] if idx + 1 < len(raw_lines) else ""
            captions.append(l + ("\n" + nxt if re.match(r"^(Fig|表|Tab)", nxt, re.I) else ""))
    bicap = [c for c in captions if CJK.search(c) and re.search(r"Fig\.?\s*\d", c, re.I)]
    add("S14", "图题中英双语", 2 if captions and len(bicap) / len(captions) >= 0.8 else
        1 if bicap else (0 if cfg["need_figs"] else 2), f"{len(bicap)}/{len(captions)}")
    # S15 公式与式中
    eq_nums = {int(m.group(1)) for m in EQUATION_NUM.finditer(body)}
    eq_seq = sorted(eq_nums) == list(range(1, len(eq_nums) + 1)) if eq_nums else False
    zhongshi = len(re.findall(r"式\s*中\s*[:：]", draft))
    if eq_nums and eq_seq:
        add("S15", "公式编号+式中说明", 2 if zhongshi >= max(1, len(eq_nums) // 2) else 1, f"式({len(eq_nums)})，式中×{zhongshi}")
    elif eq_nums:
        add("S15", "公式编号+式中说明", 1, "公式编号不连续")
    else:
        add("S15", "公式编号+式中说明", 0 if cfg["need_eqs"] else 2, "无公式")
    # S16 禁用词
    hits = []
    if re.search(r"众所周知", draft):
        hits.append("众所周知")
    if re.search(r"我们", re.sub(r"参考文献[\s\S]*", "", draft)):
        hits.append("我们")
    if re.search(r"首次|填补空白|国际领先", abstract):
        hits.append("摘要自我拔高")
    add("S16", "禁用词", 2 - min(2, len(hits)), "、".join(hits) or "无")
    # S17 正文字数
    nb = nsp(body) + nsp(concl)
    need_c = min_chars or cfg["min_chars"]
    add("S17", f"正文字数≥{need_c}", 2 if nb >= need_c else 1 if nb >= 0.6 * need_c else 0, f"{nb} 字")

    manual = [
        "引言逐篇评述：对关键文献逐篇说明做法并指出不足（「但…难以应用」式收束）",
        "引言修辞链：工程重要性→老化机理→分组引用[1-4]→评述指不足→「本文/文中提出…」",
        "设备与参数：仪器型号+关键参数逐项写出（如「探针移动速度5.08 mm/min」）",
        "第三人称学术语气（本文/试验结果表明…），无口语化表达",
        "缩写首现给中英文全称（如「时频域反射（time-frequency domain reflectometry, TFDR）」）",
        "摘要量化表述与正文验证章节一一对应",
        "图表在正文中被引用（「如图1所示」）且顺序与首次引用一致",
    ]
    return items, manual


def main() -> int:
    _ensure_utf8_streams()
    ap = argparse.ArgumentParser(description="Journal paper style scorecard (期刊文风评分卡)")
    ap.add_argument("file", type=Path, help="draft .md/.txt (工作稿 [Sx] 版或投稿 [n] 版)")
    ap.add_argument("--tier", choices=("top", "mid"), default="top",
                    help="档次阈值（top=高档期刊 默认; mid=中档）")
    ap.add_argument("--min-refs", type=int, default=0, help="覆盖文献数量下限（0=用档位默认）")
    ap.add_argument("--min-chars", type=int, default=0, help="覆盖正文字数下限（0=用档位默认）")
    ap.add_argument("--threshold", type=float, default=0.85, help="通过分数线（得分率）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2
    draft = read_text(args.file)
    items, manual = score(draft, args.tier, args.min_refs, args.min_chars)

    total = sum(i["score"] for i in items)
    full = sum(i["max"] for i in items)
    hard_fail = [i["id"] for i in items if i["id"] in HARD_ITEMS and i["score"] == 0]
    ratio = total / full if full else 0.0
    ok = ratio >= args.threshold and not hard_fail

    if args.json:
        print(json.dumps({"file": str(args.file), "tier": args.tier, "score": total,
                          "full": full, "ratio": round(ratio, 4), "pass": ok,
                          "hard_fail": hard_fail, "items": items,
                          "manual_checklist": manual}, ensure_ascii=False, indent=1))
    else:
        print(f"期刊文风评分卡  {args.file}  (tier={args.tier})")
        print("-" * 72)
        for i in items:
            mark = "✅" if i["score"] == i["max"] else ("⚠️ " if i["score"] > 0 else "❌")
            hard = " [硬项]" if i["id"] in HARD_ITEMS else ""
            print(f"{mark} {i['id']:>3} {i['item']}{hard:<5}  {i['score']}/{i['max']}  {i['note']}")
        print("-" * 72)
        print(f"总分 {total}/{full}（{ratio:.0%}）  硬项0分: {hard_fail or '无'}  "
              f"{'✅ PASS' if ok else '❌ FAIL'}（线 {args.threshold:.0%}）")
        print("\n人工复核清单（主观项，逐条对照参考论文核对）:")
        for m in manual:
            print(f"  [ ] {m}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
