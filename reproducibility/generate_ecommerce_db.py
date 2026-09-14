#!/usr/bin/env python3
"""
generate_ecommerce_db.py
------------------------
Deterministic generator for the `ecommerce_db` evaluation dataset used in the
Evaluation and validation section of the NoSQLInspector paper.

It reproduces, exactly and reproducibly (fixed random seed), the three collections
described in the manuscript:

    products   : 23 documents, 18 field paths, two coexisting schema variants
    orders     : 100 documents, 14 field paths, array of order lines + nested objects
    customers  : 50 documents, 11 field paths, nested address + personal data

and embeds a fixed set of anomalies with known ground truth (exposed credentials,
mixed types, malformed / inconsistent / out-of-range values). Every injected anomaly
is recorded in `ground_truth.json` so that a reviewer can verify each inspection
module's detections against the exact set of planted issues.

Outputs (written to --out, default ./data):
    products.json, orders.json, customers.json   -- the dataset
    products_v2.json                             -- drifted products schema (Experiment C)
    ground_truth.json                            -- every injected anomaly, labelled
    manifest.json                                -- counts + presence summary (sanity check)

Optional: load directly into a MongoDB instance with --mongo-uri.

Usage:
    python generate_ecommerce_db.py
    python generate_ecommerce_db.py --out data --mongo-uri mongodb://localhost:27017
"""

import argparse
import json
import os
import random
from datetime import datetime, timedelta

SEED = 42
N_PRODUCTS = 23           # 20 "specifications" variant + 3 "properties" variant
N_ORDERS = 100
N_CUSTOMERS = 50

BRANDS = ["Acme", "Globex", "Umbrella", "Initech", "Soylent", "Hooli", "Stark"]
CATEGORIES = ["electronics", "home", "sports", "books", "toys", "beauty"]
COLORS = ["black", "white", "red", "blue", "silver", "green"]
CITIES = ["Casablanca", "Rabat", "El Jadida", "Marrakech", "Tangier", "Fez"]
COUNTRIES = ["Morocco", "France", "Spain", "Germany"]
STATUSES = ["pending", "shipped", "delivered", "cancelled"]
PAY_METHODS = ["card", "paypal", "cash_on_delivery", "bank_transfer"]

ground_truth = []   # list of {collection, doc_id, field, category, severity, note}


def gt(collection, doc_id, field, category, severity, note):
    ground_truth.append({
        "collection": collection, "doc_id": doc_id, "field": field,
        "category": category, "severity": severity, "note": note,
    })


def rand_date(rng, start_year=2021, end_year=2024):
    start = datetime(start_year, 1, 1)
    delta = (datetime(end_year, 12, 31) - start).days
    return (start + timedelta(days=rng.randint(0, delta))).strftime("%Y-%m-%dT%H:%M:%S")


# --------------------------------------------------------------------------- #
# products : 20 documents use `specifications`/`supplier`/`price`/`name`
#             3 documents use the legacy `properties`/`supplied_by`/`unit_price`/`label`
# --------------------------------------------------------------------------- #
def build_products(rng):
    docs = []
    for i in range(N_PRODUCTS):
        pid = f"P-{i+1:04d}"
        doc = {
            "product_id": pid,
            "brand": rng.choice(BRANDS),
            "category": rng.choice(CATEGORIES),
            "stock": rng.randint(0, 500),
        }
        if i < 20:  # modern "specifications" variant
            doc["name"] = f"Product {i+1}"
            doc["price"] = rng.randint(20, 2000)
            doc["supplier"] = f"Supplier {rng.randint(1, 9)}"
            doc["specifications"] = {
                "color": rng.choice(COLORS),
                "warranty_months": rng.choice([6, 12, 24, 36]),
            }
        else:       # legacy "properties" variant (3 docs)
            doc["label"] = f"Item {i+1}"
            doc["unit_price"] = rng.randint(20, 2000)
            doc["supplied_by"] = f"Vendor {rng.randint(1, 9)}"
            doc["properties"] = {
                "color": rng.choice(COLORS),
                "warranty_months": rng.choice([12, 24]),
            }
        docs.append(doc)

    # --- seeded anomalies (products) ---
    # Exposed credentials (security): api_key in 1 doc, secret_key in 1 doc (4.3% each)
    docs[0]["api_key"] = "sk_live_" + "".join(rng.choice("abcdef0123456789") for _ in range(24))
    gt("products", docs[0]["product_id"], "api_key", "exposed_secret", "HIGH", "API key stored in catalogue document")
    docs[1]["secret_key"] = "".join(rng.choice("ABCDEF0123456789") for _ in range(32))
    gt("products", docs[1]["product_id"], "secret_key", "exposed_secret", "HIGH", "Secret key stored in catalogue document")

    # Type inconsistency (security type-juggling + data-quality): 1 price stored as string
    docs[2]["price"] = "199.99"
    gt("products", docs[2]["product_id"], "price", "type_inconsistency", "MEDIUM", "Financial field mixes integer and string")

    # Out-of-range / sign errors (data quality)
    docs[3]["price"] = -50
    gt("products", docs[3]["product_id"], "price", "range_sign_error", "HIGH", "Negative price")
    docs[4]["price"] = 999999
    gt("products", docs[4]["product_id"], "price", "range_sign_error", "INFO", "Outlier price (>3 sigma)")

    # Legitimate promotional zero price -> expected FALSE POSITIVE for the profiler
    docs[5]["price"] = 0
    # NOTE: not added to ground_truth; it is a legitimate promo and counts as a false positive if flagged.

    return docs


