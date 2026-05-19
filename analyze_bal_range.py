"""Render histogram + size-vs-gas line chart from a bulk-run manifest.

Consumes the JSONL manifest written by build_bal_range_bulk.py. No RPC calls —
all sizes/gas/etc. are precomputed during the build. Run this locally after
pulling the manifest back, or on the remote once the build is done.

Usage:
    python analyze_bal_range.py
    python analyze_bal_range.py --manifest reports/bal_range_manifest.jsonl
    python analyze_bal_range.py --out-dir reports/range_charts
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

project_root = Path(__file__).parent


def load_manifest(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def to_kb(b: int) -> float:
    return b / 1024


def plot_histogram(rows: list[dict], out_path: Path) -> None:
    bal = [to_kb(r["bal_snappy_bytes"]) for r in rows]
    block = [to_kb(r["block_snappy_bytes"]) for r in rows]
    combined = [a + b for a, b in zip(bal, block)]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    bins = 50
    series = [
        ("BAL (snappy)", bal, "#1f77b4"),
        ("Block excl. BAL (snappy)", block, "#ff7f0e"),
        ("BAL + Block (snappy)", combined, "#2ca02c"),
    ]
    for ax, (label, data, color) in zip(axes, series):
        ax.hist(data, bins=bins, alpha=0.85, color=color, edgecolor="black", linewidth=0.3)
        mean = sum(data) / len(data)
        p99 = sorted(data)[int(0.99 * (len(data) - 1))]
        ax.set_xlabel("Size (KB, snappy-compressed)")
        ax.set_title(f"{label}\nmean={mean:.1f} KB  p99={p99:.1f} KB  max={max(data):.1f} KB")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("Number of blocks")
    fig.suptitle(f"Size Distribution (n={len(rows)} blocks)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote histogram: {out_path}")


def plot_size_vs_gas(rows: list[dict], out_path: Path) -> None:
    rows_sorted = sorted(rows, key=lambda r: r["gas_used"])
    gas = [r["gas_used"] / 1e6 for r in rows_sorted]
    bal = [to_kb(r["bal_snappy_bytes"]) for r in rows_sorted]
    block = [to_kb(r["block_snappy_bytes"]) for r in rows_sorted]
    combined = [a + b for a, b in zip(bal, block)]

    fig, ax = plt.subplots(figsize=(11, 6))
    # With many points, use thin lines without markers.
    marker = "" if len(rows) > 500 else "o"
    ax.plot(gas, bal, marker=marker, linewidth=0.8, alpha=0.7,
            label="BAL (snappy)", color="#1f77b4")
    ax.plot(gas, block, marker=marker, linewidth=0.8, alpha=0.7,
            label="Block excl. BAL (snappy)", color="#ff7f0e")
    ax.plot(gas, combined, marker=marker, linewidth=0.8, alpha=0.7,
            label="BAL + Block (snappy)", color="#2ca02c")
    ax.set_xlabel("Gas used (millions)")
    ax.set_ylabel("Size (KB, snappy-compressed)")
    ax.set_title(f"Size vs Gas Used (blocks sorted by gas, n={len(rows)})")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote line chart: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=project_root / "reports" / "bal_range_manifest.jsonl")
    parser.add_argument("--out-dir", type=Path,
                        default=project_root / "reports")
    args = parser.parse_args()

    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")

    rows = load_manifest(args.manifest)
    if not rows:
        raise SystemExit("Manifest is empty.")
    print(f"Loaded {len(rows):,} rows from {args.manifest}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    plot_histogram(rows, args.out_dir / "bal_range_histogram.png")
    plot_size_vs_gas(rows, args.out_dir / "bal_range_size_vs_gas.png")

    bal_mean = sum(r["bal_snappy_bytes"] for r in rows) / len(rows) / 1024
    block_mean = sum(r["block_snappy_bytes"] for r in rows) / len(rows) / 1024
    print(f"\nAvg compressed BAL:   {bal_mean:7.2f} KB")
    print(f"Avg compressed block: {block_mean:7.2f} KB")
    print(f"BAL is {bal_mean/block_mean*100:.1f}% of block size on average")


if __name__ == "__main__":
    main()
