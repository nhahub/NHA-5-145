"""Frozen synthetic holdout integrity; never a runtime authority boundary."""

import hashlib
import json
import re
import unicodedata
from collections import Counter
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from eval.pilot_data import LABELS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs_digest(records):
    pairs = sorted((r["case_id"], r["input"]["message"]) for r in records)
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False).encode()).hexdigest()


def validate_overlap(records, review, overlap):
    ids = {r["case_id"] for r in records}
    audited = overlap.get("cases", [])
    if (
        overlap.get("inputs_sha256") != inputs_digest(records)
        or len(audited) != len(ids)
        or {r["case_id"] for r in audited} != ids
        or not overlap.get("source_hashes")
        or overlap.get("prior_candidate_count", 0) <= 0
    ):
        raise ValueError("Missing or mismatched overlap evidence")
    for row in audited:
        if any(pair.get("normalized_exact") for pair in row["nearest_prior"]):
            raise ValueError("Unresolved exact regression/debug overlap")
    if any(
        r.get("overlap_status") != "resolved" or not r.get("overlap_disposition")
        for r in review["records"]
    ):
        raise ValueError("Unresolved overlap review")


def normalized(text: str) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).casefold())


def checked_file(root: Path, name: str, expected: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or sha256(path) != expected:
        raise ValueError("Frozen source path/hash mismatch")
    return path


def validate_records(records, protocol, review, development):
    if len(records) != protocol["target_count"]:
        raise ValueError("Holdout count mismatch")
    ids, texts = set(), set()
    development_text = {normalized(r["text"]) for r in development["records"]}
    development_groups = {r["group"] for r in development["records"]}
    decisions = {r["case_id"]: r for r in review["records"]}
    if len(decisions) != len(review["records"]) or review.get("status") != "approved_ai_review":
        raise ValueError("Review is incomplete or duplicated")
    cells = Counter()
    for row in records:
        case_id, text = row["case_id"], row["input"]["message"]
        norm = normalized(text)
        if not norm or case_id in ids or norm in texts or norm in development_text:
            raise ValueError("Duplicate/empty case or development overlap")
        ids.add(case_id)
        texts.add(norm)
        if not row["eligible_for_evaluation"] or not row["comparison"]["intent_only_eligible"]:
            raise ValueError("Ineligible scored record")
        if row["input"]["requires_context"] or row["input"]["followup_turns"]:
            raise ValueError("Contextual case in text-only comparison")
        groups = row["grouping"]
        if groups["split"] != "synthetic_test" or any(
            not groups[k] or groups[k] in development_groups
            for k in ("paraphrase_group_id", "conversation_group_id")
        ):
            raise ValueError("Invalid split or cross-split group")
        annotation = row["annotation"]
        decision = decisions.get(case_id, {})
        if (
            annotation["status"] != "reviewed_synthetic"
            or not annotation["reviewer_id"]
            or annotation["reviewer_id"] == annotation["annotator_id"]
            or decision.get("final_intent") != row["expected"]["intent"]
            or decision.get("status") != "accepted"
        ):
            raise ValueError("Missing separate annotation review")
        cells[(row["expected"]["intent"], row["language_group"])] += 1
    expected = Counter(
        {
            (label, lang): protocol["cases_per_cell"]
            for label in protocol["labels"]
            for lang in protocol["languages"]
        }
    )
    if cells != expected or set(decisions) != ids:
        raise ValueError("Incomplete class/language/review coverage")


def load_frozen_release(path: Path, root: Path) -> dict:
    release = json.loads(path.read_text(encoding="utf-8"))
    if release.get("kind") != "synthetic_holdout" or release.get("independent_human_count") != 0:
        raise ValueError("Invalid synthetic evidence claim")
    loaded = {}
    for key in ("protocol", "records", "review", "overlap"):
        file = checked_file(root, release[key], release[key + "_sha256"])
        loaded[key] = json.loads(file.read_text(encoding="utf-8"))
    protocol = loaded["protocol"]
    if protocol["labels"] != LABELS or protocol["target_count"] != 120 or release["count"] != 120:
        raise ValueError("Frozen protocol coverage mismatch")
    development_file = checked_file(
        root, protocol["development_release"], protocol["development_sha256"]
    )
    development = json.loads(development_file.read_text(encoding="utf-8"))
    schema_file = checked_file(root, release["schema"], release["schema_sha256"])
    Draft202012Validator(json.loads(schema_file.read_text(encoding="utf-8"))).validate(
        loaded["records"]
    )
    if release["audit_sources"] != loaded["overlap"]["source_hashes"]:
        raise ValueError("Overlap source manifest is incomplete")
    for name, expected in release["audit_sources"].items():
        checked_file(root, name, expected)
    validate_records(loaded["records"], protocol, loaded["review"], development)
    validate_overlap(loaded["records"], loaded["review"], loaded["overlap"])
    return {
        **loaded,
        "release_sha256": sha256(path),
        **{key: value for key, value in release.items() if key.endswith("_sha256")},
    }


def holdout_schema(root: Path):
    source = root / "eval/datasets/capstone-v1/development/record-format-v2.schema.json"
    schema = deepcopy(json.loads(source.read_text(encoding="utf-8")))
    schema["$id"] = "urn:shopping-copilot:synthetic-holdout:20261009"
    schema["title"] = "Reviewed synthetic holdout; not independent human evidence"
    schema["minItems"] = schema["maxItems"] = 120
    props = schema["items"]["properties"]
    props["dataset_version"] = {"const": "synthetic-holdout-20261009"}
    props["eligible_for_evaluation"] = {"const": True}
    group = props["grouping"]["properties"]
    group["split"] = {"const": "synthetic_test"}
    group["duplicate_review"] = {"const": "reviewed_before_evaluation"}
    annotation = props["annotation"]["properties"]
    annotation["reviewer_id"] = {"type": "string", "minLength": 1}
    annotation["status"] = {"const": "reviewed_synthetic"}
    annotation["disagreements"] = {"type": "array"}
    annotation["resolution"] = {"type": "string", "minLength": 1}
    return schema
