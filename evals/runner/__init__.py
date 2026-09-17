"""Phase 8 eval runner: live-pipeline harness plus honest METRICS.md computation.

- ``harness`` runs gold examples through the real pipeline (no simulation).
- ``metrics`` is pure stdlib and computes exact numerators/denominators;
  buckets below their METRICS.md floor are reported as unevaluated.
- ``report`` writes JSON and Markdown report files.
"""
