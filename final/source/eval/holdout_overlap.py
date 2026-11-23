"""Candidate overlap signals for review, never an independence proof."""

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

from eval.holdout_release import inputs_digest, normalized, sha256


def inventory(root):
    candidates, sources = [], {}
    paths = subprocess.check_output(
        ["git", "ls-files", "agent/tests", "eval"], cwd=root, text=True
    ).splitlines()
    paths += [
        p.relative_to(root).as_posix()
        for p in (root / "work/manual-test").glob("*")
        if p.suffix in {".json", ".py"}
    ]
    for relative in sorted(set(paths)):
        path = root / relative
        if (
            not path.is_file()
            or path.suffix not in {".json", ".py"}
            or "holdout-20261009" in relative
        ):
            continue
        if path.stat().st_size > 5_000_000:
            continue
        try:
            source = path.read_text(encoding="utf-8-sig")
            values = []
            if path.suffix == ".py":
                values = [
                    n.value
                    for n in ast.walk(ast.parse(source))
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                ]
            else:

                def visit(value, values=values):
                    if isinstance(value, dict):
                        for key, item in value.items():
                            if key in {"message", "text", "content"} and isinstance(item, str):
                                values.append(item)
                            else:
                                visit(item)
                    elif isinstance(value, list):
                        for item in value:
                            visit(item)

                visit(json.loads(source))
            for index, value in enumerate(values):
                if 10 <= len(value) <= 600 and len(value.split()) >= 3:
                    candidates.append({"source": relative, "index": index, "text": value})
            if values:
                sources[relative] = sha256(path)
        except (ValueError, SyntaxError, UnicodeError):
            continue
    return candidates, sources


def audit(root, records):
    prior, sources = inventory(root)
    texts = [r["input"]["message"] for r in records]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)
    features = vectorizer.fit_transform([r["text"] for r in prior] + texts)
    similarity = (features[len(prior) :] @ features[: len(prior)].T).toarray()
    within = (features[len(prior) :] @ features[len(prior) :].T).toarray()
    pairs = []
    for i, row in enumerate(records):
        top = similarity[i].argsort()[-3:][::-1]
        pairs.append(
            {
                "case_id": row["case_id"],
                "nearest_prior": [
                    {
                        "source": prior[j]["source"],
                        "index": prior[j]["index"],
                        "text_sha256": hashlib.sha256(prior[j]["text"].encode()).hexdigest(),
                        "score": round(float(similarity[i, j]), 4),
                        "normalized_exact": normalized(texts[i]) == normalized(prior[j]["text"]),
                    }
                    for j in top
                ],
                "related_holdout_candidates": [
                    {"case_id": records[j]["case_id"], "score": round(float(within[i, j]), 4)}
                    for j in range(i)
                    if within[i, j] >= 0.55
                ],
            }
        )
    return {
        "method": (
            "char_wb TF-IDF 3-5 cosine; top three per case; "
            "review signals, not semantic independence proof"
        ),
        "inputs_sha256": inputs_digest(records),
        "prior_candidate_count": len(prior),
        "source_hashes": sources,
        "cases": pairs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(Path.cwd(), json.loads(args.records.read_text(encoding="utf-8")))
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Audited {len(result['cases'])} cases against "
        f"{result['prior_candidate_count']} strings; review remains required."
    )