def build_products_v2(products_v1, rng):
    """Drifted snapshot of `products` for Experiment C (schema drift).

    Applies five controlled modifications to the modern variant:
      1. FIELD_ADDED     : discount_pct (partial presence)
      2. FIELD_REMOVED   : label removed from legacy docs
      3. TYPE_CHANGED    : stock integer -> string
      4. PRESENCE_DROPPED: name present in ~60% instead of ~87%
      5. TYPE_MIXED      : specifications.warranty_months integer -> mixed int/string
    """
    import copy
    docs = copy.deepcopy(products_v1)
    for idx, doc in enumerate(docs):
        # 3. stock int -> string
        doc["stock"] = str(doc["stock"])
        # 1. discount_pct added to ~40% of docs (partial presence)
        if rng.random() < 0.4:
            doc["discount_pct"] = rng.choice([5, 10, 15, 20])
        # 2. remove legacy label
        doc.pop("label", None)
        # 4. drop `name` presence: remove from some modern docs so presence ~60%
        if "name" in doc and rng.random() < 0.3:
            doc.pop("name")
        # 5. warranty_months mixed type in specifications
        if "specifications" in doc and rng.random() < 0.3:
            doc["specifications"]["warranty_months"] = str(doc["specifications"]["warranty_months"])
    return docs


# --------------------------------------------------------------------------- #
# orders : items[] array + nested payment / shipping ; total mixed type
# --------------------------------------------------------------------------- #
def build_orders(rng, customer_ids, product_ids):
    docs = []
    # item counts: 97 orders x 2 items + 3 orders x 3 items = 203 line items
    extra = set(rng.sample(range(N_ORDERS), 3))
    for i in range(N_ORDERS):
        oid = f"ORD-{i+1:04d}"
        n_items = 3 if i in extra else 2
        items, computed_total = [], 0
        for _ in range(n_items):
            up = rng.randint(20, 800)
            qty = rng.randint(1, 5)
            computed_total += up * qty
            items.append({"product_id": rng.choice(product_ids),
                          "quantity": qty, "unit_price": up})
        doc = {
            "order_id": oid,
            "customer_id": rng.choice(customer_ids),
            "order_date": rand_date(rng),
            "items": items,
            "total": computed_total,
            "payment": {"method": rng.choice(PAY_METHODS), "paid": True},
            "shipping": {"city": rng.choice(CITIES), "status": rng.choice(STATUSES)},
        }
        docs.append(doc)

    # --- seeded anomalies (orders) ---
    # Missing sub-object: 1 order without payment (presence 99%)
    docs[10].pop("payment")
    gt("orders", docs[10]["order_id"], "payment", "missing_value", "MEDIUM", "Payment sub-object absent")

    # Type inconsistency: 1 total stored as string
    docs[11]["total"] = str(docs[11]["total"])
    gt("orders", docs[11]["order_id"], "total", "type_inconsistency", "MEDIUM", "Financial field mixes integer and string")

    # Duplicate identifier: order 99 reuses order 98's id
    docs[99]["order_id"] = docs[98]["order_id"]
    gt("orders", docs[98]["order_id"], "order_id", "duplicate_id", "CRITICAL", "Duplicated order_id")

    # Cross-field: 3 orders whose total does not match the sum of their line items
    for k in (20, 21, 22):
        docs[k]["total"] = docs[k]["total"] + 100  # 100-unit discrepancy (> 1% tolerance)
        gt("orders", docs[k]["order_id"], "total", "cross_field", "HIGH", "Order total inconsistent with line items")

    # Cross-field: 1 order marked paid but with a zero total
    docs[30]["total"] = 0
    docs[30]["payment"] = {"method": "card", "paid": True}
    gt("orders", docs[30]["order_id"], "total", "cross_field", "CRITICAL", "Marked paid but total is zero")

    return docs


