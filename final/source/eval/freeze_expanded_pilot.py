"""Verify and freeze the second exposed synthetic development release."""

import argparse
import importlib.metadata
import json
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

from eval.group_allocation import allocate
from eval.pilot_data import LABELS, digest, load_release, validate_release

BASE = "eval/datasets/capstone-v1/development/"
ANNOTATIONS = [
    BASE + name
    for name in (
        "synthetic-batch-001.json",
        "gemini-batch-001.annotated.json",
        "synthetic-batch-002.json",
    )
]


def validate_components(rows: list[dict], graph: dict) -> dict[str, str]:
    expected = {r["case_id"] for r in rows}
    listed = [i for c in graph["components"] for i in c["case_ids"]]
    if len(expected) != len(rows) or set(listed) != expected or len(listed) != len(expected):
        raise ValueError("Invalid component coverage")
    membership = {i: c["component_id"] for c in graph["components"] for i in c["case_ids"]}
    declared = {r["case_id"]: r["component_id"] for r in graph["membership"]}
    if membership != declared or len(declared) != len(graph["membership"]):
        raise ValueError("Component membership declarations disagree")
    for field in ("conversation_group_id", "paraphrase_group_id"):
        seen = {}
        for row in rows:
            component = membership[row["case_id"]]
            if seen.setdefault(row["grouping"][field], component) != component:
                raise ValueError("Conversation/paraphrase group divided")
    return membership


