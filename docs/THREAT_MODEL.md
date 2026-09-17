# SatyaLens prompt-injection threat model (Phase 7)

## Assets at risk

1. **Verdict integrity** - an attacker changes a claim's verdict, confidence or rationale.
2. **Evidence integrity** - an attacker makes the system cite fabricated or misattributed evidence.
3. **Data confidentiality** - case contents, reviewer notes, configuration and future credentials leaking out.
4. **Action safety** - the system sending, publishing or modifying anything because content told it to.

## Untrusted content classes

Every input SatyaLens ingests is attacker-controllable:

- Pasted text and forwarded WhatsApp messages (the original author is unknown).
- Fetched article pages and any documents they embed.
- OCR output from screenshots (an image can carry text aimed at the pipeline, invisible in normal viewing).
- Prior fact-check quotes and ratings returned by external APIs.

None of this content may direct system behaviour. It is evidence to analyze, never instructions to follow.

## Attack vectors

- **Instruction override**: "ignore all previous instructions", "disregard prior rules".
- **Persona override**: "you are now", "act as", "developer mode", jailbreak framings.
- **Delimiter injection**: chat-template tokens (`<|im_start|>`, `[INST]`, `<<SYS>>`) or fenced blocks marked `system`, used to smuggle a fake system turn.
- **Concealment**: instructions to hide steps or outputs from the user or reviewer.
- **Exfiltration**: instructions to forward, email or upload case data or credentials.
- **Secret extraction**: requests to print prompts, API keys or tokens.
- **Opaque payloads**: long encoded blobs whose decoded form carries any of the above.

## Defenses implemented in Phase 7

1. **Sanitization at ingestion** (`backend/app/services/injection.py`): control and
   format characters (zero-width, bidi overrides) are stripped and length is
   capped before content enters the pipeline.
2. **Heuristic detector**: deterministic pattern scan tags override, persona,
   delimiter, concealment, exfiltration, secret-extraction and opaque-blob
   attempts. It runs on every ingested text before retrieval.
3. **Routing on detection**: flagged cases skip external retrieval (so
   attacker-shaped text cannot steer queries), record `security_flags`, add a
   warning, and land in `pending_review` with an `unverifiable` draft. A human
   decides; nothing is executed from the content.
4. **Content isolation for the LLM seam**: `wrap_untrusted_for_llm` fences
   untrusted text inside explicit data markers with a standing instruction
   that the block is evidence, never commands. No LLM call exists in this
   phase; any future call must use the wrapper.
5. **Honest failure modes**: with no key configured, retrieval abstains rather
   than fabricating evidence; that behaviour is unchanged.

## Explicitly out of scope / residual risk

- The detector is a heuristic: novel phrasings will evade it, and benign text
  can be flagged (a false positive costs a human review, not a wrong verdict).
  The eval floor for injection resistance (>= 0.99 in `evals/METRICS.md`) is
  how this is measured once labeled attack data exists.
- URL fetching still runs in-process; production must move it to an
  egress-restricted, isolated worker (noted since Phase 1).
- No per-request tenant isolation or authentication exists yet; deployment
  guidance is in `docs/DEPLOYMENT.md`.
- A determined attacker can target the human reviewer instead; reviewer UI
  must keep raw content visually distinct from system output.
