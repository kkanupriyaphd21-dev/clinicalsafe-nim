# ClinicalSafe NIM

A standalone, production-ready **NVIDIA NIM API system** with an encrypted key vault, usage tracking, automatic key rotation, and a polished Next.js UI for clinical table summarization.

---

## Features

- **Encrypted API Key Vault** — store multiple NVIDIA API keys, encrypted at rest with Fernet (`MASTER_KEY`).
- **Usage Tracking** — per-key token/request metrics and event history.
- **Automatic Rotation** — falls back to the next active key on 401/402/429 failures.
- **Single-Table Summarization** — send clinical safety tables to NVIDIA NIM with numeric verification.
- **CSR PDF Pipeline** — upload full Clinical Study Reports, summarize all tables in parallel, and download a structured DOCX.
- **Polished UI** — Next.js 16 + React 19 + Tailwind CSS v4 dark clinical theme with 3D React Three Fiber background.
- **Production Docker Compose** — nginx reverse proxy, multi-stage builds, health checks.
- **End-to-End Tests** — Playwright screenshots and UI smoke tests.

---

## Architecture

```
Browser → nginx (port 80)
          ├── /api/nim/* → NIM Backend (FastAPI, port 8002)
          └── /           → Next.js Frontend (port 3000)
```

---

## Quick Start

### 1. Clone / locate the project

```bash
cd /Users/bhriguverma/clinicalsafe-nim
```

### 2. Configure environment

```bash
cp .env.example .env
```

Generate a Fernet master key and add it to `.env`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```env
MASTER_KEY=your-key-here
NVIDIA_API_KEY=nvapi-your-key-here   # optional: seeds the vault on first start
```

### 3. Run with Docker Compose

```bash
make build
make up
```

Open http://localhost

### 4. Or run locally

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn src.api.main:app --reload --port 8002
```

Frontend:

```bash
cd frontend
npm install
npm run build
NIM_BACKEND_URL=http://localhost:8002 npm start
```

For development with hot reload:

```bash
npm run dev
```

The frontend proxies `/api/nim/*` to the backend at `http://localhost:8002` (override with `NIM_BACKEND_URL`).

---

## API Reference

### Health

```http
GET /health
```

### API Keys

```http
POST   /keys                 { name, key, is_active?, is_default? }
GET    /keys
GET    /keys/{id}
PATCH  /keys/{id}            { name?, is_active?, is_default? }
DELETE /keys/{id}
GET    /keys/{id}/usage
```

### Single-Table Summarization

```http
POST /summarize
Content-Type: application/json

{
  "table_text": "start_table [HEADERS: ...",
  "model": "meta/llama-3.3-70b-instruct",
  "max_tokens": 1024,
  "temperature": 0.0
}
```

### CSR PDF Pipeline

```http
POST   /csr                  multipart/form-data: file, model, max_workers, max_tokens
GET    /csr/progress/{task_id}
GET    /csr/download/{token}
```

---

## Testing

```bash
make test
```

Backend tests only:

```bash
make test-backend
```

Frontend build check:

```bash
make test-frontend
```

---

## Project Structure

```
clinicalsafe-nim/
├── backend/                 # FastAPI NIM backend
│   ├── src/api/routers/     # keys, summarize, csr
│   ├── src/services/        # key_vault, usage_tracker, nim_client, csr_synthesizer
│   ├── src/generation/      # nim_generator, provenance
│   ├── src/data_processing/ # csr_parser, table_classifier
│   └── tests/
├── frontend/                # Next.js 16 app
│   ├── app/
│   ├── components/ui/
│   └── lib/api.ts
├── docker-compose.yml
├── nginx.conf
└── Makefile
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MASTER_KEY` | **Required.** Fernet key for encrypting stored NVIDIA API keys. |
| `NVIDIA_API_KEY` | Optional default key seeded on first startup. |
| `DATABASE_URL` | SQLite/Postgres connection string. Defaults to `sqlite:///data/clinicalsafe_nim.db`. |
| `NVIDIA_NIM_BASE_URL` | Defaults to `https://integrate.api.nvidia.com/v1`. |
| `NIM_DEFAULT_MODEL` | Defaults to `meta/llama-3.3-70b-instruct`. |
| `NIM_TIMEOUT_SECONDS` | API timeout. Defaults to `60`. |
| `LOG_LEVEL` | Defaults to `INFO`. |

---

## Security Notes

- API keys are **encrypted at rest** and only decrypted when making a request.
- Keys are **never returned in full** by the API; only masked representations are exposed.
- The default `NVIDIA_API_KEY` env var is optional and only seeds an empty vault.
- For production, rotate `MASTER_KEY` only after backing up decrypted keys—existing encrypted keys cannot be recovered without the original master key.

---

## License

Proprietary — built for the ClinicalSafe project.
