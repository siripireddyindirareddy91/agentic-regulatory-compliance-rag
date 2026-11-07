# COMPLYINTEL AI

An evidence-led regulatory compliance workspace for financial institutions. Next.js/React frontend, FastAPI API, SQLAlchemy relational storage, and a ten-stage LangGraph workflow. All seeded regulations, institution details and results are **synthetic DEMO DATA**, never official RBI or SEBI mandates.

## Run locally

Requires Python 3.12+ and Node.js 22+.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
# Generate a stable secret and set it in your shell / .env for deployment.
$env:JWT_SECRET_KEY = 'replace-with-at-least-32-random-characters'
$env:DATABASE_URL = 'sqlite:///./compliance.db'
.\.venv\Scripts\python -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python -m uvicorn backend.app.main:app --port 8000
```

In another terminal:

```powershell
npm ci --prefix frontend
$env:NEXT_PUBLIC_API_URL = 'http://localhost:8000'
npm run dev --prefix frontend
```

Open http://localhost:3000. API documentation: http://localhost:8000/api/docs. Environment values must be exported in the process; the API does not automatically load `.env`. Docker Compose reads `.env` for interpolation.

## Demo credentials

Password for all seeded accounts: `Demo-Compliance-2026!` (override with `DEMO_PASSWORD` before first seed).

| Email | Role |
| --- | --- |
| admin@complyintel.demo | Administrator |
| reviewer@complyintel.demo | Compliance reviewer |
| analyst@complyintel.demo | Analyst |
| viewer@complyintel.demo | Read-only viewer |

Public registration creates an isolated, empty institution with a viewer account. It never grants access to the shared demo tenant. Disable demo seeding using `DEMO_MODE=false` before real use; provisioning real institution administrators is an operator task in this release.

## Features

- Twelve working workspace modules, responsive navy/teal interface, searchable tables and database-derived dashboard.
- JWT access/refresh endpoints, Argon2 password hashing, role enforcement and institution-scoped record access.
- PDF, DOCX, TXT and CSV extraction; bounded upload size; DOCX expansion guard; duplicates and document versions.
- Chunking with page metadata, deterministic local signed feature-hash embeddings, lexical/vector hybrid scoring, exact source citations.
- Ten real LangGraph nodes: ingestion, change detection, obligation extraction, policy retrieval, gap analysis, risk scoring, recommendations, reflection, human escalation and auditing.
- Bounded retrieval retry, persisted workflow state, execution history and failure records.
- Evidence inspection, human approval/rejection/request-evidence, explicit confirmation and reviewer comments.
- Risk factor editing with required reasons; compliance determination by a human reviewer.
- Corrective actions only after human approval; ownership, deadlines, progress and reviewer-controlled completion with evidence.
- Audit events with SHA-256 hash chaining and verification endpoint; append-only through the API.
- Seven database-backed report categories with PDF, CSV and XLSX downloads.
- Institution/source settings, notification inbox, policy status management and version comparison.
- Optional OpenAI grounded Q&A; no key needed for the local extractive demonstration.

## Architecture

```mermaid
flowchart LR
  UI[Next.js / React workspace] --> API[FastAPI / RBAC]
  API --> DB[(SQLAlchemy: PostgreSQL or SQLite)]
  API --> Ingest[Secure extraction and chunking]
  Ingest --> Retrieval[Hash embeddings + lexical retrieval]
  API --> Graph[LangGraph specialist workflow]
  Retrieval --> Graph
  Graph --> Human[Persisted human review gate]
  Human --> Actions[Corrective actions]
  API --> Audit[Hash-chained audit events]
  API --> Reports[PDF / CSV / XLSX]
```

```mermaid
flowchart TD
  Ingest --> Changes --> Requirements --> Retrieval --> Gaps --> Risk --> Recommendations --> Validation
  Validation -->|weak evidence: retry once| Retrieval
  Validation -->|escalate| Review[Human review: paused persisted workflow]
  Review -->|all findings approved or rejected| Resume[Resume and complete workflow]
  Review -->|approved finding| CorrectiveAction
