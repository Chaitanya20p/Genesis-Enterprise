# Genesis AI — Enterprise Multi-Agent Innovation Platform

> Powered by **IBM Watsonx.ai (Granite models)** · Flask Application Factory · ChromaDB RAG · Bootstrap 5 dark-mode SaaS dashboard

---

## Architecture Overview

```
Genesis AI
├── app.py                    # Application factory (Flask + SQLAlchemy + CORS)
├── models.py                 # SQLAlchemy models (Project, DebateLog)
├── requirements.txt
├── .env.example              # Environment variable template
│
├── agents/
│   ├── orchestrator.py       # Central brain — routes through all agents
│   ├── rag_researcher.py     # ChromaDB PDF ingestion + semantic search
│   ├── architect_agent.py    # System architecture + tech stack + APIs
│   ├── business_agent.py     # BMC + budget + government schemes
│   └── debate_room.py        # AI Self-Critic Loop (Security + Finance critics)
│
├── routes/
│   ├── project_api.py        # /api/orchestrate, /api/upload_rag, /api/debate_stream
│   └── export_api.py         # /api/export_pdf
│
├── templates/
│   └── index.html            # Single-page Bootstrap 5 dark SaaS dashboard
│
└── static/
    ├── style.css             # Dark-mode enterprise theme (CSS custom properties)
    └── script.js             # Async API calls, vis-network graph, Chart.js radar
```

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone <repo-url> && cd genesis-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in IBM_CLOUD_API_KEY, PROJECT_ID, IBM_CLOUD_URL
```

### 3. (Optional) Install wkhtmltopdf for PDF export

```bash
# macOS
brew install wkhtmltopdf

# Ubuntu / Debian
sudo apt-get install wkhtmltopdf
```

### 4. Run the development server

```bash
python app.py
# → http://localhost:5000
```

### 5. Production deployment

```bash
gunicorn "app:create_app()" --bind 0.0.0.0:5000 --workers 4
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/orchestrate` | Run full multi-agent pipeline |
| `POST` | `/api/upload_rag` | Upload PDF to ChromaDB knowledge base |
| `GET`  | `/api/debate_stream?project_id=<id>` | Retrieve debate transcript |
| `GET`  | `/api/projects` | List all saved projects |
| `GET`  | `/api/projects/<id>` | Get single project |
| `POST` | `/api/export_pdf` | Generate PDF report download |

---

## Frontend Tabs

| Tab | Features |
|-----|----------|
| **Live Agent Workflow** | vis-network knowledge graph · 7-stage pipeline animation |
| **AI Debate Room** | Live chat transcript · Agent roster · Score chips |
| **Solution Analytics** | Chart.js radar chart · 3 solution cards · What-If simulator |
| **RAG & Export** | PDF drop-zone · Semantic search · Patent novelty · PDF export |

---

## Three Solution Variants

| Solution | Focus |
|----------|-------|
| **A — Low Cost** | Open-source tooling, shared cloud, phased delivery |
| **B — High Performance** | Managed cloud, auto-scaling, enterprise SLAs |
| **C — Eco-Friendly** | Green cloud regions, serverless, carbon reporting |

---

## Debate Room Thresholds

- **Innovation Score** ≥ 7/10 (Security Agent)
- **Cost Efficiency** ≥ 6/10 (Finance Agent)
- **Max Rounds:** 3 (forced acceptance after 3 iterations)