def prepare(root: Path) -> tuple[list[dict], dict, dict[str, str]]:
    hashes = {}

    def read(name: str):
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Source outside repository")
        hashes[name] = digest(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def read_pinned(name: str):
        data = read(name)
        for source in data.get("source_files", []):
            path = source["path"]
            if digest(root / path) != source["sha256_normalized_lf"]:
                raise ValueError(f"Source hash mismatch: {path}")
            if path.endswith(".json"):
                child = read(path)
                if isinstance(child, dict) and "source_files" in child:
                    read_pinned(path)
            else:
                hashes[path] = digest(root / path)
        return data

    schema = read(BASE + "record-format-v2.schema.json")
    validator = Draft202012Validator(schema)
    rows = []
    for name in ANNOTATIONS:
        batch = read(name)
        validator.validate(batch)
        rows.extend(batch)
    graph = read_pinned(BASE + "expanded-group-map.json")
    membership = validate_components(rows, graph)
    # Verify inherited and added known relations, not merely component counts.
    inherited = read(BASE + "combined-group-map.json")
    relations = [c["case_ids"] for c in inherited["components"]]
    relations += [r["case_ids"] for r in read(BASE + "batch-002-overlap-review.json")["relations"]]
    for ids in relations:
        if len({membership[i] for i in ids}) != 1:
            raise ValueError("Known overlap relation divided")
    for row in rows:
        ref = row["input"]["sanitized_context_reference"]
        if ref:
            context = read(ref)
            if hashes[ref] != row["input"]["context_sha256"]:
                raise ValueError("Context hash mismatch")
            catalogue = context.get("catalogue_reference")
            if catalogue:
                name = catalogue["path"]
                hashes[name] = digest(root / name)
                if hashes[name] != catalogue["sha256"]:
                    raise ValueError("Catalogue hash mismatch")
    supplement = read_pinned(BASE + "pilot2-overlap-review.json")
    parent = {g: g for g in membership.values()}

    def find(g: str) -> str:
        while parent[g] != g:
            g = parent[g]
        return g

    for relation in supplement["relations"]:
        ids = relation["case_ids"]
        for other in ids[1:]:
            parent[find(membership[other])] = find(membership[ids[0]])
    components = defaultdict(list)
    for case, group in membership.items():
        components[find(group)].append(case)
    groups = [
        {"component_id": f"pilot2-component-{i:03}", "case_ids": sorted(ids), "split": None}
        for i, ids in enumerate(sorted(components.values(), key=min), 1)
    ]
    reviewed = {
        "status": "frozen_synthetic_development_group_map",
        "source_files": [
            {"path": name, "sha256_normalized_lf": sha} for name, sha in sorted(hashes.items())
        ],
        "components": groups,
        "membership": [
            {"case_id": case, "component_id": group["component_id"]}
            for group in groups
            for case in group["case_ids"]
        ],
    }
    validate_components(rows, reviewed)
    return rows, reviewed, hashes


def freeze(root: Path, output: Path) -> dict:
    output = output.resolve()
    if not output.is_relative_to(root.resolve()) or output.exists():
        raise ValueError("Use a new repository output directory; existing evidence is preserved")
    rows, graph, hashes = prepare(root)
    membership = validate_components(rows, graph)
    records = [
        {
            "case_id": r["case_id"],
            "text": r["input"]["message"],
            "label": r["expected"]["intent"],
            "language": r["language_group"],
            "group": membership[r["case_id"]],
            "eligible": True,
        }
        for r in rows
        if r["comparison"]["intent_only_eligible"]
    ]
    if {r["label"] for r in records} != set(LABELS):
        raise ValueError("Expanded pilot requires all ten labels")
    assignments = allocate(records)
    for row in records:
        row["split"] = assignments[row["group"]]
    for name in (
        "eval/freeze_expanded_pilot.py",
        "eval/group_allocation.py",
        "docs/cap03-expanded-pilot-protocol.md",
    ):
        hashes[name] = digest(root / name)
    data = {
        "version": "synthetic-pilot-20261007-v2",
        "kind": "synthetic_development_pilot",
        "frozen": True,
        "unseen_count": 0,
        "labels": LABELS,
        "annotation_status": "reviewed_drafts",
        "independent_human_review": False,
        "annotation_files": ANNOTATIONS,
        "source_hashes": hashes,
        "protocol": "docs/cap03-expanded-pilot-protocol.md",
        "hash_convention": "UTF-8 bytes with CRLF normalized to LF",
        "allocation": {
            "method": "nearest20percent_then_lexicographic_whole_components",
            "scipy_version": importlib.metadata.version("scipy"),
            "min_train_rows_per_label": 8,
            "min_validation_rows_per_label": 4,
            "min_train_rows_per_label_language": 2,
            "min_validation_rows_per_label_language": 1,
            "min_train_components_per_label": 2,
            "min_validation_components_per_label": 1,
        },
        "records": records,
        "group_assignments": assignments,
        "excluded": [
            {
                "case_id": r["case_id"],
                "group": membership[r["case_id"]],
                "reason": r["comparison"]["eligibility_reason"],
            }
            for r in rows
            if not r["comparison"]["intent_only_eligible"]
        ],
        "limitations": [
            "Exposed synthetic development only; new examples authored after pilot1",
            "Bounded overlap review, not exhaustive private-history deduplication",
            "Three mutation components; authoring four-family target explicitly revised",
            "Final unseen evaluation and LLM comparison remain open",
        ],
    }
    publish_release(root, output, graph, data)
    return data


def publish_release(root: Path, output: Path, graph: dict, data: dict) -> None:
    """Validate staged bytes before atomically publishing a new release directory."""
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root) or output.exists():
        raise ValueError("Use a new repository output directory; existing evidence is preserved")
    output.parent.mkdir(parents=True, exist_ok=True)

    def write_json(path: Path, content: dict) -> None:
        formatted = subprocess.check_output(
            [
                "node",
                str(root / "node_modules/prettier/bin/prettier.cjs"),
                "--stdin-filepath",
                str(path),
            ],
            input=json.dumps(content, ensure_ascii=False).encode("utf-8"),
        )
        with path.open("xb") as handle:
            handle.write(formatted)

    with tempfile.TemporaryDirectory(prefix=".pilot2-", dir=output.parent) as temporary:
        stage = Path(temporary).resolve()
        if stage.parent != output.parent or not stage.is_relative_to(root):
            raise ValueError("Staging directory outside intended repository parent")
        staged_group = stage / "groups.json"
        write_json(staged_group, graph)
        final_name = (output / "groups.json").relative_to(root).as_posix()
        staged_name = staged_group.relative_to(root).as_posix()
        data["group_map"] = final_name
        data["source_hashes"][final_name] = digest(staged_group)
        validate_release(data)
        write_json(stage / "release.json", data)
        # The existing loader checks sources on disk. Remap only the unpublished
        # group path for this check; published bytes retain the permanent path.
        check = {**data, "group_map": staged_name, "source_hashes": dict(data["source_hashes"])}
        check["source_hashes"][staged_name] = check["source_hashes"].pop(final_name)
        check_path = stage / "validation.json"
        check_path.write_text(json.dumps(check, ensure_ascii=False), encoding="utf-8")
        load_release(check_path, root)
        check_path.unlink()
        if output.exists():
            raise ValueError("Existing evidence is preserved")
        stage.rename(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = freeze(Path(__file__).resolve().parents[1], args.output)
    print(json.dumps(dict(Counter(r["split"] for r in result["records"]))))


if __name__ == "__main__":
    main()
