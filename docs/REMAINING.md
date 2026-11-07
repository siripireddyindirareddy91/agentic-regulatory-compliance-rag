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

Still not implemented; these prevent calling the entire master prompt complete:

- Automated official-site monitoring with source-specific access rules and scheduling.
- OCR for scanned PDFs; external object-storage adapter (original files now persist in PostgreSQL).
- OpenAI or sentence-transformer embedding adapters, FAISS adapter and cross-encoder reranking.
- Trained and evaluated classification/anomaly models; production ML calibration.
- Durable background queues, distributed workers and automatic workflow retry backoff.
- Native LangGraph checkpoint interrupt/resume (the existing human gate is persisted at the application layer).
- Fully normalized role/permission, department and evidence schemas from the proposed 30+ table design.
- Refresh-token rotation/revocation, institution administration, invitations and production identity management.
- User-specific notification delivery and scheduled reports.
- Full browser end-to-end coverage and visual QA.

The local feature-hash embedding provider is deterministic and requires no paid model API. pgvector storage improves indexing and durability; it does not turn that provider into a trained semantic model. Vercel's former temporary SQLite records are not a reliable historical source: the PostgreSQL database is initialized with the documented synthetic demo scenario. No migration of all former ephemeral instances is claimed.
