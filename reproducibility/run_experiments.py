#!/usr/bin/env python3
"""
run_experiments.py
------------------
Runs the four NoSQLInspector inspection modules on the generated `ecommerce_db`
collections and prints the numbers reported in the Evaluation section of the paper,
comparing detections against data/ground_truth.json.

This harness calls the tool's own modules. The import names and entry points below
follow the modules documented in the paper (schema_inferrer, security_auditor,
semantic_profiler, drift_detector). If your package exposes different names or
signatures, adjust the ADAPTER section only — the rest is generic.

Usage:
    python run_experiments.py --data data
"""

import argparse
import json
import os
import sys


# --------------------------------------------------------------------------- #
# ADAPTER — wire these calls to your actual NoSQLInspector API.
# Each function takes a list[dict] (documents) and returns the tool's result.
# --------------------------------------------------------------------------- #
def adapt_schema_inference(docs):
    from schema_inferrer import infer_schema
    return infer_schema(docs)

def adapt_security_audit(docs):
    from security_auditor import run_audit          # -> {"score": int, "findings": [...]}
    return run_audit(docs)

def adapt_data_quality(docs):
    from semantic_profiler import SemanticProfiler
    prof = SemanticProfiler()
    return prof.compute_quality_score(docs)          # -> {"score": int, "grade": str, "findings": [...]}

def adapt_schema_drift(docs_old, docs_new):
    from schema_inferrer import infer_schema
    from drift_detector import compare_snapshots
    return compare_snapshots(infer_schema(docs_old), infer_schema(docs_new))
# --------------------------------------------------------------------------- #


def load(data_dir, name):
    with open(os.path.join(data_dir, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    args = ap.parse_args()

    products = load(args.data, "products")
    orders = load(args.data, "orders")
    customers = load(args.data, "customers")
    products_v2 = load(args.data, "products_v2")
    ground_truth = load(args.data, "ground_truth")

    print(f"Loaded ecommerce_db: products={len(products)}, orders={len(orders)}, "
          f"customers={len(customers)}; {len(ground_truth)} injected anomalies\n")

    collections = {"products": products, "orders": orders, "customers": customers}

    # --- Experiment A: schema inference -------------------------------------
    print("== Experiment A — Schema inference ==")
    try:
        for name, docs in collections.items():
            schema = adapt_schema_inference(docs)
            print(f"  {name}: {len(schema)} field paths inferred")
    except Exception as e:
        print(f"  [adapter needed] {e}")

    # --- Experiment B: security auditing ------------------------------------
    print("\n== Experiment B — Security auditing ==")
    try:
        for name, docs in collections.items():
            res = adapt_security_audit(docs)
            print(f"  {name}: score={res.get('score')}, findings={len(res.get('findings', []))}")
    except Exception as e:
        print(f"  [adapter needed] {e}")

    # --- Experiment C: schema drift -----------------------------------------
    print("\n== Experiment C — Schema drift (products vs products_v2) ==")
    try:
        drift = adapt_schema_drift(products, products_v2)
        print(f"  changes detected={len(drift.get('changes', []))}, "
              f"stability={drift.get('stability_score')}")
    except Exception as e:
        print(f"  [adapter needed] {e}")

    # --- Experiment D: data quality -----------------------------------------
    print("\n== Experiment D — Data-quality profiling ==")
    try:
        for name, docs in collections.items():
            res = adapt_data_quality(docs)
            print(f"  {name}: score={res.get('score')}, grade={res.get('grade')}, "
                  f"findings={len(res.get('findings', []))}")
    except Exception as e:
        print(f"  [adapter needed] {e}")

    # --- Ground-truth summary -----------------------------------------------
    print("\n== Ground truth (data/ground_truth.json) ==")
    by_cat = {}
    for g in ground_truth:
        by_cat.setdefault(g["category"], 0)
        by_cat[g["category"]] += 1
    for cat, cnt in sorted(by_cat.items()):
        print(f"  {cat}: {cnt}")
    print("\nCompare each module's findings against ground_truth.json to obtain "
          "precision/recall (Tables 5 and 7).")


if __name__ == "__main__":
    sys.exit(main())
