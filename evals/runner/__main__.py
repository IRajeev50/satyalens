"""CLI: uv run python -m evals.runner [--seed PATH] [--out-dir DIR] [--db-url URL] [--limit N]

Runs a gold set through the live pipeline, computes the METRICS.md tables and
writes reports. Exit code 1 when any *evaluated* gate fails; buckets below
their sample floor are reported as unevaluated and block a release evaluation
without failing the command, so `make eval` on the synthetic seed stays green
while the report says plainly that no release gate was measurable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..validate_seed import load_schema, load_seed, validate_seed
from .harness import retrieval_mode, run_seed
from .metrics import compute_metrics
from .report import write_reports

EVALS_DIR = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.runner",
                                     description="Run a SatyaLens gold set through the live pipeline and report METRICS.md gates.")
    parser.add_argument("--seed", default=str(EVALS_DIR / "gold_seed.json"),
                        help="gold set path (same schema as evals/gold_seed.json)")
    parser.add_argument("--out-dir", default=str(EVALS_DIR / "reports"),
                        help="directory for eval-report-*.json/.md (created if missing)")
    parser.add_argument("--db-url", default=None,
                        help="override the eval database URL; default is a throwaway SQLite file")
    parser.add_argument("--limit", type=int, default=None,
                        help="run only the first N examples (smoke runs)")
    args = parser.parse_args(argv)

    seed = validate_seed(load_seed(Path(args.seed)), load_schema())
    if args.limit is not None:
        seed = seed[: args.limit]

    mode = retrieval_mode()
    print(f"Running {len(seed)} example(s) through the live pipeline. Retrieval mode: {mode}")
    preds = run_seed(seed, db_url=args.db_url)
    metrics = compute_metrics(preds)
    json_path, md_path = write_reports(args.seed, preds, metrics, Path(args.out_dir), mode)

    for gate in metrics["gates"]:
        value = f"{gate['numerator']}/{gate['denominator']}" if gate["numerator"] is not None else "n/a"
        print(f"  {gate['name']:<28} {value:<10} gate {gate['gate']:<8} -> {gate['status']}")
    print(f"Reports written: {json_path} and {md_path}")
    if metrics["synthetic_only"]:
        print("NOTE: synthetic seed below all sample floors; no gate is a release signal.")
    return 1 if any(g["status"] == "fail" for g in metrics["gates"]) else 0


if __name__ == "__main__":
    sys.exit(main())
