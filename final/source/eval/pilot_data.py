"""Offline synthetic-pilot release checks; never grants runtime Action authority."""

import hashlib
import json
from pathlib import Path

LABELS = [
    "advice",
    "find_products",
    "locate",
    "navigate",
    "open_product",
    "mutate",
    "cart_edit",
    "help",
    "off_topic",
    "unsupported",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def pinned_source(root: Path, source: str, expected: str) -> Path:
    resolved = (root / source).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Source outside repository: {source}")
    if resolved.is_file() and digest(resolved) == expected:
        return resolved
    # The historical catalogue module moved to SQLite. Preserve its exact release
    # bytes without weakening hashes for annotations, splits, or other sources.
    if (
        source == "store/src/catalogue.ts"
        and len(expected) == 64
        and all(c in "0123456789abcdef" for c in expected)
    ):
        archived = root / "eval/frozen-sources" / (expected + ".txt")
        if archived.is_file() and digest(archived) == expected:
            return archived
    raise ValueError(f"Source hash mismatch: {source}")


def validate_release(data: dict) -> None:
    if data.get("kind") != "synthetic_development_pilot" or data.get("unseen_count") != 0:
        raise ValueError("Pilot cannot claim unseen evaluation")
    labels = data["labels"]
    if labels != LABELS:
        raise ValueError("Invalid label order")
    ids, texts, groups = set(), set(), {}
    for row in data["records"]:
        if row["case_id"] in ids or row["text"] in texts:
            raise ValueError("duplicate ID or text")
        ids.add(row["case_id"])
        texts.add(row["text"])
        if not row["eligible"]:
            raise ValueError("Scored record is not eligible")
        if row["label"] not in labels or row["split"] not in {"train", "validation"}:
            raise ValueError("Invalid label or split")
        if not row["text"].strip() or not row["group"]:
            raise ValueError("Empty text or group")
        if groups.setdefault(row["group"], row["split"]) != row["split"]:
            raise ValueError("Connected group crosses splits")
    train = {r["label"] for r in data["records"] if r["split"] == "train"}
    validation = {r["label"] for r in data["records"] if r["split"] == "validation"}
    if len(train) < 2 or not validation or not validation <= train:
        raise ValueError("Training/validation class support is insufficient")


def load_release(path: Path, root: Path) -> dict:
    content = path.read_bytes().replace(b"\r\n", b"\n")
    data = json.loads(content)
    validate_release(data)
    for source, expected in data["source_hashes"].items():
        pinned_source(root, source, expected)
    required = [*data["annotation_files"], data["group_map"]]
    if any(name not in data["source_hashes"] for name in required):
        raise ValueError("Unhashed annotation/group source")
    originals = {}
    for name in data["annotation_files"]:
        for row in json.loads((root / name).read_text(encoding="utf-8")):
            if row["case_id"] in originals:
                raise ValueError("Duplicate source annotation")
            originals[row["case_id"]] = row
    membership = json.loads((root / data["group_map"]).read_text(encoding="utf-8"))["membership"]
    groups = {row["case_id"]: row["component_id"] for row in membership}
    if len(groups) != len(membership) or set(groups) != set(originals):
        raise ValueError("Invalid annotation/group coverage")
    for row in data["records"]:
        original = originals.get(row["case_id"])
        if original is None or (
            row["text"] != original["input"]["message"]
            or row["label"] != original["expected"]["intent"]
            or row["language"] != original["language_group"]
            or row["eligible"] != original["comparison"]["intent_only_eligible"]
            or row["group"] != groups[row["case_id"]]
        ):
            raise ValueError("Release row differs from annotation/group source")
    data["_loaded_sha256"] = hashlib.sha256(content).hexdigest()
    return data
