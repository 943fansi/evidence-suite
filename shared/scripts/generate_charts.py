#!/usr/bin/env python3
"""Generate publication-quality charts driven by a JSON data file.

All chart data (labels, values, sources, colors, titles, annotations) lives in
a JSON file — by default `sample_chart_data.json` next to this script (a sample
for a preschool children's sports-thesis). To reuse for another topic, copy the
sample, edit its numbers, and pass `--data path/to/my_chart_data.json`.

Supported chart types (per-entry `type`):
  horizontal_bar   — effect-size comparison (labeled bars + reference line)
  line_area        — development trajectory with stage bands + annotation
  grouped_bar      — grouped bars with per-series labels

Validation: each chart entry must carry the required keys for its type
(see `_REQUIRED`); a missing key raises a ValueError naming the chart id, so
editing the data file for another topic fails loudly instead of silently
producing a wrong chart.

Usage:
  python3 generate_charts.py -o figures/
  python3 generate_charts.py -o figures/ --data my_chart_data.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# matplotlib / numpy are imported lazily in _setup_plotlib() so that
# `--help` and data validation work even without the optional deps installed.

# ---------------------------------------------------------------------------
# Chinese font setup — fall back gracefully if no CJK font is found
# (performed lazily inside _setup_plotlib)
# ---------------------------------------------------------------------------

CJK_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",       # Microsoft YaHei
    "C:/Windows/Fonts/simhei.ttf",     # SimHei
    "C:/Windows/Fonts/simsun.ttc",     # SimSun
]

_cjk_registered = False
np = None  # type: ignore[assignment]
plt = None  # type: ignore[assignment]
fm = None  # type: ignore[assignment]


def _setup_plotlib() -> None:
    """Import matplotlib/numpy and configure CJK fonts. Called from main()."""
    global _cjk_registered, np, plt, fm
    import matplotlib  # noqa: PLC0415
    import matplotlib.font_manager as font_manager  # noqa: PLC0415
    import matplotlib.pyplot as pyplot  # noqa: PLC0415
    import numpy  # noqa: PLC0415

    np = numpy
    plt = pyplot
    fm = font_manager

    for _path in CJK_CANDIDATES:
        if os.path.exists(_path):
            try:
                fm.fontManager.addfont(_path)
                _prop = fm.FontProperties(fname=_path)
                _family = _prop.get_name()
                plt.rcParams["font.family"] = _family
                _cjk_registered = True
                break
            except Exception:
                continue

    if not _cjk_registered:
        # Use English labels as ultimate fallback
        print("Warning: No CJK font found. Charts will use English labels.", file=sys.stderr)

    matplotlib.rcParams["axes.unicode_minus"] = False  # Prevent minus signs breaking with CJK fonts
    matplotlib.rcParams["figure.dpi"] = 150
    matplotlib.rcParams["savefig.dpi"] = 300
    matplotlib.rcParams["savefig.bbox"] = "tight"


# ---------------------------------------------------------------------------
# Data schema validation
# ---------------------------------------------------------------------------

_REQUIRED = {
    "horizontal_bar": {"filename", "title", "xlabel", "labels", "values", "categories", "category_colors"},
    "line_area": {"filename", "title", "xlabel", "ylabel", "x", "series", "xlim", "ylim"},
    "grouped_bar": {"filename", "title", "standards", "groups", "series_labels", "colors", "ylabel"},
}


def _require(chart_id: str, spec: dict) -> None:
    required = _REQUIRED.get(spec.get("type"))
    if not required:
        raise ValueError(f"[{chart_id}] unknown chart type: {spec.get('type')!r}")
    missing = required - set(spec)
    if missing:
        raise ValueError(f"[{chart_id}] missing required keys for "
                         f"{spec['type']}: {sorted(missing)}")


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _safe_label(key: str, en_map: dict | None) -> str:
    """Return the Chinese label if CJK font is available, otherwise English fallback."""
    if _cjk_registered:
        return key
    return (en_map or {}).get(key, key)


def _clean_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


# ===================================================================
# FIGURE 1: Effect Size Comparison (Horizontal Bar Chart)
# ===================================================================

def fig_effect_sizes(out_dir: Path, spec: dict) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))

    labels = spec["labels"]
    values = spec["values"]
    metrics = spec.get("metrics", ["d"] * len(values))
    sources = spec.get("sources", [""] * len(values))
    categories = spec["categories"]
    colors = spec["category_colors"]

    bar_colors = [colors[c] for c in categories]

    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values, color=bar_colors, edgecolor="white", height=0.55)

    # Annotate each bar with value + source
    for i, (v, m, s) in enumerate(zip(values, metrics, sources)):
        ax.text(v + 0.02, i, f"{m}={v:.2f}  [{s}]", va="center", fontsize=8, color="#333333")

    # Reference line (e.g. d=0.5 medium effect)
    ref = spec.get("reference_line")
    if ref:
        ax.axvline(x=ref["value"], color="#999999", linestyle="--", linewidth=0.8)
        ax.text(ref["value"] + 0.01, len(labels) - 0.3, _safe_label(ref["label"], spec.get("en_labels")),
                fontsize=7, color="#999999")

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel(spec["xlabel"], fontsize=10)
    ax.set_xlim(0, spec.get("xlim", 1.2))
    ax.invert_yaxis()
    _clean_axis(ax)

    # Legend
    legend_patches = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    ax.legend(legend_patches, [_safe_label(k, spec.get("en_labels")) for k in colors.keys()],
              loc="lower right", fontsize=8, frameon=False)

    ax.set_title(spec["title"], fontsize=12, fontweight="bold", pad=15)

    fig.tight_layout()
    fig.savefig(out_dir / spec["filename"], dpi=300)
    plt.close(fig)
    print(f"  Saved: {spec['filename']}")


# ===================================================================
# FIGURE 2: Development Trajectory by Age (Line + Stage Bands)
# ===================================================================

def fig_trajectory(out_dir: Path, spec: dict) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))

    x = np.asarray(spec["x"], dtype=float)
    en = spec.get("en_labels")

    for s in spec["series"]:
        ax.plot(x, s["values"], s.get("marker", "o") + "-", color=s["color"],
                linewidth=2, markersize=7, label=_safe_label(s["label"], en))

    # Stage background shading
    for st in spec.get("stages", []):
        ax.axvspan(st["xmin"], st["xmax"], alpha=0.08, color=st["color"],
                   label=_safe_label(st["label"], en))

    # Key window annotation
    ann = spec.get("annotation")
    if ann:
        ax.annotate(_safe_label(ann["text"], en), xy=(ann["x"], ann["y"]),
                    fontsize=9, color="#C00000", fontweight="bold", ha="center",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor="#C00000", alpha=0.8))

    ax.set_xlabel(spec["xlabel"], fontsize=10)
    ax.set_ylabel(spec["ylabel"], fontsize=10)
    ax.set_xticks(spec.get("x_ticks", x))
    ax.set_xlim(*spec["xlim"])
    ax.set_ylim(*spec["ylim"])

    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    _clean_axis(ax)

    title = spec["title"]
    if spec.get("subtitle"):
        title = title + "\n" + spec["subtitle"]
    ax.set_title(title, fontsize=11, fontweight="bold", pad=12)

    fig.tight_layout()
    fig.savefig(out_dir / spec["filename"], dpi=300)
    plt.close(fig)
    print(f"  Saved: {spec['filename']}")


# ===================================================================
# FIGURE 3: International Guideline Comparison (Grouped Bar)
# ===================================================================

def fig_grouped_bars(out_dir: Path, spec: dict) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))

    standards = spec["standards"]
    groups = spec["groups"]  # dict key -> list of values (required, validated by _REQUIRED)
    series_labels = spec["series_labels"]
    colors = spec["colors"]
    en = spec.get("en_labels")
    sources = spec.get("sources", [])

    x = np.arange(len(standards))
    width = 0.8 / max(1, len(groups))

    bar_groups = []
    for i, (key, values) in enumerate(groups.items()):
        offset = (i - (len(groups) - 1) / 2) * width
        bars = ax.bar(x + offset, values, width, color=colors[key], edgecolor="white",
                      label=_safe_label(series_labels[key], en))
        bar_groups.append((key, bars))

    # Annotate bars
    for key, bars in bar_groups:
        for j, bar in enumerate(bars):
            src = sources[j] if j < len(sources) else ""
            suffix = f" {src}" if src else ""
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                    f"{int(bar.get_height())}{suffix}", ha="center", va="bottom",
                    fontsize=7, color="#333333")

    ax.set_xticks(x)
    ax.set_xticklabels(standards, fontsize=9)
    ax.set_ylabel(spec["ylabel"], fontsize=10)
    ax.set_ylim(0, spec.get("ylim", 220))

    note = spec.get("note")
    if note:
        ax.annotate(_safe_label(note["text"], en), xy=(note["x"], note.get("y", 65)),
                    fontsize=7, color="#666666", ha="center", xytext=(note["x"], note.get("target_y", 100)),
                    arrowprops=dict(arrowstyle="->", color="#999999", lw=0.8))

    ax.legend(loc="upper right", fontsize=8, frameon=False)
    _clean_axis(ax)

    title = spec["title"]
    if spec.get("subtitle"):
        title = title + "\n" + spec["subtitle"]
    ax.set_title(title, fontsize=11, fontweight="bold", pad=12)

    fig.tight_layout()
    fig.savefig(out_dir / spec["filename"], dpi=300)
    plt.close(fig)
    print(f"  Saved: {spec['filename']}")


# ===================================================================
# CLI
# ===================================================================

_PLOTTERS = {
    "horizontal_bar": fig_effect_sizes,
    "line_area": fig_trajectory,
    "grouped_bar": fig_grouped_bars,
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out-dir", type=Path, default=Path("figures"),
                        help="Output directory for chart PNG files.")
    parser.add_argument("--data", type=Path,
                        default=Path(__file__).resolve().parent / "sample_chart_data.json",
                        help="Chart data JSON (see sample_chart_data.json for schema).")
    args = parser.parse_args(argv)

    if not args.data.exists():
        print(f"ERROR: data file not found: {args.data}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(args.data.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot parse data file {args.data}: {exc}", file=sys.stderr)
        return 2

    charts = payload.get("charts")
    if not isinstance(charts, dict) or not charts:
        print(f"ERROR: data file lacks a non-empty 'charts' object", file=sys.stderr)
        return 2

    # Schema validation FIRST (promised ValueError) so that an invalid data file
    # fails with a clear message even when matplotlib/numpy are not installed.
    for chart_id, spec in charts.items():
        try:
            _require(chart_id, spec)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    _setup_plotlib()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating charts → {args.out_dir}/  (data: {args.data.name})")
    for chart_id, spec in charts.items():
        plotter = _PLOTTERS.get(spec["type"])
        plotter(args.out_dir, spec)
    print(f"Done: {len(charts)} charts generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))