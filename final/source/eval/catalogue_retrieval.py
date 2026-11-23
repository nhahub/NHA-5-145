"""Frozen exposed retrieval development comparison; no provider calls."""

import argparse
import hashlib
import json
import shutil
import statistics
import subprocess
import time
from pathlib import Path

from agent.catalogue_embedding import MODEL, REVISION, CatalogueEncoder

ROOT = Path(__file__).resolve().parents[1]


def recall_at_k(ranked, relevant, k=10):
    return len(set(ranked[:k]) & set(relevant)) / len(relevant) if relevant else None


def reciprocal_rank(ranked, relevant):
    return next((1 / i for i, item in enumerate(ranked, 1) if item in relevant), 0.0)


def verify_manifest(content: bytes, manifest: dict):
    if hashlib.sha256(content).hexdigest() != manifest["sha256"]:
        raise ValueError("Dataset differs from its freeze manifest")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--work", type=Path, default=ROOT / "work/catalogue-retrieval")
    args = parser.parse_args()
    corpus = ROOT / "eval/datasets/catalogue-retrieval-v1/queries.json"
    verify_manifest(corpus.read_bytes(), json.loads(corpus.with_name("manifest.json").read_text()))
    cases = json.loads(corpus.read_text(encoding="utf-8"))
    products = json.loads((args.work / "products.json").read_text(encoding="utf-8"))
    start = time.perf_counter()
    encoder = CatalogueEncoder(args.cache)
    descriptions = [
        " ".join(
            [p["nameAr"], p["nameEn"], p["type"], *p["colors"], *p["features"], *p["suitableFor"]]
        )
        for p in products
    ]
    vectors = encoder.encode(descriptions)
    product_encoding_ms = (time.perf_counter() - start) * 1000
    query_start = time.perf_counter()
    queries = encoder.encode([case["text"] for case in cases])
    query_batch_ms = (time.perf_counter() - query_start) * 1000
    request = {
        "index": {
            "model": MODEL,
            "model_revision": REVISION,
            "catalogue_revision": 1,
            "vectors": {p["id"]: v for p, v in zip(products, vectors, strict=True)},
        },
        "queries": [
            {
                "id": c["id"],
                "query": c["search"],
                "embedding": {"model": MODEL, "model_revision": REVISION, "vector": v},
            }
            for c, v in zip(cases, queries, strict=True)
        ],
    }
    source = args.work / "benchmark-input.json"
    destination = args.work / "benchmark-output.json"
    source.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is required")
    subprocess.run(
        [
            node,
            str(ROOT / "store/node_modules/tsx/dist/cli.mjs"),
            str(ROOT / "store/scripts/catalogue-benchmark.ts"),
            str(args.work / "evaluation.sqlite"),
            str(source),
            str(destination),
        ],
        cwd=ROOT,
        check=True,
    )
    results = json.loads(destination.read_text(encoding="utf-8"))
    report = {
        "provenance": (
            "language-model-generated exposed development queries; "
            "provisional relevance labels; no live LLM"
        ),
        "model": MODEL,
        "revision": REVISION,
        "device": "cpu",
        "corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "product_encoding_including_load_ms": product_encoding_ms,
        "query_batch_ms": query_batch_ms,
        "node_rss_bytes": results["rss_bytes"],
        "results": [],
    }
    for case, result in zip(cases, results["results"], strict=True):
        record = {
            "id": case["id"],
            "language": case["language"],
            "relevant_ids": case["relevant_ids"],
        }
        for mode in ("lexical", "hybrid"):
            response = result[mode]
            ranked = [p["product"]["id"] for p in response["candidates"]]
            record[mode] = {
                "ids": ranked,
                "recall_at_10": recall_at_k(ranked, case["relevant_ids"]),
                "rr": reciprocal_rank(ranked, case["relevant_ids"]),
                "search_ms": result[mode + "_ms"],
                "response_bytes": len(json.dumps(response, ensure_ascii=False).encode()),
                "unknown_candidates": sum(
                    any(r["status"] == "unknown" for r in p["requirements"])
                    for p in response["candidates"]
                ),
            }
        report["results"].append(record)
    report["summary"] = {
        mode: {
            "mean_recall_at_10": statistics.mean(
                r[mode]["recall_at_10"]
                for r in report["results"]
                if r[mode]["recall_at_10"] is not None
            ),
            "mrr": statistics.mean(r[mode]["rr"] for r in report["results"]),
        }
        for mode in ("lexical", "hybrid")
    }
    report["per_language"] = {
        language: {
            mode: statistics.mean(
                r[mode]["recall_at_10"] for r in report["results"] if r["language"] == language
            )
            for mode in ("lexical", "hybrid")
        }
        for language in sorted({r["language"] for r in report["results"]})
    }
    report["historical_full_read"] = {
        "candidate_recall_at_60": 1.0,
        "products_per_read": len(products),
        "response_bytes": len((args.work / "products.json").read_bytes()),
        "note": (
            "Full evidence transport baseline only; no claim about "
            "historical model or three-card selection accuracy."
        ),
    }
    load_products, load_vectors = [], {}
    for i in range(1000):
        product = dict(products[i % len(products)])
        old_id = product["id"]
        product["id"] = f"load-{i:04d}"
        load_products.append(product)
        load_vectors[product["id"]] = request["index"]["vectors"][old_id]
    load_input, load_output = args.work / "load-input.json", args.work / "load-output.json"
    load_input.write_text(
        json.dumps(
            {
                **request,
                "products": load_products,
                "index": {**request["index"], "vectors": load_vectors},
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            node,
            str(ROOT / "store/node_modules/tsx/dist/cli.mjs"),
            str(ROOT / "store/scripts/catalogue-benchmark.ts"),
            str(args.work / "load.sqlite"),
            str(load_input),
            str(load_output),
        ],
        cwd=ROOT,
        check=True,
    )
    load = json.loads(load_output.read_text())
    report["cpu_load_fixture"] = {
        "products": 1000,
        "construction": (
            "Repeated catalogue facts with unique IDs; cached normalized "
            "vectors, not 1000 independently labelled products."
        ),
        "node_rss_bytes": load["rss_bytes"],
        "warm_search_p95_ms": {
            mode: sorted(r[mode + "_ms"] for r in load["results"][1:])[
                int(0.95 * (len(load["results"]) - 2))
            ]
            for mode in ("lexical", "hybrid")
        },
        "excludes": (
            "Query encoding, HTTP overhead and other service processes; "
            "whole-stack fit and end-to-end p95 remain unqualified."
        ),
    }
    report["qualification"] = {
        "default_enabled": False,
        "live_model": "not run; separate budget authorization required",
        "host_fit": "not measured; no deployment qualification",
        "quality": (
            "Exposed provisional target labels only; not unseen "
            "performance or exhaustive relevance."
        ),
    }
    output = ROOT / "eval/evidence/catalogue-retrieval-v1.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
