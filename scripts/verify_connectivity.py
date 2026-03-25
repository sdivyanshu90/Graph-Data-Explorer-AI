"""Verify graph backend connectivity."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

NEO4J_AVAILABLE = False

# Try Neo4j first
try:
    from neo4j import GraphDatabase
    from dotenv import load_dotenv
    import os

    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "graphpassword")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print(f"✅ Neo4j is reachable at {uri}")
    NEO4J_AVAILABLE = True
    driver.close()
except Exception as e:
    print(f"⚠️  Neo4j not available: {e}")
    print("   Falling back to NetworkX in-memory graph engine.")

# Verify NetworkX fallback
import networkx as nx
G = nx.DiGraph()
G.add_node("test", label="Test")
G.add_edge("test", "test2", type="TEST_EDGE")
print(f"✅ NetworkX is available (v{nx.__version__})")
print(f"   In-memory graph engine ready as fallback.")

if NEO4J_AVAILABLE:
    print("\n🟢 PRIMARY ENGINE: Neo4j")
else:
    print("\n🟡 ACTIVE ENGINE: NetworkX (in-memory fallback)")
