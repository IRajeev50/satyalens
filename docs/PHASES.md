# SatyaLens delivery phases

Phase 1 is the working evidence skeleton in this repository: text/URL intake, atomic claims, Google Fact Check retrieval, versioned qualitative assessment, stored evidence chain, and a human-review endpoint.

## Phase 2 - screenshot OCR
- Region-aware Hindi/English OCR with original-image offsets and confidence.
- Safe image validation, metadata extraction, perceptual hash, immutable artifact record.
- Reviewer correction UI and OCR evaluation by script.

## Phase 3 - image forensics
- Separate caption truth from media authenticity.
- C2PA validation, reverse-image vendor seam, optional forensic-vendor signals.
- Never infer "authentic" from absent signals; require review for high-impact findings.

## Phase 4 - WhatsApp-style intake
- Consent-led intake flow, queue-backed workers, status notifications and case links.
- Current Meta policy review, retention controls, rate limits and abuse handling.
- No autonomous publishing or forwarding.

## Phase 5 - Hindi and Hinglish
- Preserve original beside translation; transliteration and alias expansion.
- India-specific date, currency and place normalization.
- Bilingual review sets; confidence calibrated separately by language and claim type.

## Phase 6 - monitoring and professional operations
- Saved queries/source monitors, corrections, version history and exports.
- Tenant isolation, roles, object storage, audit log and retention/deletion controls.
- Paid-pilot metrics: citation correctness, decisive-evidence recall, abstention quality and researcher time saved.

Each phase keeps deterministic orchestration. Background workers are introduced for slow fetch/OCR jobs; service splitting happens only when load, security boundaries or team ownership require it.

## Phase 7 - claim-type gate, evals scaffold, injection defenses
- Every atomic claim typed (checkable_fact / prediction / opinion / satire / subjective / not_a_claim) before verification; only checkable facts proceed. Structured components: subject, predicate, object, quantity, place, time, authority, modality. English and Hindi/Hinglish cues; deterministic and conservative.
- evals/ scaffold: schema, deterministic generator, synthetic seed (56 examples, all branches), stdlib validator, METRICS.md with per-bucket floors and release gates. Seed is bootstrap-only, never quality evidence.
- Untrusted-content defenses: sanitization, deterministic injection detector, human routing on flags, LLM-seam isolation wrapper. Threat model in docs/THREAT_MODEL.md.
- Later: model-assisted typing behind the labeled LLM seam (must use the isolation wrapper), real labeled eval data to meet the floors, detector hardening against the eval floors.
