"""
Graph Construction Script
Loads cleaned SAP O2C data into a NetworkX directed graph (primary)
or Neo4j (when Docker is available). Prints schema and summary stats.

GRAPH SCHEMA:
─────────────────────────────────────────────────────────────────
NODES:
  Customer          — businessPartner, customer, name, category
  SalesOrder        — salesOrder, type, creationDate, totalNetAmount, currency, deliveryStatus
  SalesOrderItem    — salesOrder, salesOrderItem, material, quantity, netAmount
  Delivery          — deliveryDocument, creationDate, goodsMovementStatus, pickingStatus
  BillingDocument   — billingDocument, type, creationDate, totalNetAmount, isCancelled
  Payment           — accountingDocument, clearingDate, amount, currency, customer
  Product           — product, productType, description, grossWeight, baseUnit
  Plant             — plant, plantName
  Address           — businessPartner, addressId, city, country, region, street, postalCode

EDGES (directed):
  Customer      ─[PLACED]──────────► SalesOrder
  SalesOrder    ─[CONTAINS]─────────► SalesOrderItem
  SalesOrderItem─[IS_MATERIAL]──────► Product
  SalesOrder    ─[HAS_DELIVERY]─────► Delivery
  Delivery      ─[SHIPPED_FROM]─────► Plant
  Delivery      ─[HAS_INVOICE]──────► BillingDocument
  BillingDocument─[SETTLED_BY]──────► Payment
  Customer      ─[HAS_ADDRESS]──────► Address
─────────────────────────────────────────────────────────────────
"""

import os
import sys
import pandas as pd
import networkx as nx
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"

# ── Helper: load cleaned CSV ──────────────────────────────────────


