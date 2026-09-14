# Reproducibility capsule — NoSQLInspector evaluation

This capsule contains everything needed to regenerate the evaluation dataset and
reproduce the quantitative results reported in the **Evaluation and validation** section
of the paper *NoSQLInspector: An Open-Source Inspection Software for Document-Oriented
NoSQL Databases*.

The dataset (`ecommerce_db`) is **generated deterministically** from a fixed random seed,
so anyone re-running the generator obtains byte-for-byte the same documents, and every
injected anomaly is recorded with its exact location in `ground_truth.json`. Reviewers
can therefore verify each inspection module's output against a known, machine-readable
ground truth rather than trusting reported numbers.

## Contents

| File | Description |
|------|-------------|
| `generate_ecommerce_db.py` | Deterministic generator (seed = 42) for the three collections |
| `run_experiments.py` | Harness that runs the four inspection modules and prints the paper tables |
| `data/products.json`, `orders.json`, `customers.json` | The generated dataset (23 / 100 / 50 documents) |
| `data/products_v2.json` | Drifted `products` schema used in the schema-drift experiment |
| `data/ground_truth.json` | Every injected anomaly, labelled by collection, field, category, and severity |
| `data/manifest.json` | Document counts and per-field presence (sanity check against the paper) |
| `requirements.txt` | Python dependencies |

## Requirements

- Python ≥ 3.11
- The NoSQLInspector source package (imported by `run_experiments.py`)
- Optional: a running MongoDB instance, to load the dataset and reproduce the interface
- `pip install -r requirements.txt`

## 1. Regenerate the dataset

```bash
python generate_ecommerce_db.py --out data
# optionally load into MongoDB as database "ecommerce_db":
python generate_ecommerce_db.py --out data --mongo-uri mongodb://localhost:27017
```

Expected output: `products = 23, orders = 100, customers = 50`, `173` documents total,
`43` distinct field paths, `18` injected anomalies. These match Table 4 in the paper.

## 2. Reproduce the experiments

```bash
python run_experiments.py --data data
```

This runs schema inference, security auditing, schema-drift comparison, and data-quality
profiling on the generated collections, compares detections against `ground_truth.json`,
and prints the numbers reported in the paper.

## Mapping to the paper

| Paper table | Experiment | What to check |
|-------------|------------|---------------|
| Table 4 | Schema inference | 43/43 field paths recovered, depth 2, 0 FP / 0 FN; presence values equal `manifest.json` |
| Table 5 | Security auditing | Per-collection Critical/High/Medium/Info counts and score; all `exposed_secret`, `plaintext_password`, PII, and type-juggling ground-truth items detected |
| Table 6 | Schema drift | `products` vs `products_v2`: 5 modifications detected, stability score 10/100 |
| Table 7 | Data quality | Injected anomalies per category detected; recall 100%, precision 93.8% (one expected false positive: the legitimate zero-price promotional item) |
| Table 8 | Scalability | **Must be measured on your machine** — see below |

## `ground_truth.json` format

Each entry records one injected anomaly:

```json
{
  "collection": "customers",
  "doc_id": "C-0001",
  "field": "password",
  "category": "plaintext_password",
  "severity": "CRITICAL",
  "note": "Password stored in clear text"
}
```

Categories map to the experiments as follows:
- **Security (Table 5):** `plaintext_password`, `exposed_secret`, `type_inconsistency` (financial), plus PII fields detected directly from the customer records.
- **Data quality (Table 7):** `missing_value`, `type_inconsistency`, `duplicate_id`, `invalid_format`, `range_sign_error`, `cross_field`. The legitimate zero-price promotional product (`products` document with `price = 0`) is intentionally **not** listed — if the profiler flags it, it is the single expected false positive.

## 3. Scalability (Table 8)

The scalability timings are hardware-dependent and are **not** reproduced by this capsule.
To reproduce Table 8, generate larger synthetic collections (1 000 / 10 000 / 50 000 /
100 000 documents) from the same document templates and time each module. Report your
environment (CPU, RAM, OS, Python version, MongoDB version) alongside the results.

## Citing

If you use this dataset or capsule, please cite the paper and the archived release
(see the Code metadata table / Zenodo DOI in the manuscript).
