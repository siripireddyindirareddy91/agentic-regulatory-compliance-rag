# Master-prompt coverage and remaining work

Implemented in the PostgreSQL update:

- Free Neon PostgreSQL connected to the Vercel production project through its managed integration.
- Native pgvector extension, 256-dimensional embedding table, HNSW cosine index and tenant-filtered retrieval.
- Serverless-safe PostgreSQL connections and database/vector readiness endpoint.
- Explicit policy-to-requirement mappings with reviewer authorization and audit history.
- Administrator-controlled risk weights; changes recalculate findings and audit each score change.
- Persistent corrective-action evidence files in PostgreSQL, checksums, authenticated downloads and limits.
- Overdue-action escalation with notifications and audit events.
- Failed workflow retry endpoint.
- Controls UI for mapping, weights, evidence upload/download and operational readiness.
- Original uploaded regulatory/policy bytes retained in PostgreSQL with checksums and authenticated download.

Implemented in the automation update:

- Daily Vercel cron with secret authentication, configurable source monitoring, official-host allowlist, public-address checks, robots policy, bounded redirects/downloads and change snapshots. Monitoring never labels a changed web page as a verified new mandate.
- PostgreSQL durable jobs, leased claiming with SKIP LOCKED, lease recovery, three-attempt exponential retry backoff, tenant-scoped administration, continuous standalone worker and scheduled report generation.
- Trained TF-IDF Logistic Regression, Random Forest and Isolation Forest models with portable inference artifacts and held-out synthetic-data metrics. Document uploads use the trained classifier; the UI also exposes model diagnostics. These models are not production calibrated.
- Refresh-token rotation/replay rejection and logout revocation, with browser token renewal.
- Scrollable sidebar navigation and additional idempotent synthetic scenarios, policies, findings, sample review records and corrective actions.

Implemented in the retrieval and identity update:

- RBI monitoring uses its published notifications_rss.xml syndication feed, reads notification metadata, and does not crawl linked pages when robots access is unavailable. Fixed a PostgreSQL verification-label length error caught by live testing.
- Native LangGraph checkpoints backed by PostgreSQL in cloud and SQLite locally. A real interrupt pauses the graph; all final human decisions resume the saved graph. Older investigations retain their explicitly labeled legacy gate.
- Optional OpenAI and sentence-transformer embedding adapters, FAISS local search and cross-encoder reranking. Provider profiles prevent comparing vectors from different embedding backends; reindex after changing providers.
- Optional PyMuPDF/Tesseract OCR and private S3-compatible original-file storage adapters. Durable PostgreSQL originals remain the default.
- Administrator-issued, expiring, single-use invitations and recovery links, role-restricted provisioning and refresh-session revocation after recovery.
- New finding notifications have individual reviewer/admin deliveries and per-user read state; old tenant-wide notifications remain legacy broadcasts.

Still incomplete or externally unverified; the entire original master prompt is not complete:

- Independently labeled real regulatory evaluation data and production model calibration. Synthetic training metrics cannot establish real-world accuracy.
- Enterprise identity-provider SSO, account recovery delivery infrastructure and independent security review. Current recovery is administrator-assisted link sharing.
- Full 30+ normalized-table permission/department/evidence schema; current operational schema consolidates these entities.
- OCR requires a backend with Tesseract; sentence-transformers/FAISS/cross-encoder require optional packages and model downloads; S3 requires a configured private bucket. Those external integrations are not provisioned or live-validated on Vercel.
- Full browser end-to-end and visual QA. Windows computer-use verification stopped because the tool could not establish the current browser URL; no browser-safety barrier was bypassed.

Queue semantics are at-least-once. PostgreSQL worker claims are serialized with SKIP LOCKED; SQLite is intended for a single worker. Job handlers use document hashes, analysis checks or report job IDs for idempotency, but this is not a claim of exactly-once side effects. The serverless cron processes at most three jobs per daily invocation; use a persistent worker for prompt processing of larger queues. Jobs retain failed attempts and retry times. No paid plan is required. Sources can deny automated retrieval; such failures are visible and retried, never reported as successful collection.

The local feature-hash embedding provider is deterministic and requires no paid model API. pgvector storage improves indexing and durability; it does not turn that provider into a trained semantic model. Vercel's former temporary SQLite records are not a reliable historical source: the PostgreSQL database is initialized with the documented synthetic demo scenario. No migration of all former ephemeral instances is claimed.
