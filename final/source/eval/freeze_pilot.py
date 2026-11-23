"""Freeze the owner-approved synthetic pilot; preserve full conversation components."""

import argparse
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from eval.pilot_data import LABELS, digest, validate_release

BASE = "eval/datasets/capstone-v1/development/"


def build_release(root: Path) -> dict:
    annotations = [
        BASE + n for n in ("synthetic-batch-001.json", "gemini-batch-001.annotated.json")
    ]
    group_path = BASE + "combined-group-map.json"
    groups = json.loads((root / group_path).read_text(encoding="utf-8"))
    schema_path = BASE + "record-format-v2.schema.json"
    validator = Draft202012Validator(json.loads((root / schema_path).read_text(encoding="utf-8")))
    all_rows = []
    for name in annotations:
        rows = json.loads((root / name).read_text(encoding="utf-8"))
        validator.validate(rows)
        all_rows.extend(rows)
    originals = {r["case_id"]: r for r in all_rows}
    if len(originals) != len(all_rows):
        raise ValueError("Duplicate source IDs")
    membership = {m["case_id"]: m["component_id"] for m in groups["membership"]}
    if len(membership) != len(groups["membership"]) or set(membership) != set(originals):
        raise ValueError("Incomplete or duplicate component membership")
    for source in groups["source_files"]:
        if digest(root / source["path"]) != source["sha256_normalized_lf"]:
            raise ValueError("Grouping was reviewed against different source content")
    for relation in groups["relations"]:
        if len({membership[i] for i in relation["case_ids"]}) != 1:
            raise ValueError("Related cases separated by grouping map")
    for field in ("conversation_group_id", "paraphrase_group_id"):
        mapping = {}
        for row in all_rows:
            key = row["grouping"][field]
            component = membership[row["case_id"]]
            if mapping.setdefault(key, component) != component:
                raise ValueError("Source conversation/paraphrase group divided")
    eligible = [r for r in all_rows if r["comparison"]["intent_only_eligible"]]
    counts = Counter(r["expected"]["intent"] for r in eligible)
    components = sorted({membership[r["case_id"]] for r in eligible})
    if len(components) > 20:
        raise ValueError("This small-pilot allocator supports at most 20 components")
    by_group = {
        g: Counter(r["expected"]["intent"] for r in eligible if membership[r["case_id"]] == g)
        for g in components
    }
    target = round(len(eligible) * 0.2)
    options = []
    for bits in itertools.product((False, True), repeat=len(components)):
        selected = [g for g, include in zip(components, bits, strict=True) if include]
        vc = sum((by_group[g] for g in selected), Counter())
        if not vc or any(vc[label] >= counts[label] for label in vc):
            continue
        tie = hashlib.sha256(("42:" + ",".join(selected)).encode()).hexdigest()
        options.append((abs(sum(vc.values()) - target), tie, selected))
    if not options:
        raise ValueError("No group-isolated validation subset with training support")
    validation_groups = set(min(options)[2])
    rows = [
        {
            "case_id": r["case_id"],
            "text": r["input"]["message"],
            "label": r["expected"]["intent"],
            "language": r["language_group"],
            "group": membership[r["case_id"]],
            "eligible": True,
            "split": "validation" if membership[r["case_id"]] in validation_groups else "train",
        }
        for r in eligible
    ]
    sources = [
        *annotations,
        group_path,
        schema_path,
        "docs/cap03-pilot-protocol.md",
        "eval/freeze_pilot.py",
    ]
    data = {
        "version": "synthetic-pilot-20261006-v1",
        "kind": "synthetic_development_pilot",
        "approved_scope": "Owner authorized synthetic pilot on 2026-10-06; final evaluation open",
        "frozen": True,
        "unseen_count": 0,
        "labels": LABELS,
        "independent_human_review": False,
        "annotation_status": "reviewed_drafts",
        "annotation_files": annotations,
        "group_map": group_path,
        "source_hashes": {name: digest(root / name) for name in sources},
        "hash_convention": "UTF-8 file bytes with CRLF normalized to LF",
        "allocation": {
            "seed": 42,
            "target_validation_count": target,
            "method": (
                "Exhaustive whole-component subsets; minimize distance to 20%; "
                "retain training label support; seeded SHA256 tie break"
            ),
        },
        "records": rows,
        "excluded": [
            {
                "case_id": r["case_id"],
                "group": membership[r["case_id"]],
                "reason": r["comparison"]["eligibility_reason"],
            }
            for r in all_rows
            if not r["comparison"]["intent_only_eligible"]
        ],
        "group_assignments": {
            g: "validation" if g in validation_groups else "train" for g in components
        },
        "limitations": [
            "Synthetic exposed data and draft labels, not independent gold",
            "Missing contextual tasks excluded from primary comparison",
            "Large connected component and rare classes constrain validation coverage",
            "Final CAP-02 unseen release and CAP-03 LLM comparison remain open",
        ],
    }
    validate_release(data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = build_release(Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "cases": len(data["records"]),
                "excluded": len(data["excluded"]),
                "splits": dict(Counter(r["split"] for r in data["records"])),
                "unseen": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
