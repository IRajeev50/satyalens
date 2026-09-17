"""Write eval run reports: machine-readable JSON plus a human-readable Markdown table.

Reports state exact numerators/denominators, mark below-floor buckets as
unevaluated, and carry the synthetic-data warning whenever the seed is
synthetic, so a report can never be mistaken for quality evidence it is not.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .metrics import Prediction


def _fmt_fraction(numerator: int | None, denominator: int | None, value: float | None) -> str:
    if numerator is None or denominator is None:
        return "n/a"
    pct = f"{value:.1%}" if value is not None else "n/a"
    return f"{numerator}/{denominator} ({pct})"


def render_markdown(seed_path: str, preds: list[Prediction], metrics: dict, retrieval_mode: str,
                    generated_at: str) -> str:
    lines: list[str] = []
    lines.append("# SatyaLens eval report")
    lines.append("")
    lines.append(f"- Generated: {generated_at}")
    lines.append(f"- Gold set: `{seed_path}` ({metrics['example_count']} examples)")
    lines.append(f"- Retrieval mode: {retrieval_mode}")
    if metrics["synthetic_only"]:
        lines.append("- WARNING: every example is synthetic bootstrap data. This report exercises the "
                     "harness; it is NOT evidence of system quality and must not be quoted as such.")
    lines.append("")
    lines.append("## Bucket sizes vs sample floors")
    lines.append("")
    lines.append("| Bucket | n | Floor | Meets floor |")
    lines.append("| --- | --- | --- | --- |")
    floors = metrics["floors"]
    counts = metrics["bucket_counts"]
    true_n = counts.get("true", 0) + counts.get("mostly_true", 0)
    rows = [("true+mostly_true", true_n, floors["true+mostly_true"])]
    for bucket in ("political_sensitive", "prompt_injection", "abstain", "media_wrong_context"):
        rows.append((bucket, counts.get(bucket, 0), floors[bucket]))
    for label, n, floor in rows:
        lines.append(f"| {label} | {n} | {floor} | {'yes' if n >= floor else 'NO - unevaluated'} |")
    lines.append("")
    lines.append("## Release gates")
    lines.append("")
    lines.append("| Metric | Gate | Result | Status |")
    lines.append("| --- | --- | --- | --- |")
    for gate in metrics["gates"]:
        lines.append(f"| {gate['name']} | {gate['gate']} | "
                     f"{_fmt_fraction(gate['numerator'], gate['denominator'], gate['value'])} | {gate['status']} |")
    lines.append("")
    for gate in metrics["gates"]:
        lines.append(f"- **{gate['name']}** ({gate['status']}): {gate['detail']}")
    lines.append("")
    lines.append("## Secondary metrics (reported, not gated)")
    lines.append("")
    abstain = metrics["secondary"]["abstention_correctness"]
    lines.append(f"- Abstention correctness: "
                 f"{_fmt_fraction(abstain['numerator'], abstain['denominator'], abstain['value'])} "
                 f"of abstain-bucket examples scored unverifiable. {abstain['detail']}")
    cta = metrics["secondary"]["claim_type_accuracy"]
    lines.append(f"- Claim-type gate exact match: "
                 f"{_fmt_fraction(cta['exact_match_numerator'], cta['exact_match_denominator'], cta['exact_match'])}")
    lines.append("")
    lines.append("| Claim type | Recall | Precision |")
    lines.append("| --- | --- | --- |")
    for claim_type, stats in cta["per_type"].items():
        lines.append(f"| {claim_type} | "
                     f"{_fmt_fraction(stats['recall_numerator'], stats['recall_denominator'], stats['recall'])} | "
                     f"{_fmt_fraction(stats['precision_numerator'], stats['precision_denominator'], stats['precision'])} |")
    lines.append("")
    veracity = metrics["secondary"]["veracity_accuracy"]
    lines.append("### Veracity accuracy per expected class")
    lines.append("")
    lines.append("| Expected veracity | Exact match |")
    lines.append("| --- | --- |")
    for verdict, stats in veracity["per_class"].items():
        lines.append(f"| {verdict} | {_fmt_fraction(stats['numerator'], stats['denominator'], stats['accuracy'])} |")
    lines.append("")
    lines.append("### Veracity accuracy by language")
    lines.append("")
    lines.append("| Language | Exact match |")
    lines.append("| --- | --- |")
    for lang, stats in veracity["per_language"].items():
        lines.append(f"| {lang} | {_fmt_fraction(stats['numerator'], stats['denominator'], stats['accuracy'])} |")
    lines.append("")
    lines.append(f"_{veracity['detail']}_")
    lines.append("")
    latency = metrics["latency"]
    lines.append("## Latency and cost")
    lines.append("")
    if "mean" in latency:
        lines.append(f"- Latency (ms, wall clock per example): mean {latency['mean']}, p50 {latency['p50']}, "
                     f"p95 {latency['p95']}, max {latency['max']}, total {latency['total']}")
    lines.append(f"- Cost: {metrics['cost']['status']} - {metrics['cost']['detail']}")
    lines.append("")
    lines.append("## Honest limits")
    lines.append("")
    lines.append("- Buckets below their sample floor are unevaluated; a number on too-small data is never a release signal.")
    lines.append("- The fabricated-citation gate's supports-the-relation half is a human hand-check (METRICS.md); "
                 "only the existence half is automated here.")
    lines.append("- Abstention rationale acceptance and reviewer time saved are manual measurements, not computed by this harness.")
    lines.append("- Veracity accuracy with no retrieval key configured measures the abstention path only.")
    lines.append("")
    lines.append(f"Release evaluation status: **{'BLOCKED (one or more gates failed or are unevaluated/manual)' if metrics['release_blocked'] else 'ALL GATES PASS'}**")
    lines.append("")
    return "\n".join(lines)


def write_reports(seed_path: str, preds: list[Prediction], metrics: dict, out_dir: Path,
                  retrieval_mode: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"eval-report-{stamp}.json"
    md_path = out_dir / f"eval-report-{stamp}.md"
    payload = {
        "generated_at": generated_at,
        "seed": seed_path,
        "retrieval_mode": retrieval_mode,
        "metrics": metrics,
        "predictions": [asdict(p) for p in preds],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(seed_path, preds, metrics, retrieval_mode, generated_at),
                       encoding="utf-8")
    return json_path, md_path
