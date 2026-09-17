# SatyaLens Phase 1

An evidence-first verification workbench. It creates a versioned case, extracts atomic claims, retrieves matching published fact checks when configured, stores evidence items, applies rubric `1.0.0`, and marks every draft `pending_review`.

It is a modular monolith. The service boundaries under `backend/app/services/` can move to background workers later without introducing an agent framework.

## Mac quick start: SQLite, no Docker, no keys

Prerequisites: Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
brew install uv
cd satyalens
cp .env.example .env
make dev
```

Open http://localhost:8000. SQLite is created as `satyalens.db`. API docs are at http://localhost:8000/docs.

Run tests:

```bash
uv run --extra dev pytest -q
```

### Standard `venv` alternative

```bash
cd satyalens
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000
```

## Use Postgres locally

```bash
docker compose up -d postgres
cp .env.example .env
# Put this line in .env:
# DATABASE_URL=postgresql+psycopg://satyalens:satyalens@localhost:5432/satyalens
make dev
```

Stop it with `docker compose down`. Add `-v` only if you intend to delete local database data.

## External seams

- **No key:** pasted text and public article URLs work; cases, claims and assessments are stored. Extraction is deterministic. With no external evidence, the rubric deliberately returns `unverifiable / Low` rather than inventing support.
- **`GOOGLE_FACTCHECK_API_KEY`:** calls the real Google Fact Check Tools API and stores matching review URLs, quotes/published claims, publishers and ratings. Create a key with that API enabled in Google Cloud.
- **`LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`:** labeled seam for later multilingual/model-assisted claim extraction. Phase 1 does not call it.
- **`SEARCH_API_KEY`, `SEARCH_PROVIDER`:** labeled seam for later open-web and official-source retrieval. Phase 1 does not call it.

No integration is simulated and no key is hardcoded.

## API

`POST /api/verify` accepts exactly one input:

```json
{"text":"The government launched Scheme X in 2024."}
```

or:

```json
{"url":"https://example.org/article"}
```

`POST /api/cases/{case_id}/review` records an approval, override, or request for more evidence:

```json
{"actor":"reviewer@example.org","decision":"approve","reason":"Checked sources and scope."}
```

The response includes the complete path `case -> claims -> evidence -> assessment`, evidence IDs, source links, quotes, rubric version, confidence band and reasoning path.

## Honest Phase 1 limits

Google Fact Check results are prior-work leads, not an oracle. Their rating text is mapped conservatively; claim/date/source fitness still needs human review. URL fetching blocks local/private addresses, limits redirects and payload size, and strips non-content tags, but production should move it into an isolated egress-restricted worker. Phase 1 has no OCR, general web search, translation, source snapshots, authentication or tenant isolation. See [docs/PHASES.md](docs/PHASES.md).

## Screenshot OCR (Phase 2)

For local Hindi/English OCR on macOS:

```bash
brew install tesseract tesseract-lang
make dev
```

The UI and `POST /api/verify/screenshot` accept PNG/JPEG/WebP. The original bytes are not retained in Phase 2; the case stores SHA-256, dimensions, MIME type, OCR engine, extracted text and qualitative extraction confidence. A production object-store seam is deferred until tenant/security controls are added.

## Image forensics (Phase 3)

`POST /api/inspect/image` runs local EXIF inspection and dHash generation. Screenshot cases also record these media signals. Set `C2PA_CLI_PATH` to a real compatible local verifier to enable signed-manifest inspection. Reverse-image and forensic-vendor credentials are explicit seams only in this phase; no result is fabricated when absent.

Media signals never change a semantic claim verdict by themselves. No EXIF/C2PA result means "authentic," and no missing credential means "fake."

## WhatsApp-style intake (Phase 4)

The Meta Cloud API webhook is real and closed by default:
- `GET /api/intake/whatsapp/webhook` performs verify-token challenge handling.
- `POST /api/intake/whatsapp/webhook` requires a valid `X-Hub-Signature-256`, deduplicates provider message IDs, hashes sender identifiers, and creates text evidence cases.

Set all four `WHATSAPP_*` variables to connect a Meta app. Phase 4 does not send replies or download media because those actions require a real approved Meta account and template/product decisions; `outbound_status` is explicitly `not_sent`.

## Hindi and Hinglish (Phase 5)

Original text is preserved. The normalized NFC representation, detected language, code-switch flag logic and deterministic Devanagari transliteration query are available without keys. Fact Check API requests use Hindi where detected. Screenshot OCR already requests Hindi+English language packs.

`TRANSLATION_API_KEY` and `TRANSLATION_PROVIDER` are future managed-translation seams. Phase 5 does not fabricate translations. Human review remains required, especially for negation, numbers, names and mixed-script claims.

## Monitoring (Phase 6)

Monitors are explicit and user-controlled:
- `POST /api/monitors` saves an English/Hindi prior-check query.
- `POST /api/monitors/{id}/run` performs a real Google Fact Check query now.
- `POST /api/monitors/{id}/pause` stops it; `GET /api/monitors` shows state and last count.

Scheduling is deliberately deployment-owned. Locally, invoke the run endpoint from cron/launchd. Production should call it from the chosen managed queue/scheduler after authentication and tenant controls exist. No fake background watch or notification is claimed.