# --------------------------------------------------------------------------- #
# customers : nested address + personal data ; 1 plaintext password ; 1 null email
# --------------------------------------------------------------------------- #
def build_customers(rng):
    docs = []
    for i in range(N_CUSTOMERS):
        cid = f"C-{i+1:04d}"
        docs.append({
            "customer_id": cid,
            "first_name": rng.choice(["Sara", "Youssef", "Amine", "Nadia", "Omar", "Laila"]),
            "last_name": rng.choice(["Alaoui", "Bennani", "Idrissi", "Fassi", "Cherkaoui"]),
            "email": f"user{i+1}@example.com",
            "phone": f"+2126{rng.randint(10000000, 99999999)}",
            "address": {"city": rng.choice(CITIES), "country": rng.choice(COUNTRIES)},
            "loyalty_points": rng.randint(0, 5000),
            "registration_date": rand_date(rng),
        })

    # --- seeded anomalies (customers) ---
    # Plaintext password exposed in exactly 1 document (2%)
    docs[0]["password"] = "P@ssw0rd123"
    gt("customers", docs[0]["customer_id"], "password", "plaintext_password", "CRITICAL", "Password stored in clear text")

    # Missing value: 1 null email
    docs[1]["email"] = None
    gt("customers", docs[1]["customer_id"], "email", "missing_value", "INFO", "Null e-mail")

    # Invalid formats: 2 malformed emails, 1 malformed phone
    docs[2]["email"] = "john[at]mail"
    gt("customers", docs[2]["customer_id"], "email", "invalid_format", "HIGH", "Malformed e-mail")
    docs[3]["email"] = "bad-email"
    gt("customers", docs[3]["customer_id"], "email", "invalid_format", "HIGH", "Malformed e-mail")
    docs[4]["phone"] = "PHONE-N/A"
    gt("customers", docs[4]["customer_id"], "phone", "invalid_format", "HIGH", "Malformed phone number")

    # Out-of-range / sign error: 1 negative loyalty_points
    docs[5]["loyalty_points"] = -100
    gt("customers", docs[5]["customer_id"], "loyalty_points", "range_sign_error", "HIGH", "Negative loyalty points")

    return docs


def presence_summary(docs):
    """Field-path presence counts (flattened, dot notation) for the manifest."""
    counts, n = {}, len(docs)
    def walk(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{prefix}.{k}" if prefix else k
                counts[p] = counts.get(p, 0) + 1
                if isinstance(v, (dict, list)):
                    walk(v, p)
        elif isinstance(obj, list):
            # array elements are flattened onto the array path (e.g. items.product_id),
            # counted once per element occurrence, matching the schema inferrer
            for item in obj:
                if isinstance(item, dict):
                    for k, v in item.items():
                        p = f"{prefix}.{k}"
                        counts[p] = counts.get(p, 0) + 1
                        if isinstance(v, (dict, list)):
                            walk(v, p)
    for d in docs:
        walk(d)
    return {k: {"occurrences": v, "presence_pct": round(v / n * 100, 1)}
            for k, v in sorted(counts.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--mongo-uri", default=None, help="If set, also load into this MongoDB instance")
    ap.add_argument("--db-name", default="ecommerce_db")
    args = ap.parse_args()

    rng = random.Random(SEED)
    os.makedirs(args.out, exist_ok=True)

    products = build_products(rng)
    customers = build_customers(rng)
    orders = build_orders(rng, [c["customer_id"] for c in customers],
                          [p["product_id"] for p in products])
    products_v2 = build_products_v2(products, rng)

    collections = {
        "products": products, "orders": orders, "customers": customers,
        "products_v2": products_v2,
    }
    for name, docs in collections.items():
        with open(os.path.join(args.out, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)

    with open(os.path.join(args.out, "ground_truth.json"), "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)

    manifest = {
        "seed": SEED,
        "collections": {n: len(d) for n, d in collections.items() if n != "products_v2"},
        "total_documents": len(products) + len(orders) + len(customers),
        "injected_anomalies": len(ground_truth),
        "presence": {
            "products": presence_summary(products),
            "orders": presence_summary(orders),
            "customers": presence_summary(customers),
        },
    }
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Wrote dataset to '{args.out}/': "
          f"products={len(products)}, orders={len(orders)}, customers={len(customers)}; "
          f"{len(ground_truth)} injected anomalies recorded in ground_truth.json")

    if args.mongo_uri:
        from pymongo import MongoClient
        client = MongoClient(args.mongo_uri)
        db = client[args.db_name]
        for name in ("products", "orders", "customers"):
            db[name].drop()
            db[name].insert_many(json.loads(json.dumps(collections[name])))
        print(f"Loaded into MongoDB database '{args.db_name}' at {args.mongo_uri}")


if __name__ == "__main__":
    main()
