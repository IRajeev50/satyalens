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
