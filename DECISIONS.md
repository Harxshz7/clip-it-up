# Architectural Decisions (DECISIONS.md)

This document records the foundational engineering decisions made for `clip-it-up` Phase 0.

---

## 1. Realtime Streaming & SSE Authentication Approach
- **Choice**: Fetch-based Server-Sent Events (SSE) using `fetch()` and `ReadableStreamDefaultReader`, with `Authorization: Bearer <token>` in request headers (and query parameter fallback).
- **Rationale**:
  - Native browser `EventSource` does not support custom HTTP headers (such as `Authorization: Bearer <jwt>`), forcing applications to put sensitive JWTs into query parameters in URL logs or use cookies with CSRF risks.
  - A modern fetch-based streaming client enables secure standard Bearer authentication, handles instant snapshot parsing, processes custom event channels (`snapshot`, `update`), ignores keep-alive heartbeats (`: heartbeat`), and seamlessly manages `Last-Event-ID` reconnection without leaking tokens.

---

## 2. Direct S3 Upload & Multipart Threshold
- **Choice**: Direct-to-S3 upload via Presigned PUT URLs for files $\le$ 100 MB; S3 Multipart Upload with 10 MB chunk size for files > 100 MB up to 5 GB.
- **Rationale**:
  - Uploading video files directly from the browser to MinIO / S3 removes load, bandwidth saturation, and buffering memory pressure from the FastAPI API servers.
  - For files over 100 MB, multipart uploads allow concurrent part transfers (concurrency of 4) and per-part retry on network drops without re-uploading the whole file.

---

## 3. Worker Idempotency & Cost Recording Strategy
- **Choice**: Stage-level task idempotency using deterministic task arguments `(job_id, stage_name)` and PostgreSQL unique constraints on `job_stages(job_id, name)` and `usage(job_id, metric)`.
- **Rationale**:
  - Distributed workers may experience task retries or manual rerun triggers.
  - Using PostgreSQL `ON CONFLICT DO UPDATE` ensures usage quantities and ₹ INR costs are never duplicated on retries.

---

## 4. Why Clerk for Authentication
- **Choice**: Clerk on the frontend + FastAPI JWT validation against Clerk JWKS.
- **Rationale**:
  - Eliminates the security surface of maintaining raw password hashing, reset tokens, and MFA infrastructure in PostgreSQL.
  - FastAPI verifies standard RS256 JWTs using cached JWKS endpoints, running completely statelessly without roundtrips to Clerk servers on every API call.
  - `DEV_AUTH_BYPASS=true` is provided so developers can run and test the complete stack locally without needing third-party API keys.