def load_csv(name):
    path = CLEANED_DIR / f"{name}.csv"
    if not path.exists():
        print(f"  ⚠️ Missing: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    return df


# ── NetworkX Graph Builder ────────────────────────────────────────


def build_networkx_graph():
    """Build the full O2C graph in NetworkX."""
    G = nx.DiGraph()

    # ── Load all tables ──
    customers = load_csv("business_partners")
    addresses = load_csv("business_partner_addresses")
    sales_orders = load_csv("sales_order_headers")
    sales_order_items = load_csv("sales_order_items")
    deliveries = load_csv("outbound_delivery_headers")
    delivery_items = load_csv("outbound_delivery_items")
    billing_headers = load_csv("billing_document_headers")
    billing_items = load_csv("billing_document_items")
    journal_entries = load_csv("journal_entry_items_accounts_receivable")
    payments = load_csv("payments_accounts_receivable")
    products = load_csv("products")
    product_descs = load_csv("product_descriptions")
    plants = load_csv("plants")

    # Merge product descriptions
    prod_desc_map = {}
    if not product_descs.empty:
        prod_desc_map = dict(zip(product_descs["product"], product_descs["productDescription"]))

    # ── 1. Customer nodes ──
    print("  Loading Customer nodes...")
    for _, row in customers.iterrows():
        cid = row.get("customer") or row.get("businessPartner")
        if pd.isna(cid):
            continue
        G.add_node(f"Customer:{cid}", **{
            "id": cid,
            "label": "Customer",
            "name": row.get("businessPartnerFullName", ""),
            "category": row.get("businessPartnerCategory", ""),
            "grouping": row.get("businessPartnerGrouping", ""),
            "creationDate": row.get("creationDate", ""),
        })

    # ── 2. Address nodes + Customer→Address edges ──
    print("  Loading Address nodes...")
    for _, row in addresses.iterrows():
        bp = row.get("businessPartner")
        aid = row.get("addressId")
        if pd.isna(bp) or pd.isna(aid):
            continue
        node_id = f"Address:{bp}:{aid}"
        G.add_node(node_id, **{
            "id": f"{bp}_{aid}",
            "label": "Address",
            "businessPartner": bp,
            "addressId": aid,
            "city": row.get("cityName", ""),
            "country": row.get("country", ""),
            "region": row.get("region", ""),
            "street": row.get("streetName", ""),
            "postalCode": row.get("postalCode", ""),
        })
        cust_node = f"Customer:{bp}"
        if G.has_node(cust_node):
            G.add_edge(cust_node, node_id, type="HAS_ADDRESS")

    # ── 3. Product nodes ──
    print("  Loading Product nodes...")
    for _, row in products.iterrows():
        pid = row.get("product")
        if pd.isna(pid):
            continue
        G.add_node(f"Product:{pid}", **{
            "id": pid,
            "label": "Product",
            "productType": row.get("productType", ""),
            "description": prod_desc_map.get(pid, ""),
            "grossWeight": row.get("grossWeight", ""),
            "netWeight": row.get("netWeight", ""),
            "weightUnit": row.get("weightUnit", ""),
            "baseUnit": row.get("baseUnit", ""),
            "productGroup": row.get("productGroup", ""),
            "division": row.get("division", ""),
        })

    # ── 4. Plant nodes ──
    print("  Loading Plant nodes...")
    for _, row in plants.iterrows():
        plid = row.get("plant")
        if pd.isna(plid):
            continue
        G.add_node(f"Plant:{plid}", **{
            "id": plid,
            "label": "Plant",
            "plantName": row.get("plantName", ""),
            "salesOrganization": row.get("salesOrganization", ""),
            "distributionChannel": row.get("distributionChannel", ""),
            "language": row.get("language", ""),
        })

    # ── 5. SalesOrder nodes + Customer→SalesOrder edges ──
    print("  Loading SalesOrder nodes...")
    for _, row in sales_orders.iterrows():
        soid = row.get("salesOrder")
        if pd.isna(soid):
            continue
        G.add_node(f"SalesOrder:{soid}", **{
            "id": soid,
            "label": "SalesOrder",
            "salesOrderType": row.get("salesOrderType", ""),
            "creationDate": row.get("creationDate", ""),
            "totalNetAmount": row.get("totalNetAmount", ""),
            "transactionCurrency": row.get("transactionCurrency", ""),
            "overallDeliveryStatus": row.get("overallDeliveryStatus", ""),
            "soldToParty": row.get("soldToParty", ""),
            "requestedDeliveryDate": row.get("requestedDeliveryDate", ""),
            "customerPaymentTerms": row.get("customerPaymentTerms", ""),
        })
        # Edge: Customer → SalesOrder
        cust = row.get("soldToParty")
        if pd.notna(cust) and G.has_node(f"Customer:{cust}"):
            G.add_edge(f"Customer:{cust}", f"SalesOrder:{soid}", type="PLACED")

    # ── 6. SalesOrderItem nodes + edges ──
    print("  Loading SalesOrderItem nodes...")
    for _, row in sales_order_items.iterrows():
        soid = row.get("salesOrder")
        item = row.get("salesOrderItem")
        if pd.isna(soid) or pd.isna(item):
            continue
        node_id = f"SalesOrderItem:{soid}:{item}"
        G.add_node(node_id, **{
            "id": f"{soid}_{item}",
            "label": "SalesOrderItem",
            "salesOrder": soid,
            "salesOrderItem": item,
            "material": row.get("material", ""),
            "requestedQuantity": row.get("requestedQuantity", ""),
            "netAmount": row.get("netAmount", ""),
            "transactionCurrency": row.get("transactionCurrency", ""),
            "materialGroup": row.get("materialGroup", ""),
            "productionPlant": row.get("productionPlant", ""),
        })
        # Edge: SalesOrder → SalesOrderItem
        so_node = f"SalesOrder:{soid}"
        if G.has_node(so_node):
            G.add_edge(so_node, node_id, type="CONTAINS")
        # Edge: SalesOrderItem → Product
        mat = row.get("material")
        if pd.notna(mat) and G.has_node(f"Product:{mat}"):
            G.add_edge(node_id, f"Product:{mat}", type="IS_MATERIAL")

    # ── 7. Delivery nodes ──
    print("  Loading Delivery nodes...")
    for _, row in deliveries.iterrows():
        did = row.get("deliveryDocument")
        if pd.isna(did):
            continue
        G.add_node(f"Delivery:{did}", **{
            "id": did,
            "label": "Delivery",
            "creationDate": row.get("creationDate", ""),
            "actualGoodsMovementDate": row.get("actualGoodsMovementDate", ""),
            "overallGoodsMovementStatus": row.get("overallGoodsMovementStatus", ""),
            "overallPickingStatus": row.get("overallPickingStatus", ""),
            "shippingPoint": row.get("shippingPoint", ""),
        })

    # ── 8. Delivery items: link SalesOrder→Delivery and Delivery→Plant ──
    print("  Loading Delivery edges...")
    so_delivery_linked = set()
    for _, row in delivery_items.iterrows():
        did = row.get("deliveryDocument")
        ref_so = row.get("referenceSdDocument")
        plant = row.get("plant")

        # Edge: SalesOrder → Delivery (deduplicated per pair)
        if pd.notna(did) and pd.notna(ref_so):
            pair = (ref_so, did)
            if pair not in so_delivery_linked:
                so_node = f"SalesOrder:{ref_so}"
                del_node = f"Delivery:{did}"
                if G.has_node(so_node) and G.has_node(del_node):
                    G.add_edge(so_node, del_node, type="HAS_DELIVERY")
                    so_delivery_linked.add(pair)

        # Edge: Delivery → Plant
        if pd.notna(did) and pd.notna(plant):
            del_node = f"Delivery:{did}"
            plant_node = f"Plant:{plant}"
            if G.has_node(del_node) and G.has_node(plant_node):
                if not G.has_edge(del_node, plant_node):
                    G.add_edge(del_node, plant_node, type="SHIPPED_FROM")

    # ── 9. BillingDocument nodes ──
    print("  Loading BillingDocument nodes...")
    for _, row in billing_headers.iterrows():
        bdid = row.get("billingDocument")
        if pd.isna(bdid):
            continue
        G.add_node(f"BillingDocument:{bdid}", **{
            "id": bdid,
            "label": "BillingDocument",
            "billingDocumentType": row.get("billingDocumentType", ""),
            "creationDate": row.get("creationDate", ""),
            "billingDocumentDate": row.get("billingDocumentDate", ""),
            "totalNetAmount": row.get("totalNetAmount", ""),
            "transactionCurrency": row.get("transactionCurrency", ""),
            "isCancelled": row.get("billingDocumentIsCancelled", ""),
            "companyCode": row.get("companyCode", ""),
            "accountingDocument": row.get("accountingDocument", ""),
            "soldToParty": row.get("soldToParty", ""),
        })

    # ── 10. Billing items: link Delivery→BillingDocument ──
    print("  Loading BillingDocument edges...")
    del_billing_linked = set()
    for _, row in billing_items.iterrows():
        bdid = row.get("billingDocument")
        ref_del = row.get("referenceSdDocument")  # This references deliveryDocument

        if pd.notna(bdid) and pd.notna(ref_del):
            pair = (ref_del, bdid)
            if pair not in del_billing_linked:
                del_node = f"Delivery:{ref_del}"
                bd_node = f"BillingDocument:{bdid}"
                if G.has_node(del_node) and G.has_node(bd_node):
                    G.add_edge(del_node, bd_node, type="HAS_INVOICE")
                    del_billing_linked.add(pair)

    # ── 11. Payment nodes ──
    print("  Loading Payment nodes...")
    for _, row in payments.iterrows():
        payid = row.get("accountingDocument")
        if pd.isna(payid):
            continue
        G.add_node(f"Payment:{payid}", **{
            "id": payid,
            "label": "Payment",
            "accountingDocument": payid,
            "clearingDate": row.get("clearingDate", ""),
            "postingDate": row.get("postingDate", ""),
            "amountInTransactionCurrency": row.get("amountInTransactionCurrency", ""),
            "transactionCurrency": row.get("transactionCurrency", ""),
            "customer": row.get("customer", ""),
            "glAccount": row.get("glAccount", ""),
        })

    # ── 12. Link BillingDocument → Payment via journal entries ──
    #   billing_document_headers.billingDocument → journal.referenceDocument
    #   journal.accountingDocument → payment.clearingAccountingDocument
    print("  Linking BillingDocument → Payment...")
    # Build mapping: billingDocument → journal accountingDocuments
    billing_to_journal = {}
    for _, row in journal_entries.iterrows():
        ref_doc = row.get("referenceDocument")
        acct_doc = row.get("accountingDocument")
        if pd.notna(ref_doc) and pd.notna(acct_doc):
            billing_to_journal.setdefault(ref_doc, set()).add(acct_doc)

    # Build mapping: clearingAccountingDocument → payment accountingDocument
    clearing_to_payment = {}
    for _, row in payments.iterrows():
        clearing = row.get("clearingAccountingDocument")
        pay_doc = row.get("accountingDocument")
        if pd.notna(clearing) and pd.notna(pay_doc):
            clearing_to_payment.setdefault(clearing, set()).add(pay_doc)

    # Chain: billing → journal (acctDoc) → payment (via clearing)
    billing_payment_count = 0
    for billing_doc, journal_acct_docs in billing_to_journal.items():
        bd_node = f"BillingDocument:{billing_doc}"
        if not G.has_node(bd_node):
            continue
        for j_acct in journal_acct_docs:
            if j_acct in clearing_to_payment:
                for pay_id in clearing_to_payment[j_acct]:
                    pay_node = f"Payment:{pay_id}"
                    if G.has_node(pay_node) and not G.has_edge(bd_node, pay_node):
                        G.add_edge(bd_node, pay_node, type="SETTLED_BY")
                        billing_payment_count += 1

    print(f"    → {billing_payment_count} BillingDocument→Payment links created")

    return G


# ── Neo4j Graph Builder (for when Docker is available) ────────────


def build_neo4j_graph():
    """Load graph into Neo4j using Cypher MERGE statements."""
    from neo4j import GraphDatabase
    from dotenv import load_dotenv

    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "graphpassword")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()

    # Load all data
    customers = load_csv("business_partners")
    addresses = load_csv("business_partner_addresses")
    sales_orders = load_csv("sales_order_headers")
    sales_order_items = load_csv("sales_order_items")
    deliveries = load_csv("outbound_delivery_headers")
    delivery_items = load_csv("outbound_delivery_items")
    billing_headers = load_csv("billing_document_headers")
    billing_items = load_csv("billing_document_items")
    journal_entries = load_csv("journal_entry_items_accounts_receivable")
    payments = load_csv("payments_accounts_receivable")
    products = load_csv("products")
    product_descs = load_csv("product_descriptions")
    plants = load_csv("plants")

    prod_desc_map = {}
    if not product_descs.empty:
        prod_desc_map = dict(zip(product_descs["product"], product_descs["productDescription"]))

    with driver.session() as session:
        # Clear existing data
        session.run("MATCH (n) DETACH DELETE n")

        # Create constraints for performance
        for label, prop in [
            ("Customer", "id"), ("SalesOrder", "id"), ("Delivery", "id"),
            ("BillingDocument", "id"), ("Payment", "id"), ("Product", "id"),
            ("Plant", "id"), ("Address", "id"),
        ]:
            try:
                session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")
            except Exception:
                pass

        # Customers
        for _, row in customers.iterrows():
            cid = row.get("customer") or row.get("businessPartner")
            if pd.isna(cid):
                continue
            session.run(
                "MERGE (c:Customer {id: $id}) SET c.name = $name, c.category = $cat, c.creationDate = $cd",
                id=cid, name=row.get("businessPartnerFullName", ""),
                cat=row.get("businessPartnerCategory", ""), cd=row.get("creationDate", ""),
            )

        # Addresses + edges
        for _, row in addresses.iterrows():
            bp = row.get("businessPartner")
            aid = row.get("addressId")
            if pd.isna(bp) or pd.isna(aid):
                continue
            session.run("""
                MERGE (a:Address {id: $id})
                SET a.city = $city, a.country = $country, a.region = $region,
                    a.street = $street, a.postalCode = $postal
                WITH a
                MATCH (c:Customer {id: $bp})
                MERGE (c)-[:HAS_ADDRESS]->(a)
            """, id=f"{bp}_{aid}", city=row.get("cityName", ""),
                country=row.get("country", ""), region=row.get("region", ""),
                street=row.get("streetName", ""), postal=row.get("postalCode", ""), bp=bp)

        # Products
        for _, row in products.iterrows():
            pid = row.get("product")
            if pd.isna(pid):
                continue
            session.run(
                "MERGE (p:Product {id: $id}) SET p.productType = $pt, p.description = $desc, p.baseUnit = $bu",
                id=pid, pt=row.get("productType", ""),
                desc=prod_desc_map.get(pid, ""), bu=row.get("baseUnit", ""),
            )

        # Plants
        for _, row in plants.iterrows():
            plid = row.get("plant")
            if pd.isna(plid):
                continue
            session.run(
                "MERGE (p:Plant {id: $id}) SET p.plantName = $name",
                id=plid, name=row.get("plantName", ""),
            )

        # Sales Orders + Customer→SO edges
        for _, row in sales_orders.iterrows():
            soid = row.get("salesOrder")
            if pd.isna(soid):
                continue
            session.run("""
                MERGE (s:SalesOrder {id: $id})
                SET s.creationDate = $cd, s.totalNetAmount = $amt, s.currency = $cur,
                    s.deliveryStatus = $ds
                WITH s
                MATCH (c:Customer {id: $cust})
                MERGE (c)-[:PLACED]->(s)
            """, id=soid, cd=row.get("creationDate", ""),
                amt=row.get("totalNetAmount", ""), cur=row.get("transactionCurrency", ""),
                ds=row.get("overallDeliveryStatus", ""), cust=row.get("soldToParty", ""))

        # Sales Order Items + edges
        for _, row in sales_order_items.iterrows():
            soid = row.get("salesOrder")
            item = row.get("salesOrderItem")
            mat = row.get("material")
            if pd.isna(soid) or pd.isna(item):
                continue
            session.run("""
                MERGE (si:SalesOrderItem {id: $id})
                SET si.material = $mat, si.quantity = $qty, si.netAmount = $amt
                WITH si
                MATCH (s:SalesOrder {id: $soid})
                MERGE (s)-[:CONTAINS]->(si)
            """, id=f"{soid}_{item}", mat=mat or "",
                qty=row.get("requestedQuantity", ""), amt=row.get("netAmount", ""), soid=soid)
            if pd.notna(mat):
                session.run("""
                    MATCH (si:SalesOrderItem {id: $siid})
                    MATCH (p:Product {id: $pid})
                    MERGE (si)-[:IS_MATERIAL]->(p)
                """, siid=f"{soid}_{item}", pid=mat)

        # Deliveries
        for _, row in deliveries.iterrows():
            did = row.get("deliveryDocument")
            if pd.isna(did):
                continue
            session.run(
                "MERGE (d:Delivery {id: $id}) SET d.creationDate = $cd, d.goodsMovementStatus = $gm",
                id=did, cd=row.get("creationDate", ""),
                gm=row.get("overallGoodsMovementStatus", ""),
            )

        # Delivery items: SO→Delivery and Delivery→Plant
        seen_so_del = set()
        for _, row in delivery_items.iterrows():
            did = row.get("deliveryDocument")
            ref_so = row.get("referenceSdDocument")
            plant = row.get("plant")
            if pd.notna(did) and pd.notna(ref_so):
                pair = (ref_so, did)
                if pair not in seen_so_del:
                    session.run("""
                        MATCH (s:SalesOrder {id: $soid})
                        MATCH (d:Delivery {id: $did})
                        MERGE (s)-[:HAS_DELIVERY]->(d)
                    """, soid=ref_so, did=did)
                    seen_so_del.add(pair)
            if pd.notna(did) and pd.notna(plant):
                session.run("""
                    MATCH (d:Delivery {id: $did})
                    MATCH (p:Plant {id: $pid})
                    MERGE (d)-[:SHIPPED_FROM]->(p)
                """, did=did, pid=plant)

        # Billing Documents
        for _, row in billing_headers.iterrows():
            bdid = row.get("billingDocument")
            if pd.isna(bdid):
                continue
            session.run("""
                MERGE (b:BillingDocument {id: $id})
                SET b.creationDate = $cd, b.totalNetAmount = $amt, b.isCancelled = $cancel,
                    b.accountingDocument = $acct
            """, id=bdid, cd=row.get("creationDate", ""),
                amt=row.get("totalNetAmount", ""),
                cancel=row.get("billingDocumentIsCancelled", ""),
                acct=row.get("accountingDocument", ""))

        # Billing items: Delivery→BillingDocument
        seen_del_bill = set()
        for _, row in billing_items.iterrows():
            bdid = row.get("billingDocument")
            ref_del = row.get("referenceSdDocument")
            if pd.notna(bdid) and pd.notna(ref_del):
                pair = (ref_del, bdid)
                if pair not in seen_del_bill:
                    session.run("""
                        MATCH (d:Delivery {id: $did})
                        MATCH (b:BillingDocument {id: $bid})
                        MERGE (d)-[:HAS_INVOICE]->(b)
                    """, did=ref_del, bid=bdid)
                    seen_del_bill.add(pair)

        # Payments
        for _, row in payments.iterrows():
            payid = row.get("accountingDocument")
            if pd.isna(payid):
                continue
            session.run("""
                MERGE (p:Payment {id: $id})
                SET p.clearingDate = $cd, p.amount = $amt, p.currency = $cur, p.customer = $cust
            """, id=payid, cd=row.get("clearingDate", ""),
                amt=row.get("amountInTransactionCurrency", ""),
                cur=row.get("transactionCurrency", ""), cust=row.get("customer", ""))

        # BillingDocument → Payment via journal entries
        billing_to_journal = {}
        for _, row in journal_entries.iterrows():
            ref_doc = row.get("referenceDocument")
            acct_doc = row.get("accountingDocument")
            if pd.notna(ref_doc) and pd.notna(acct_doc):
                billing_to_journal.setdefault(ref_doc, set()).add(acct_doc)

        clearing_to_payment = {}
        for _, row in payments.iterrows():
            clearing = row.get("clearingAccountingDocument")
            pay_doc = row.get("accountingDocument")
            if pd.notna(clearing) and pd.notna(pay_doc):
                clearing_to_payment.setdefault(clearing, set()).add(pay_doc)

        for billing_doc, journal_acct_docs in billing_to_journal.items():
            for j_acct in journal_acct_docs:
                if j_acct in clearing_to_payment:
                    for pay_id in clearing_to_payment[j_acct]:
                        session.run("""
                            MATCH (b:BillingDocument {id: $bid})
                            MATCH (p:Payment {id: $pid})
                            MERGE (b)-[:SETTLED_BY]->(p)
                        """, bid=billing_doc, pid=pay_id)

    driver.close()
    print("  ✅ Neo4j graph loaded.")
    return None  # Neo4j doesn't return a graph object


