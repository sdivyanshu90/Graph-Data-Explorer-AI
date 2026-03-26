# Graph Data Explorer AI

> An interactive graph-based data modeling and natural language query system built on SAP Order-to-Cash data.  
> Ask questions in plain English — the AI writes graph queries, executes them, and streams back answers with visual highlights.

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Request Lifecycle](#request-lifecycle)
- [Data Pipeline](#data-pipeline)
- [Graph Schema](#graph-schema)
- [LLM Query Engine](#llm-query-engine)
- [Frontend Visualization](#frontend-visualization)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Guardrails & Safety](#guardrails--safety)

---

## Overview

This project transforms flat SAP Order-to-Cash transactional data (19 JSONL tables, 21,393 records) into a **knowledge graph** (765 nodes, 877 edges) and exposes it through:

1. **A natural language query engine** — powered by Google Gemini 2.5 Flash — that converts English questions into Python graph traversals
2. **An interactive graph visualization** — React Flow with force-directed layout, color-coded entity types, hover effects, and query-result highlighting
3. **A streaming chat interface** — SSE-based real-time token delivery with Markdown rendering

```mermaid
flowchart LR
    User([User]) -->|"Natural language"| Chat[Chat Panel]
    Chat -->|SSE| API[FastAPI Backend]
    API -->|"Python code gen"| LLM[Gemini 2.5 Flash]
    LLM -->|"Graph traversal code"| API
    API -->|"exec() sandbox"| Graph[(NetworkX DiGraph)]
    Graph -->|"Raw result"| API
    API -->|"NL answer + node IDs"| Chat
    Chat -->|"Highlight nodes"| Viz[Graph Panel]
```

---

## System Architecture

```mermaid
graph TB
    subgraph Frontend ["Frontend (React + Vite)"]
        App[App.jsx]
        GP[GraphPanel.jsx<br/>Force-directed layout]
        CP[ChatPanel.jsx<br/>SSE streaming]
        CN[CustomNode.jsx<br/>Glassmorphism nodes]
        ND[NodeDrawer.jsx<br/>Property inspector]
        App --> GP
        App --> CP
        App --> ND
        GP --> CN
    end

    subgraph Backend ["Backend (FastAPI)"]
        Main[main.py<br/>CORS + SSE endpoints]
        Engine[engine.py<br/>Query pipeline]
        Main --> Engine
    end

    subgraph LLM ["LLM Layer"]
        Gemini[Google Gemini 2.5 Flash<br/>via LangChain]
        Guard[Guardrail System<br/>Keyword + prompt-based]
    end

    subgraph Data ["Data Layer"]
        PKL[(graph.pkl<br/>765 nodes · 877 edges)]
        CSV[19 cleaned CSVs]
        JSONL[SAP JSONL source]
    end

    Frontend -->|"HTTP + SSE"| Backend
    Engine --> Gemini
    Engine --> Guard
    Engine --> PKL
    JSONL -->|"ingest.py"| CSV
    CSV -->|"load_graph.py"| PKL

    style Frontend fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style Backend fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style LLM fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style Data fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
```

---

## Request Lifecycle

```mermaid
sequenceDiagram
    actor User
    participant Chat as ChatPanel
    participant API as FastAPI
    participant Guard as Guardrails
    participant LLM as Gemini 2.5 Flash
    participant Graph as NetworkX

    User->>Chat: Types question
    Chat->>API: POST /query (SSE)
    API->>Guard: Keyword pre-filter

    alt Off-topic detected
        Guard-->>API: Blocked
        API-->>Chat: event: token → rejection message
        API-->>Chat: event: done
    else On-topic
        API-->>Chat: event: status → "Analyzing..."
        API->>LLM: System prompt + schema + question
        LLM-->>API: Python graph traversal code
        API-->>Chat: event: status → "Querying the graph..."
        API->>Graph: exec() in sandbox
        Graph-->>API: result string + node_ids[]
        API-->>Chat: event: status → "Generating answer..."
        API->>LLM: Raw result → natural language
        loop Token streaming
            LLM-->>API: chunk
            API-->>Chat: event: token → chunk
        end
        API-->>Chat: event: node_ids → [ids]
        API-->>Chat: event: done
        Chat->>Chat: Highlight nodes on graph
    end
```

---

## Data Pipeline

```mermaid
flowchart LR
    subgraph Source ["Raw Data"]
        ZIP[sap-order-to-cash-dataset.zip]
        JSONL["19 JSONL files<br/>21,393 records"]
    end

    subgraph Ingestion ["scripts/ingest.py"]
        Parse["Parse JSONL<br/>Flatten nested JSON"]
        Clean["Clean & deduplicate<br/>Handle NaN values"]
        Write["Write 19 CSVs"]
    end

    subgraph GraphBuild ["scripts/load_graph.py"]
        Nodes["Create 765 nodes<br/>9 entity types"]
        Edges["Create 877 edges<br/>8 relationship types"]
        Serialize["Pickle → graph.pkl"]
    end

    ZIP --> JSONL --> Parse --> Clean --> Write
    Write --> Nodes --> Edges --> Serialize
```

### Source Tables (19 JSONL → CSV)

| Category | Tables                                                                                                               |
| -------- | -------------------------------------------------------------------------------------------------------------------- |
| Sales    | `sales_order_headers`, `sales_order_items`, `sales_order_schedule_lines`                                             |
| Delivery | `outbound_delivery_headers`, `outbound_delivery_items`                                                               |
| Billing  | `billing_document_headers`, `billing_document_items`, `billing_document_cancellations`                               |
| Payment  | `payments_accounts_receivable`, `journal_entry_items_accounts_receivable`                                            |
| Master   | `business_partners`, `business_partner_addresses`, `customer_company_assignments`, `customer_sales_area_assignments` |
| Product  | `products`, `product_descriptions`, `product_plants`, `product_storage_locations`                                    |
| Org      | `plants`                                                                                                             |

---

## Graph Schema

```mermaid
erDiagram
    Customer ||--o{ SalesOrder : PLACED
    Customer ||--o{ Address : HAS_ADDRESS
    SalesOrder ||--o{ SalesOrderItem : CONTAINS
    SalesOrderItem }o--|| Product : IS_MATERIAL
    SalesOrder ||--o{ Delivery : HAS_DELIVERY
    Delivery }o--|| Plant : SHIPPED_FROM
    Delivery ||--o{ BillingDocument : HAS_INVOICE
    BillingDocument ||--o{ Payment : SETTLED_BY

    Customer {
        string id
        string name
        string category
        date creationDate
    }
    SalesOrder {
        string id
        string salesOrderType
        float totalNetAmount
        string overallDeliveryStatus
        string soldToParty
    }
    SalesOrderItem {
        string id
        string material
        float requestedQuantity
        float netAmount
    }
    Delivery {
        string id
        date actualGoodsMovementDate
        string overallGoodsMovementStatus
        string shippingPoint
    }
    BillingDocument {
        string id
        string billingDocumentType
        float totalNetAmount
        boolean isCancelled
    }
    Payment {
        string id
        date clearingDate
        float amountInTransactionCurrency
        string glAccount
    }
    Product {
        string id
        string productType
        string description
        float grossWeight
    }
    Plant {
        string id
        string plantName
        string salesOrganization
    }
    Address {
        string id
        string city
        string country
        string street
    }
```

### Node Counts

| Entity          |   Count | Example ID                 |
| --------------- | ------: | -------------------------- |
| Customer        |       8 | `Customer:320000082`       |
| SalesOrder      |     100 | `SalesOrder:740532`        |
| SalesOrderItem  |     167 | `SalesOrderItem:740532-10` |
| Delivery        |      86 | `Delivery:80016100`        |
| BillingDocument |     163 | `BillingDocument:90504298` |
| Payment         |     120 | `Payment:1400000051`       |
| Product         |      69 | `Product:TG11`             |
| Plant           |      44 | `Plant:1010`               |
| Address         |       8 | `Address:320000082-1`      |
| **Total**       | **765** |                            |

### Edge Types (877 total)

| Relationship                | Direction      | Edge Type                |
| --------------------------- | -------------- | ------------------------ |
| Customer → SalesOrder       | `PLACED`       | Customer placed an order |
| SalesOrder → SalesOrderItem | `CONTAINS`     | Order line items         |
| SalesOrderItem → Product    | `IS_MATERIAL`  | Material reference       |
| SalesOrder → Delivery       | `HAS_DELIVERY` | Fulfillment link         |
| Delivery → Plant            | `SHIPPED_FROM` | Shipping origin          |
| Delivery → BillingDocument  | `HAS_INVOICE`  | Invoice generation       |
| BillingDocument → Payment   | `SETTLED_BY`   | Payment settlement       |
| Customer → Address          | `HAS_ADDRESS`  | Customer address         |

---

## LLM Query Engine

The engine uses a **two-phase LLM pipeline** to convert natural language into graph answers:

```mermaid
flowchart TD
    Q["User Question"] --> KW{"Keyword<br/>Pre-filter"}
    KW -->|"Off-topic"| REJECT["Return rejection message<br/>(no LLM call)"]
    KW -->|"On-topic"| GEN["Phase 1: Code Generation<br/>LLM generates Python code<br/>using GRAPH_SCHEMA + examples"]
    GEN --> SAFE{"Safety Check<br/>No os/sys/open/exec/eval"}
    SAFE -->|"Blocked"| ERR["Return safety error"]
    SAFE -->|"Clean"| EXEC["exec() in sandbox<br/>namespace = {G, nx}"]
    EXEC --> RES["result string + node_ids list"]
    RES --> NL["Phase 2: Answer Generation<br/>LLM converts raw data<br/>to natural language"]
    NL --> STREAM["Stream tokens via SSE"]

    style REJECT fill:#dc2626,stroke:#f87171,color:#fef2f2
    style ERR fill:#dc2626,stroke:#f87171,color:#fef2f2
    style STREAM fill:#059669,stroke:#34d399,color:#d1fae5
```

### Key Design Decisions

| Decision                                      | Rationale                                                                                             |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Keyword pre-filter before LLM**             | Saves API calls + latency for obviously off-topic questions like "write me a poem"                    |
| **Working code examples in schema**           | Dramatically improved code generation quality — LLM copies patterns instead of guessing API           |
| **Sandboxed exec()**                          | Forbidden list blocks `os`, `sys`, `open`, `subprocess`, `__import__`, `eval`, `exec`                 |
| **Two-phase pipeline**                        | Phase 1 (code gen) + Phase 2 (NL answer) — separating concerns improves both accuracy and readability |
| **Conversation history (deque, 10 messages)** | Enables follow-up questions without losing context                                                    |

---

## Frontend Visualization

```mermaid
graph TD
    subgraph Layout ["Force-Directed Layout Engine"]
        Radial["Radial grouping by entity type"]
        Spring["Spring attraction (k=0.02)"]
        Repel["Repulsion (8000)"]
        Gravity["Center gravity (0.001)"]
        Damp["80 iterations, damping=0.85"]
        Radial --> Spring --> Repel --> Gravity --> Damp
    end

    subgraph Interaction ["User Interactions"]
        Hover["Hover: Dim non-neighbors<br/>Glow connected edges"]
        Click["Click: Open property drawer"]
        Filter["Legend: Toggle entity types"]
        Highlight["Query result: Gold glow<br/>+ scale 1.25x for 10s"]
        Pan["Pan / Zoom / MiniMap"]
    end

    subgraph Style ["Visual Design"]
        Glass["Glassmorphism nodes<br/>Translucent + backdrop blur"]
        Colors["9 distinct entity colors<br/>+ 8 edge colors"]
        Arrows["Arrow markers on edges"]
        Anim["Animated highlighted edges"]
    end

    Layout --> Interaction
    Interaction --> Style
```

### Component Responsibilities

| Component        | Lines | Role                                                                                         |
| ---------------- | ----: | -------------------------------------------------------------------------------------------- |
| `GraphPanel.jsx` |  ~300 | Force layout algorithm, React Flow orchestration, legend with filters, hover/highlight logic |
| `CustomNode.jsx` |   ~70 | Glassmorphism rendering, glow effects, dim/blur states, type badge + name + ID display       |
| `ChatPanel.jsx`  |  ~230 | SSE stream reader, Markdown rendering, example queries, message history                      |
| `NodeDrawer.jsx` |   ~35 | Slide-out property inspector for clicked nodes                                               |
| `App.jsx`        |   ~75 | Layout shell, graph data fetch, highlight state management                                   |

---

## Project Structure

```
Graph-Data-Explorer-AI/
├── backend/
│   ├── engine.py              # LLM query engine (two-phase pipeline)
│   └── main.py                # FastAPI app (SSE + REST endpoints)
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Root component + state management
│   │   ├── index.css          # Tailwind + custom animations
│   │   └── components/
│   │       ├── GraphPanel.jsx # Force layout + React Flow
│   │       ├── CustomNode.jsx # Glassmorphism node renderer
│   │       ├── ChatPanel.jsx  # SSE chat with Markdown
│   │       └── NodeDrawer.jsx # Node property drawer
│   ├── index.html
│   ├── tailwind.config.js
│   └── vite.config.js
├── scripts/
│   ├── ingest.py              # JSONL → cleaned CSV (19 tables)
│   ├── load_graph.py          # CSV → NetworkX graph → graph.pkl
│   ├── test_engine.py         # 4 end-to-end query tests
│   └── verify_connectivity.py # Graph connectivity checks
├── data/
│   ├── sap-o2c-data/          # Raw JSONL source files
│   ├── cleaned/               # 19 processed CSVs
│   └── graph.pkl              # Serialized NetworkX DiGraph
├── .env                       # GEMINI_API_KEY
├── .gitignore
├── docker-compose.yml         # Optional Neo4j setup
├── start.sh                   # One-command launcher
└── README.md
```

---

## Tech Stack

```mermaid
block-beta
    columns 3

    block:frontend["Frontend"]:3
        React["React 18"]
        Vite["Vite 5"]
        Tailwind["Tailwind CSS 3"]
        ReactFlow["@xyflow/react 12"]
        Markdown["react-markdown"]
    end

    block:backend["Backend"]:3
        FastAPI["FastAPI"]
        SSE["sse-starlette"]
        LangChain["LangChain 0.3"]
        Gemini["Gemini 2.5 Flash"]
        NetworkX["NetworkX 3.4"]
    end

    block:data["Data"]:3
        Pandas["Pandas"]
        Pickle["Python pickle"]
        JSONL["JSONL / CSV"]
    end
```

| Layer        | Technologies                                                           |
| ------------ | ---------------------------------------------------------------------- |
| **Frontend** | React 18, Vite 5, Tailwind CSS 3, @xyflow/react 12, react-markdown     |
| **Backend**  | FastAPI, Uvicorn, sse-starlette, python-dotenv                         |
| **LLM**      | Google Gemini 2.5 Flash, LangChain 0.3.7, langchain-google-genai 2.0.4 |
| **Graph**    | NetworkX 3.4.2, pickle serialization                                   |
| **Data**     | Pandas, JSONL/CSV processing                                           |

---

## Getting Started

### Prerequisites

- **Python 3.10+** with `venv`
- **Node.js 18+** with `npm`
- **Google Gemini API Key** — [Get one here](https://aistudio.google.com/apikey)

### Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd Graph-Data-Explorer-AI

# 2. Set up environment
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sse-starlette python-dotenv \
            networkx pandas langchain langchain-google-genai

# 3. Configure API key
echo 'GEMINI_API_KEY=your-key-here' > .env

# 4. Ingest data & build graph
python scripts/ingest.py       # JSONL → 19 CSVs
python scripts/load_graph.py   # CSVs → graph.pkl (765 nodes, 877 edges)

# 5. Start backend
cd backend && uvicorn main:app --port 8002 &

# 6. Start frontend
cd ../frontend && npm install && npm run dev
```

Or use the convenience script:

```bash
chmod +x start.sh && ./start.sh
```

Open **http://localhost:5173** — the graph loads automatically. Type a question in the chat panel.

### Example Queries

| Query                                            | What it does                                                     |
| ------------------------------------------------ | ---------------------------------------------------------------- |
| "How many sales orders does each customer have?" | Counts orders per customer with node IDs                         |
| "Trace the full journey of Sales Order 740532"   | Follows O2C path: order → items → delivery → invoices → payments |
| "Which billing documents are cancelled?"         | Filters by `isCancelled` property                                |
| "Show deliveries with incomplete goods movement" | Checks `overallGoodsMovementStatus` field                        |

---

## API Reference

### `GET /health`

Returns backend status and graph statistics.

```json
{
  "status": "healthy",
  "engine": "networkx",
  "graph": { "nodes": 765, "edges": 877 }
}
```

### `GET /graph`

Returns the full graph as JSON for visualization.

```json
{
  "nodes": [
    { "node_id": "Customer:320000082", "label": "Customer", "name": "..." }
  ],
  "edges": [
    {
      "source": "Customer:320000082",
      "target": "SalesOrder:740532",
      "type": "PLACED"
    }
  ]
}
```

### `POST /query` (SSE Streaming)

**Body:** `{"question": "How many customers are there?"}`

**SSE Events:**
| Event | Payload | Description |
|-------|---------|-------------|
| `status` | `{"content": "Analyzing..."}` | Progress indicator |
| `token` | `{"content": "There"}` | Streamed answer token |
| `node_ids` | `{"node_ids": ["Customer:320000082"]}` | Referenced graph nodes |
| `done` | `{"content": ""}` | Stream complete |
| `error` | `{"error": "..."}` | Error occurred |

### `POST /query/sync`

Non-streaming version for testing. Same body, returns full JSON response.

### `GET /graph/schema`

Returns the graph schema description used by the LLM.

---

## Guardrails & Safety

```mermaid
flowchart LR
    Q["User Input"] --> KW{"30 supply-chain<br/>keywords check"}
    KW -->|"None match"| LLM_CHECK["LLM with strict<br/>system prompt"]
    KW -->|"Match found"| PROCEED["Process query"]
    LLM_CHECK -->|"Off-topic"| BLOCK["❌ Rejection message"]
    PROCEED --> CODE["Generated Python code"]
    CODE --> FORBIDDEN{"Forbidden tokens:<br/>os, sys, open, exec,<br/>eval, subprocess,<br/>__import__, shutil"}
    FORBIDDEN -->|"Found"| BLOCK2["❌ Safety violation"]
    FORBIDDEN -->|"Clean"| SANDBOX["exec() with<br/>namespace = {G, nx} only"]
```

**Three layers of protection:**

1. **Keyword pre-filter** — 30 supply-chain keywords (`order`, `deliver`, `invoice`, `payment`, `customer`, `product`, etc.). If none match, the question is likely off-topic → sent to LLM with strict system prompt that only allows the rejection message.

2. **Code safety scan** — Before execution, generated code is checked for forbidden patterns: `import os`, `import sys`, `open(`, `exec(`, `eval(`, `subprocess`, `__import__`, `shutil`, `pathlib`.

3. **Sandboxed execution** — Code runs in a restricted namespace containing only `G` (the graph) and `nx` (NetworkX). No access to file system, network, or dangerous builtins.

---

### Development Phases

```mermaid
gantt
    title Development Phases
    dateFormat X
    axisFormat %s

    section Phase 1
    Environment & Data Ingestion     :done, p1, 0, 1

    section Phase 2
    Graph Construction (765 nodes)   :done, p2, 1, 2

    section Phase 3
    Backend API + LLM Engine         :done, p3, 2, 3

    section Phase 4
    Frontend (React Flow + Chat)     :done, p4, 3, 4

    section Phase 5
    Documentation & Polish           :done, p5, 4, 5

    section Post-Launch
    Bug Fixes & Visual Overhaul      :done, p6, 5, 6
```

### Key Prompts & Workflows

| Phase                  | Prompt / Task                                                                | AI Contribution                                                             |
| ---------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Data Ingestion**     | "Parse 19 JSONL tables, flatten nested JSON, clean NaN values, deduplicate"  | Complete `ingest.py` script — handles all 19 table schemas                  |
| **Graph Construction** | "Build NetworkX DiGraph from CSVs with typed nodes and directed edges"       | Node/edge creation with 8 relationship types, ID formatting (`Label:value`) |
| **Query Engine**       | "Two-phase LLM pipeline: NL → Python code → exec → NL answer"                | Full `engine.py` with guardrails, sandboxing, conversation history          |
| **Schema Enhancement** | "Add working Python code examples to GRAPH_SCHEMA"                           | Key breakthrough — LLM code-gen accuracy jumped dramatically                |
| **Frontend**           | "React Flow graph with force-directed layout, SSE streaming chat"            | All 5 components, force layout algorithm, SSE parser                        |
| **Visual Overhaul**    | "Glassmorphism nodes, hover dimming, color-coded edges, animated highlights" | Complete rewrite of `GraphPanel.jsx` and `CustomNode.jsx`                   |

### Lessons Learned

1. **Schema examples > schema descriptions** — Adding working Python code examples to the LLM's graph schema prompt was the single most impactful improvement. The LLM went from broken traversals to correct queries immediately.

2. **Port management matters** — In long development sessions, zombie processes and stale servers cause confusing failures. Always verify which process actually owns a port before debugging application code.

3. **Two-phase LLM is cleaner than one** — Separating "write code to query the graph" from "explain the results in English" produces better output for both tasks. The code-gen prompt can be technical; the answer prompt can focus on readability.

4. **Force layout needs tuning per dataset** — Repulsion = 8000, spring k = 0.02, 80 iterations worked well for ~765 nodes. Smaller graphs need less repulsion; larger graphs need more iterations and adaptive cooling.

5. **Keyword pre-filter saves cost** — A simple keyword check before LLM invocation prevents unnecessary API calls for obviously off-topic questions, reducing both latency and cost.
