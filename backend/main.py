"""
FastAPI Backend — Graph Data Explorer
Endpoints: /health, /graph, /query (SSE streaming)
"""

import os
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

load_dotenv()

# Import the query engine
from engine import GraphQueryEngine

app = FastAPI(title="Graph Data Explorer API", version="1.0.0")

# CORS for frontend (dev + production)
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Add production Vercel URL from environment
prod_url = os.getenv("FRONTEND_URL")
if prod_url:
    allowed_origins.append(prod_url.rstrip("/"))

# Also allow any vercel.app subdomain for preview deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize query engine at startup
engine: GraphQueryEngine = None


@app.on_event("startup")
async def startup():
    global engine
    print("🚀 Initializing Graph Query Engine...")
    engine = GraphQueryEngine()
    print("✅ Backend ready.")


@app.get("/health")
async def health():
    """Health check endpoint."""
    graph_info = {}
    if engine and engine.graph:
        graph_info = {
            "nodes": engine.graph.number_of_nodes(),
            "edges": engine.graph.number_of_edges(),
        }
    return {
        "status": "healthy",
        "engine": "networkx",
        "graph": graph_info,
    }


@app.get("/graph")
async def get_graph():
    """Return full graph as nodes/edges JSON for visualization."""
    if not engine:
        return JSONResponse(status_code=503, content={"error": "Engine not initialized"})
    data = engine.get_graph_data()
    return data


@app.post("/query")
async def query(request: Request):
    """
    Accept natural language query, return answer + node IDs via SSE.
    Body: {"question": "..."}
    """
    if not engine:
        return JSONResponse(status_code=503, content={"error": "Engine not initialized"})

    body = await request.json()
    question = body.get("question", "").strip()

    if not question:
        return JSONResponse(status_code=400, content={"error": "No question provided"})

    async def event_generator():
        try:
            async for event in engine.query_stream(question):
                event_type = event.get("type", "message")
                content = event.get("content", "")

                if event_type == "token":
                    yield {"event": "token", "data": json.dumps({"content": content})}
                elif event_type == "node_ids":
                    yield {"event": "node_ids", "data": json.dumps({"node_ids": content})}
                elif event_type == "status":
                    yield {"event": "status", "data": json.dumps({"content": content})}
                elif event_type == "done":
                    yield {"event": "done", "data": json.dumps({"content": ""})}
                elif event_type == "answer":
                    # Non-streaming full answer (for guardrail responses)
                    yield {"event": "token", "data": json.dumps({"content": content})}
                    yield {"event": "done", "data": json.dumps({"content": ""})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/query/sync")
async def query_sync(request: Request):
    """
    Synchronous query endpoint (non-streaming) for testing.
    Body: {"question": "..."}
    """
    if not engine:
        return JSONResponse(status_code=503, content={"error": "Engine not initialized"})

    body = await request.json()
    question = body.get("question", "").strip()

    if not question:
        return JSONResponse(status_code=400, content={"error": "No question provided"})

    try:
        result = engine.query(question)
        return result
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "answer": f"LLM service error: {str(e)}",
                "node_ids": [],
                "query_code": None,
            },
        )


@app.get("/graph/schema")
async def get_schema():
    """Return graph schema info."""
    if not engine:
        return JSONResponse(status_code=503, content={"error": "Engine not initialized"})
    from engine import GRAPH_SCHEMA
    return {"schema": GRAPH_SCHEMA}