# ── Summary / Verification ────────────────────────────────────────


def print_schema():
    """Print the graph schema to terminal."""
    print("\n" + "=" * 70)
    print("  GRAPH SCHEMA")
    print("=" * 70)
    print("""
  NODES:
    Customer          — id, name, category, creationDate
    SalesOrder        — id, type, creationDate, totalNetAmount, currency
    SalesOrderItem    — id, salesOrder, salesOrderItem, material, quantity, netAmount
    Delivery          — id, creationDate, goodsMovementStatus, pickingStatus
    BillingDocument   — id, type, creationDate, totalNetAmount, isCancelled
    Payment           — id, clearingDate, amount, currency, customer
    Product           — id, productType, description, grossWeight, baseUnit
    Plant             — id, plantName
    Address           — id, city, country, region, street, postalCode

  EDGES (directed):
    Customer       ─[PLACED]──────────► SalesOrder
    SalesOrder     ─[CONTAINS]─────────► SalesOrderItem
    SalesOrderItem ─[IS_MATERIAL]──────► Product
    SalesOrder     ─[HAS_DELIVERY]─────► Delivery
    Delivery       ─[SHIPPED_FROM]─────► Plant
    Delivery       ─[HAS_INVOICE]──────► BillingDocument
    BillingDocument─[SETTLED_BY]───────► Payment
    Customer       ─[HAS_ADDRESS]──────► Address
""")
    print("=" * 70)