```

The human gate is an application-level persisted pause/resume. It does not use LangGraph checkpoint interrupts. AI never records a human approval.

## Repository

```text
frontend/app/            Next.js workspace and responsive styles
frontend/components/     Reusable Radix-based dialog and UI primitives
backend/app/models.py    Tenant-scoped relational schema
backend/app/security.py  JWT, password hashing and roles
backend/app/rag.py       Parsing, chunking, embeddings, hybrid retrieval
backend/app/workflow.py  Typed ten-node LangGraph workflow
backend/app/risk.py      Explainable weighted score
backend/app/audit.py     Hash chain and verification
backend/app/main.py      REST API and report generation
backend/app/seed.py      Synthetic scenario and demo users
backend/migrations/      Alembic migration
backend/tests/           Security and end-to-end API tests
api/index.py             Vercel Python entrypoint
data/                    Exportable synthetic source examples
docker-compose.yml       PostgreSQL, API and frontend
render.yaml              Optional dedicated backend configuration
vercel.json              Static Next.js frontend + Python API
```

The schema contains users, regulatory documents (including policies), chunks (including embedding vectors), requirements, findings (including risk/evidence), workflow runs (including execution steps), reviews, actions, audit logs, sources, notifications and settings. Document and policy versions use a previous-version foreign key. This compact schema consolidates several tables from the original specification rather than implementing all 30+ proposed tables.

## Database and configuration

SQLite works locally without external services. For durable deployment use `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`. Migrate with `python -m alembic -c backend/alembic.ini upgrade head`. Startup also creates missing schema for demonstration convenience. Docker uses the pgvector-enabled PostgreSQL image, but this release stores hash embeddings as JSON and computes similarity in the application, not pgvector ANN search.

| Variable | Purpose |
| --- | --- |
| DATABASE_URL | SQLite local or managed PostgreSQL |
| JWT_SECRET_KEY | Stable random secret, required with APP_ENV=production |
| DEMO_MODE / DEMO_PASSWORD | Demo seeding and initial passwords |
| OPENAI_API_KEY / OPENAI_MODEL | Optional grounded Q&A provider |
| CORS_ORIGINS | Comma-separated exact frontend origins |
| MAX_UPLOAD_SIZE_MB | Upload size limit, default 10 |
| NEXT_PUBLIC_API_URL | Frontend build-time backend URL; empty uses same origin |
| APP_ENV | development or production |

`REDIS_URL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `VECTOR_STORE`, and `UPLOAD_DIRECTORY` are reserved example settings; alternate embedding/vector providers, Redis jobs and original-file object storage are not wired into this release. Extracted text is persisted in the database; original upload bytes are not retained.

## API

Interactive OpenAPI documentation is exposed at `/api/docs`. All business endpoints require a bearer token. Important groups: `/auth/*`, `/dashboard/*`, `/regulations/*`, `/documents`, `/policies/*`, `/rag/*`, `/agents/*`, `/compliance/findings/*`, `/risks/*`, `/reviews/*`, `/actions/*`, `/audit/*`, `/reports/*`, `/settings/*`, `/sources`, `/notifications`.

Scoring: `severity × .35 + likelihood × .25 + regulatory impact × .25 + operational impact × .15`. Each input is 1–5. Critical ≥4.2; High ≥3.4; Medium ≥2.4; Low otherwise. Scores and extraction confidence are heuristics, not validated probabilities. Policy similarity does not prove control compliance. Coverage counts only approved findings a human marks fully compliant.

## Complete demonstration

1. Sign in as administrator or reviewer.
2. Inspect the pre-indexed synthetic six-obligation circular and three internal policies.
3. Open AI Compliance Agents to inspect the seeded LangGraph run.
4. Upload a sample regulation; run Analyze, then inspect its exact evidence and retrieved policy excerpts.
5. Open a finding and inspect risk inputs, uncertainty and recommendation.
6. In Human review, provide a rationale, check the confirmation box and approve or reject.
7. After approval, create a corrective action; set owner, deadline, progress and evidence.
8. Complete the action as reviewer; generate a report; verify the audit chain.

Source documents are never automatically marked official. When evidence is unverified, Q&A returns: **Insufficient verified regulatory evidence. Human verification required.**

## Tests and builds

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

Tests cover authentication, roles, tenant isolation, upload validation, deterministic retrieval, risk boundaries, workflow execution, human confirmation, action authorization, three report formats and audit tampering detection.

Validation on 7 November 2026: 8 backend integration tests passed; 2 frontend validation tests passed; TypeScript and the optimized Next.js production build passed. Live HTTPS checks verified the frontend, API health, login, database dashboard (1 seeded regulation, 6 requirements, 6 findings), and a valid audit chain. Automated browser preview timed out, so visual browser QA was not completed. The npm dependency audit returned zero vulnerabilities after updating Zod.

## Deployment

Vercel deploys both static Next.js and FastAPI using `vercel deploy --prod`. The root lightweight requirements exclude local-only ML training packages. Set a stable `JWT_SECRET_KEY` and `DATABASE_URL` before production use. Without PostgreSQL, Vercel uses `/tmp/complyintel.db`, explicitly marked **ephemeral demo storage**: records may reset or differ across instances. This is not durable production storage. The frontend and API share an origin on Vercel, so leave `NEXT_PUBLIC_API_URL` unset.

For Docker: set a random `JWT_SECRET_KEY` in `.env`, then `docker compose up --build`. Frontend: port 3000; API: port 8000. Database is a named persistent volume.

For a dedicated backend, use `render.yaml` with a managed database and set frontend `NEXT_PUBLIC_API_URL` at build time. Do not deploy confidential data with demo credentials.

## Limits and next work

This is a functional demonstration and engineering foundation, not a fully certified enterprise product. Automated official-source crawling, OCR, calibrated ML classifiers, trained anomaly models, cross-encoder reranking, FAISS/pgvector ANN retrieval, policy mapping CRUD, durable background queues, object-store attachments, multi-user notification targeting, refresh-token rotation/revocation and scheduled reports remain future work. Source URLs are metadata and external links; the server does not fetch arbitrary URLs. Settings do not silently activate monitoring or alternate providers. Workflows execute in the request and are suitable for bounded demo documents. Audit chaining is application-level tamper evidence, not legal immutability. No legal or regulatory accuracy certification is claimed.
