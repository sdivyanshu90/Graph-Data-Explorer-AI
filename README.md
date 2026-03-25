# Graph Data Explorer AI

A graph-based data modeling and natural-language query system built on an SAP Order-to-Cash dataset. Explore supply-chain entities and their relationships through an interactive graph visualization and an LLM-powered chat assistant.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      Frontend (React)                    │
│  ┌────────────────────┐   ┌────────────────────────────┐ │
│  │  Graph Panel        │   │  Chat Panel (SSE stream)   │ │
│  │  @xyflow/react      │   │  react-markdown            │ │
│  │  color-coded nodes  │   │  example queries           │ │
│  │  node inspector     │◄──│  node highlighting         │ │
│  └────────────────────┘   └────────────────────────────┘ │
│            Vite + Tailwind CSS — localhost:5173           │
└──────────────────────┬───────────────────────────────────┘
                       │  HTTP / SSE
┌──────────────────────▼───────────────────────────────────┐
│                 Backend (FastAPI + Uvicorn)               │
│  Endpoints: /health  /graph  /query (SSE)  /query/sync   │
│  GraphQueryEngine: LangChain → Gemini 2.0 Flash          │
│  Text-to-Python chain → exec against NetworkX graph      │
│  Guardrails: keyword filter + system prompt               │
│                    localhost:8000                         │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│              Graph Engine (NetworkX DiGraph)              │
│  765 nodes · 877 edges · 9 entity types · 8 edge types   │
│  Serialized: data/graph.pkl                              │
└──────────────────────────────────────────────────────────┘

Data flow:
  JSONL dataset → ingest.py (clean) → load_graph.py (build) → graph.pkl
  graph.pkl → FastAPI (serve) → React (visualize + query)
```

## Entity Types & Relationships

| Node Type       | Count | Color  |
| --------------- | ----- | ------ |
| Customer        | 50    | Blue   |
| SalesOrder      | 100   | Purple |
| SalesOrderItem  | ~200  | Pink   |
| Product         | 50    | Rose   |
| Delivery        | 100   | Amber  |
| BillingDocument | 100   | Green  |
| Payment         | 100   | Cyan   |
| Plant           | 10    | Lime   |
| Address         | 55    | Indigo |

**Edge types:** PLACED_ORDER, HAS_ITEM, CONTAINS_PRODUCT, FULFILLED_BY, SHIPS_FROM, INVOICED_AS, PAID_BY, HAS_ADDRESS

**Sample O2C path:**
Customer → SalesOrder → Delivery → BillingDocument → Payment

---

## Project Structure

```
Graph-Data-Explorer-AI/
├── backend/
│   ├── main.py              # FastAPI app — all endpoints
│   ├── engine.py            # GraphQueryEngine (LLM + NetworkX)
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main layout (split-screen)
│   │   ├── components/
│   │   │   ├── GraphPanel.jsx   # React Flow graph vis
│   │   │   ├── CustomNode.jsx   # Color-coded node renderer
│   │   │   ├── NodeDrawer.jsx   # Side drawer for metadata
│   │   │   └── ChatPanel.jsx    # SSE chat interface
│   │   ├── main.jsx         # Entry point
│   │   └── index.css        # Tailwind + custom styles
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── postcss.config.js
├── scripts/
│   ├── ingest.py            # JSONL → cleaned CSV pipeline
│   ├── load_graph.py        # Build NetworkX + Neo4j graph
│   ├── test_engine.py       # API test suite (4 cases)
│   └── verify_connectivity.py
├── data/
│   ├── sap-o2c-data/        # Raw JSONL dataset
│   ├── cleaned/             # 19 cleaned CSV files
│   └── graph.pkl            # Serialized NetworkX graph
├── docker-compose.yml       # Neo4j container (optional)
├── .env                     # API keys & credentials
└── README.md
```

---

## Prerequisites

- **Python 3.10+** with `pip`
- **Node.js 18+** with `npm`
- **Google Gemini API key** (free tier works, with rate limits)
- _Optional:_ Docker (for Neo4j instead of NetworkX)

---

## Quick Start

### 1. Clone & configure

```bash
git clone <repo-url> && cd Graph-Data-Explorer-AI

# Create .env with your credentials
cat > .env << 'EOF'
GEMINI_API_KEY="your-gemini-api-key"
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphpassword
EOF
```

### 2. Backend setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 3. Data ingestion & graph construction

```bash
# Place your dataset zip in data/ and extract it, then:
python scripts/ingest.py       # Clean raw JSONL → data/cleaned/
python scripts/load_graph.py   # Build graph → data/graph.pkl
```

### 4. Start the backend

```bash
source venv/bin/activate
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## API Endpoints

| Method | Path            | Description                         |
| ------ | --------------- | ----------------------------------- |
| GET    | `/health`       | Server status + graph stats         |
| GET    | `/graph`        | Full graph (nodes + edges JSON)     |
| GET    | `/graph/schema` | Schema description                  |
| POST   | `/query`        | Natural-language query (SSE stream) |
| POST   | `/query/sync`   | Natural-language query (sync JSON)  |

### Query request body

```json
{ "question": "Which customers have the most sales orders?" }
```

### SSE events (streaming)

```
event: status
data: {"content": "Analyzing your question..."}

event: token
data: {"content": "Customer X has 5 sales orders..."}

event: node_ids
data: {"node_ids": ["Customer:310000108", "SalesOrder:740532"]}

event: done
data: {"content": ""}
```

---

## Guardrails

The system enforces strict domain boundaries. Any off-topic question returns:

> _This system is designed to answer questions related to the provided dataset only._

This is enforced in two layers:

1. **Keyword pre-filter** — rejects obviously off-topic questions without consuming LLM quota
2. **System prompt** — instructs the LLM to refuse non-dataset questions

---

## Tech Stack

| Layer    | Technology                                      |
| -------- | ----------------------------------------------- |
| Frontend | React 18, Vite, Tailwind CSS, @xyflow/react     |
| Backend  | FastAPI, Uvicorn, sse-starlette                 |
| LLM      | Google Gemini 2.0 Flash via LangChain           |
| Graph    | NetworkX (primary), Neo4j (optional via Docker) |
| Data     | Pandas, JSONL/CSV processing                    |