def summarize_networkx(G):
    """Print node/edge counts and a sample O2C path."""
    print("\n" + "=" * 70)
    print("  GRAPH SUMMARY")
    print("=" * 70)

    # Node counts by label
    label_counts = {}
    for node, data in G.nodes(data=True):
        label = data.get("label", "Unknown")
        label_counts[label] = label_counts.get(label, 0) + 1

    print(f"\n  Total nodes: {G.number_of_nodes():,}")
    print(f"  Total edges: {G.number_of_edges():,}")
    print(f"\n  Node counts by label:")
    for label, count in sorted(label_counts.items()):
        print(f"    {label:20s}: {count:,}")

    # Edge counts by type
    edge_counts = {}
    for u, v, data in G.edges(data=True):
        etype = data.get("type", "Unknown")
        edge_counts[etype] = edge_counts.get(etype, 0) + 1

    print(f"\n  Edge counts by type:")
    for etype, count in sorted(edge_counts.items()):
        print(f"    {etype:20s}: {count:,}")

    # Sample path: Customer → SalesOrder → Delivery → BillingDocument
    print(f"\n  Sample O2C path:")
    customer_nodes = [n for n, d in G.nodes(data=True) if d.get("label") == "Customer"]
    found_path = False
    for cnode in customer_nodes:
        # Find a sales order placed by this customer
        for _, so_node in G.out_edges(cnode):
            so_data = G.nodes[so_node]
            if so_data.get("label") != "SalesOrder":
                continue
            # Find a delivery for this SO
            for _, del_node in G.out_edges(so_node):
                del_data = G.nodes[del_node]
                if del_data.get("label") != "Delivery":
                    continue
                # Find a billing doc for this delivery
                for _, bd_node in G.out_edges(del_node):
                    bd_data = G.nodes[bd_node]
                    if bd_data.get("label") != "BillingDocument":
                        continue
                    # Find a payment
                    for _, pay_node in G.out_edges(bd_node):
                        pay_data = G.nodes[pay_node]
                        if pay_data.get("label") != "Payment":
                            continue
                        cust_name = G.nodes[cnode].get("name", cnode)
                        print(f"    Customer: {cust_name} ({G.nodes[cnode].get('id')})")
                        print(f"      ─[PLACED]─► SalesOrder: {so_data.get('id')}")
                        print(f"        ─[HAS_DELIVERY]─► Delivery: {del_data.get('id')}")
                        print(f"          ─[HAS_INVOICE]─► BillingDocument: {bd_data.get('id')}")
                        print(f"            ─[SETTLED_BY]─► Payment: {pay_data.get('id')}")
                        found_path = True
                        break
                    if found_path:
                        break
                if found_path:
                    break
            if found_path:
                break
        if found_path:
            break

    if not found_path:
        print("    (No complete Customer→SO→Delivery→Invoice→Payment chain found)")
        # Try a partial path
        for cnode in customer_nodes:
            for _, so_node in G.out_edges(cnode):
                so_data = G.nodes[so_node]
                if so_data.get("label") != "SalesOrder":
                    continue
                for _, del_node in G.out_edges(so_node):
                    del_data = G.nodes[del_node]
                    if del_data.get("label") != "Delivery":
                        continue
                    cust_name = G.nodes[cnode].get("name", cnode)
                    print(f"    Partial: Customer: {cust_name}")
                    print(f"      ─[PLACED]─► SalesOrder: {so_data.get('id')}")
                    print(f"        ─[HAS_DELIVERY]─► Delivery: {del_data.get('id')}")
                    found_path = True
                    break
                if found_path:
                    break
            if found_path:
                break

    print(f"\n{'=' * 70}\n")


# ── Main ──────────────────────────────────────────────────────────


def main():
    print_schema()

    # Try Neo4j first, fall back to NetworkX
    neo4j_available = False
    try:
        from neo4j import GraphDatabase
        from dotenv import load_dotenv
        load_dotenv()
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "graphpassword")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        neo4j_available = True
    except Exception:
        pass

    if neo4j_available:
        print("\n🟢 Loading graph into Neo4j...")
        build_neo4j_graph()
        print("  ℹ️  Run Cypher queries in Neo4j Browser at http://localhost:7474")
    else:
        print("\n🟡 Neo4j not available — building NetworkX in-memory graph...")

    G = build_networkx_graph()
    summarize_networkx(G)

    # Save graph to disk for the backend to load
    import pickle
    graph_path = PROJECT_ROOT / "data" / "graph.pkl"
    with open(graph_path, "wb") as f:
        pickle.dump(G, f)
    print(f"💾 Graph saved to {graph_path}")

    return G


if __name__ == "__main__":
    main()
