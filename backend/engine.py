"""
Graph query engine — wraps NetworkX graph with LLM-powered natural language interface.
Uses Google Gemini via LangChain with strict guardrails.
"""

import os
import re
import pickle
import networkx as nx
from pathlib import Path
from collections import deque
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Guardrail system prompt (injected verbatim into every LLM call) ──

SYSTEM_PROMPT = """You are a data analyst assistant for a supply chain dataset.
You ONLY answer questions about: Orders, Deliveries, Invoices, Payments, Customers, Products, and Addresses in this dataset.

If the user asks ANYTHING outside this domain — general knowledge, creative writing, coding help, opinions, or any other topic — respond with EXACTLY this string and nothing else:
"This system is designed to answer questions related to the provided dataset only."

Never hallucinate data. Every claim must come from query results.
If a query returns no results, say so explicitly."""

# ── Graph schema description for the LLM ──

GRAPH_SCHEMA = """
GRAPH SCHEMA (NetworkX DiGraph):
Node labels and their key properties:
- Customer: id, name, category, creationDate
- SalesOrder: id, salesOrderType, creationDate, totalNetAmount, transactionCurrency, overallDeliveryStatus, soldToParty, requestedDeliveryDate
- SalesOrderItem: id, salesOrder, salesOrderItem, material, requestedQuantity, netAmount, transactionCurrency, materialGroup, productionPlant
- Delivery: id, creationDate, actualGoodsMovementDate, overallGoodsMovementStatus, overallPickingStatus, shippingPoint
- BillingDocument: id, billingDocumentType, creationDate, billingDocumentDate, totalNetAmount, transactionCurrency, isCancelled, accountingDocument, soldToParty
- Payment: id, accountingDocument, clearingDate, postingDate, amountInTransactionCurrency, transactionCurrency, customer, glAccount
- Product: id, productType, description, grossWeight, netWeight, baseUnit, productGroup, division
- Plant: id, plantName, salesOrganization
- Address: id, businessPartner, addressId, city, country, region, street, postalCode

Edge types (directed):
- Customer -[PLACED]-> SalesOrder
- SalesOrder -[CONTAINS]-> SalesOrderItem
- SalesOrderItem -[IS_MATERIAL]-> Product
- SalesOrder -[HAS_DELIVERY]-> Delivery
- Delivery -[SHIPPED_FROM]-> Plant
- Delivery -[HAS_INVOICE]-> BillingDocument
- BillingDocument -[SETTLED_BY]-> Payment
- Customer -[HAS_ADDRESS]-> Address

Node IDs are formatted as "Label:value" (e.g., "Customer:320000082", "SalesOrder:740532").
Access node properties with G.nodes[node_id]["property_name"].
Iterate with: for node, data in G.nodes(data=True): if data.get("label") == "SalesOrder": ...
Get neighbors: list(G.successors(node_id)), list(G.predecessors(node_id))
Get edges: G.out_edges(node_id), G.in_edges(node_id), G.edges(data=True)
Edge type is stored as: G.edges[u, v]["type"] (e.g., "PLACED", "HAS_INVOICE")

WORKING CODE EXAMPLES:

# Find all sales orders for a customer:
for _, target in G.out_edges("Customer:310000108"):
    if G.nodes[target].get("label") == "SalesOrder":
        print(target, G.nodes[target])

# Trace a billing document upstream to its delivery:
for source, _ in G.in_edges("BillingDocument:90504298"):
    if G.nodes[source].get("label") == "Delivery":
        print("Delivery:", source)

# Count sales orders per customer:
from collections import Counter
counts = Counter()
for node, data in G.nodes(data=True):
    if data.get("label") == "Customer":
        for _, target in G.out_edges(node):
            if G.nodes[target].get("label") == "SalesOrder":
                counts[node] += 1

# Trace full O2C path: Customer -> SalesOrder -> Delivery -> BillingDocument -> Payment
# Use G.out_edges for forward traversal, G.in_edges for backward traversal
"""

