# Deployment readiness

The local product is one ASGI process plus SQLite or Postgres. Production must add, before public use:

1. Authentication, tenant IDs on every entity, object-level authorization and rate limits.
2. Isolated URL/OCR/media workers with restricted egress, malware scanning and object storage.
3. A managed queue/scheduler calling monitor runs and job status APIs.
4. Encrypted object storage, retention/deletion controls, secrets manager and audit export.
5. Real vendor contracts/configuration for search, OCR/translation, reverse-image and forensics.
6. Migration tooling, backups, observability, incident response and legal/security review.

The code does not claim these controls exist. SQLite is for local development only.
