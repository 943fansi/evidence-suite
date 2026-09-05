#!/usr/bin/env python3
r"""evidence-suite 能力边界常量与引用归一化工具.

集中管理「套件能力边界」声明（README / manifest / 导出报告三处共用同一文本），
以及 locator 引用片段的归一化哈希工具（PR-10：排版差异不再导致 quote_hash 失效）。

边界声明原则（PR-01）：
  - 套件只校验「引用的原文是否支持当前 Claim」，不检测来源网页/论文本身真伪。
  - quote_hash / 页码 locator 会因 PDF 版本、扫描件、网页改版而失效。
  - 反证检索找不到 ≠ 论断正确。
"""

from __future__ import annotations

import hashlib
import re

BOUNDARY_NOTICE = (
    "边界声明：本报告由 evidence-suite 校验「引用原文是否支持论断」，"
    "不保证来源网页/论文内容本身真实；quote_hash/页码等 locator 可能因 PDF 版本、"
    "扫描件或网页改版失效；未找到反证不等于论断正确。"
)

REVIEW_KIND_LABELS = {
    "ai-internal": "同模型角色隔离（内部红队，不等同独立评审）",
    "ai-cross-model": "跨模型独立审查（共享 context/evidence 时仍存在相关失败风险）",
    "human-expert": "人类专家评审",
}


def review_kind_label(review_kind: str) -> str:
    """Return the human-readable label for a review_kind value."""
    return REVIEW_KIND_LABELS.get(review_kind, review_kind or "未知")


_WS = re.compile(r"[\s\u00a0\u3000]+")


def normalize_quote(text: str) -> str:
    """Normalize a source quote fragment for stable hashing.

    Collapses all whitespace (including NBSP/full-width space, newlines,
    tabs) to a single ASCII space and strips leading/trailing whitespace.
    Layout-only differences (line wraps, indentation) therefore produce the
    same hash.
    """
    return _WS.sub(" ", text or "").strip()


def quote_sha256(text: str) -> str:
    """Return 'sha256:<hex>' of the normalized quote fragment.

    Prefix keeps the digest self-describing and lets downstream tooling
    distinguish it from plain strings.
    """
    return "sha256:" + hashlib.sha256(normalize_quote(text).encode("utf-8")).hexdigest()
