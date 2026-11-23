"""Online catalogue copies preserve a single SQLite snapshot, never inference history."""

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path


def inspect(database):
    if database.execute("PRAGMA quick_check").fetchone() != ("ok",):
        raise ValueError("Catalogue integrity failed")
    rows = database.execute("SELECT schema_version,revision FROM catalogue_meta").fetchall()
    if len(rows) != 1 or rows[0][0] != 1 or rows[0][1] < 1:
        raise ValueError("Incompatible catalogue")
    tables = database.execute(
        "SELECT name,sql FROM sqlite_schema WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    if not {"products", "product_attributes", "product_fts"}.issubset({r[0] for r in tables}):
        raise ValueError("Incomplete catalogue")
    digest = hashlib.sha256()
    for name, schema in tables:
        quoted = '"' + name.replace('"', '""') + '"'
        content = sorted(database.execute(f"SELECT * FROM {quoted}").fetchall(), key=repr)
        digest.update(repr((schema, content)).encode("utf-8"))
    return {"schema": rows[0][0], "revision": rows[0][1], "content_sha256": digest.hexdigest()}


def catalogue_status(path):
    path = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as database:
        database.execute("BEGIN")
        return inspect(database)


def copy_catalogue(source, output):
    source, output = Path(source).resolve(strict=True), Path(output).absolute()
    if source == output.resolve() or output.exists() or output.is_symlink():
        raise ValueError("Catalogue copy requires a new destination")
    # Check the source before creating output; an allowance/admission file is not
    # a catalogue and must never become a release restore candidate.
    created = False
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as live:
            live.execute("BEGIN")
            before = inspect(live)
            output.touch(mode=0o600, exist_ok=False)
            created = True
            with closing(sqlite3.connect(output)) as target:
                live.backup(target)
                if inspect(target) != before:
                    raise ValueError("Catalogue copy verification failed")
        return before
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