# ── Query generation prompt ──

QUERY_PROMPT_TEMPLATE = """You have access to a NetworkX DiGraph named `G` containing supply chain data.

{schema}

Given the user's question, write Python code that queries the graph `G` to answer it.
The code MUST:
1. Use only `G`, `nx` (networkx), and standard Python libraries (no imports needed).
2. Store the final answer in a variable called `result` — it should be a string suitable for display.
3. Also store any relevant node IDs in a list called `node_ids` (e.g., ["Customer:320000082", "SalesOrder:740532"]).
4. Be safe — no file operations, no network calls, no exec/eval of external input.
5. Handle edge cases: if no data is found, set result to explain that.

IMPORTANT: Return ONLY the Python code, no markdown fences, no explanation.

User question: {question}
"""


class GraphQueryEngine:
    def __init__(self):
        self.graph = self._load_graph()
        api_key = os.getenv("GEMINI_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0,
            max_retries=2,
        )
        print(f"  ✅ LLM configured: gemini-2.5-flash")
        self.conversation_history = deque(maxlen=10)  # last 5 turns = 10 messages

    def _load_graph(self):
        graph_path = PROJECT_ROOT / "data" / "graph.pkl"
        if not graph_path.exists():
            raise FileNotFoundError(
                f"Graph not found at {graph_path}. Run scripts/load_graph.py first."
            )
        with open(graph_path, "rb") as f:
            G = pickle.load(f)
        print(f"  ✅ Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G

    def _is_off_topic(self, question: str) -> bool:
        """Quick pre-check for obviously off-topic questions."""
        supply_chain_keywords = [
            "order", "deliver", "invoice", "bill", "payment", "customer",
            "product", "material", "plant", "address", "sales", "ship",
            "amount", "currency", "trace", "flow", "cancel", "settle",
            "quantity", "billing", "document", "incomplete", "delay",
            "average", "total", "count", "highest", "lowest", "most",
        ]
        q_lower = question.lower()
        return not any(kw in q_lower for kw in supply_chain_keywords)

    def _execute_graph_code(self, code: str) -> tuple:
        """Safely execute LLM-generated graph query code."""
        # Remove markdown fences if present
        code = re.sub(r"```python\s*", "", code)
        code = re.sub(r"```\s*", "", code)
        code = code.strip()

        # Safety checks
        forbidden = ["import os", "import sys", "open(", "exec(", "eval(",
                      "subprocess", "__import__", "shutil", "pathlib"]
        for f in forbidden:
            if f in code:
                return f"Code safety violation: '{f}' is not allowed.", []

        # Execute in sandboxed namespace
        namespace = {"G": self.graph, "nx": nx}
        try:
            exec(code, namespace)
        except Exception as e:
            return f"Query execution error: {str(e)}", []

        result = namespace.get("result", "No result was produced by the query.")
        node_ids = namespace.get("node_ids", [])

        # Ensure result is a string
        if not isinstance(result, str):
            result = str(result)

        return result, node_ids

    def _invoke_llm(self, messages):
        """Invoke LLM with error handling for quota/rate limits."""
        try:
            return self.llm.invoke(messages)
        except Exception as e:
            err_str = str(e).lower()
            if "quota" in err_str or "429" in err_str or "rate" in err_str:
                raise RuntimeError("Gemini API quota exceeded. Please wait a minute and try again, or upgrade your API plan.")
            raise

    def query(self, question: str) -> dict:
        """Process a natural language question and return answer + node IDs."""
        guardrail_response = "This system is designed to answer questions related to the provided dataset only."

        # Step 1: Off-topic pre-filter
        if self._is_off_topic(question):
            try:
                messages = [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=question),
                ]
                response = self._invoke_llm(messages)
                answer = response.content.strip()
            except Exception:
                pass
            return {"answer": guardrail_response, "node_ids": [], "query_code": None}

        # Step 2: Generate graph query code
        query_prompt = QUERY_PROMPT_TEMPLATE.format(
            schema=GRAPH_SCHEMA,
            question=question,
        )

        # Build messages with conversation history for context
        messages = [
            SystemMessage(content=SYSTEM_PROMPT + "\n\n" + query_prompt),
        ]
        # Add conversation history
        for msg in self.conversation_history:
            messages.append(msg)
        messages.append(HumanMessage(content=question))

        response = self._invoke_llm(messages)
        generated_code = response.content.strip()

        # Step 3: Execute the generated code
        result, node_ids = self._execute_graph_code(generated_code)

        # Step 4: Generate natural language answer from results
        answer_messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"""The user asked: "{question}"

The graph query returned this raw result:
{result}

Referenced node IDs: {node_ids[:20]}

Please provide a clear, well-formatted answer to the user's question based on these results.
Use the data directly — do not hallucinate or add information not in the results.
If the result indicates no data was found, say so explicitly."""),
        ]

        answer_response = self._invoke_llm(answer_messages)
        final_answer = answer_response.content.strip()

        # Update conversation history
        self.conversation_history.append(HumanMessage(content=question))
        self.conversation_history.append(AIMessage(content=final_answer))

        return {
            "answer": final_answer,
            "node_ids": node_ids if isinstance(node_ids, list) else [],
            "query_code": generated_code,
        }

    async def query_stream(self, question: str):
        """Stream the query response token by token."""
        guardrail_response = "This system is designed to answer questions related to the provided dataset only."

        # Step 1: Off-topic pre-filter
        if self._is_off_topic(question):
            yield {"type": "answer", "content": guardrail_response}
            yield {"type": "node_ids", "content": []}
            yield {"type": "done", "content": ""}
            return

        try:
            # Step 2: Generate graph query code
            yield {"type": "status", "content": "Analyzing your question..."}

            query_prompt = QUERY_PROMPT_TEMPLATE.format(
                schema=GRAPH_SCHEMA,
                question=question,
            )

            messages = [
                SystemMessage(content=SYSTEM_PROMPT + "\n\n" + query_prompt),
            ]
            for msg in self.conversation_history:
                messages.append(msg)
            messages.append(HumanMessage(content=question))

            response = self._invoke_llm(messages)
            generated_code = response.content.strip()

            yield {"type": "status", "content": "Querying the graph..."}

            # Step 3: Execute
            result, node_ids = self._execute_graph_code(generated_code)

            yield {"type": "status", "content": "Generating answer..."}

            # Step 4: Stream the natural language answer
            answer_messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"""The user asked: "{question}"

The graph query returned this raw result:
{result}

Referenced node IDs: {node_ids[:20]}

Please provide a clear, well-formatted answer to the user's question based on these results.
Use the data directly — do not hallucinate or add information not in the results.
If the result indicates no data was found, say so explicitly."""),
            ]

            full_answer = ""
            async for chunk in self.llm.astream(answer_messages):
                token = chunk.content
                if token:
                    full_answer += token
                    yield {"type": "token", "content": token}

            # Send node IDs at the end
            yield {"type": "node_ids", "content": node_ids if isinstance(node_ids, list) else []}

            # Update conversation history
            self.conversation_history.append(HumanMessage(content=question))
            self.conversation_history.append(AIMessage(content=full_answer))

            yield {"type": "done", "content": ""}

        except Exception as e:
            yield {"type": "token", "content": f"Error: {str(e)}"}
            yield {"type": "node_ids", "content": []}
            yield {"type": "done", "content": ""}

    def get_graph_data(self) -> dict:
        """Return the full graph as nodes/edges JSON for visualization."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            node_data = {k: v for k, v in data.items() if v and str(v) != "nan"}
            node_data["node_id"] = node_id
            nodes.append(node_data)

        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "type": data.get("type", "UNKNOWN"),
            })

        return {"nodes": nodes, "edges": edges}
