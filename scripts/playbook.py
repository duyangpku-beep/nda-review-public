#!/usr/bin/env python3
"""
playbook.py — Local NDA playbook CRUD (no external dependencies)

Storage layout:
  ~/.nda-skill/
  ├── .env
  ├── playbook/
  │   ├── index.json
  │   └── NDA/
  │       ├── ci-definition.md
  │       └── ...
  └── reviews/

Usage:
  python3 playbook.py --save   --clause "CI Definition" --doc-type NDA \
      --standard "..." --fallback "..." --walkaway "..." \
      --notes "..." --priority High --category "Confidentiality" \
      --perspective receiving
  python3 playbook.py --load   --doc-type NDA
  python3 playbook.py --list
  python3 playbook.py --export-json  --output playbook_export.json
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

def _env_path(key: str, default: str) -> Path:
    raw = os.environ.get(key, default)
    return Path(raw).expanduser()

def playbook_dir() -> Path:
    return _env_path("NDA_SKILL_PLAYBOOK_DIR", "~/.nda-skill/playbook")

def clause_slug(name: str) -> str:
    """Convert clause name to a safe filename slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")

def clause_path(doc_type: str, clause_name: str) -> Path:
    return playbook_dir() / doc_type / f"{clause_slug(clause_name)}.md"

def index_path() -> Path:
    return playbook_dir() / "index.json"

# ── Index helpers ─────────────────────────────────────────────────────────────

def load_index() -> dict:
    p = index_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            print(
                f"WARNING: index.json is corrupt — will not overwrite. "
                f"Fix or delete {p} manually.",
                file=sys.stderr,
            )
            return {"clauses": [], "last_updated": None, "_corrupt": True}
        except OSError as e:
            print(f"WARNING: Could not read index file: {e}", file=sys.stderr)
    return {"clauses": [], "last_updated": None}

def save_index(idx: dict) -> None:
    if idx.get("_corrupt"):
        return  # Do not overwrite a corrupt index file
    index_path().parent.mkdir(parents=True, exist_ok=True)
    try:
        index_path().write_text(json.dumps(idx, indent=2, default=str))
    except OSError as e:
        print(f"ERROR: Could not save index: {e}", file=sys.stderr)
        raise

def upsert_index(clause_name: str, doc_type: str, priority: str, category: str) -> None:
    idx = load_index()
    key = f"{doc_type}/{clause_slug(clause_name)}"
    existing = next((c for c in idx["clauses"] if c.get("key") == key), None)
    entry = {
        "key": key,
        "clause": clause_name,
        "doc_type": doc_type,
        "priority": priority,
        "category": category,
        "updated": str(date.today()),
    }
    if existing:
        existing.update(entry)
    else:
        idx["clauses"].append(entry)
    idx["last_updated"] = str(date.today())
    save_index(idx)

# ── Clause file I/O ────────────────────────────────────────────────────────────

TEMPLATE = """\
---
clause: {clause}
doc-type: {doc_type}
perspective: {perspective}
priority: {priority}
category: {category}
updated: {updated}
---
## Standard Position
{standard}

## Acceptable Fallback
{fallback}

## Walk-Away / Red Line
{walkaway}

## Notes
{notes}
"""

def read_clause(path: Path) -> dict:
    """Parse frontmatter + section bodies from a clause .md file."""
    text = path.read_text()
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    meta = {}
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    sections = {}
    for heading, content in re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL):
        sections[heading.strip()] = content.strip()
    return {**meta, **sections}

def save_clause(args: argparse.Namespace) -> str:
    """Save (create or update) a clause file. Returns 'NEW' | 'UPDATED' | 'UNCHANGED'."""
    path = clause_path(args.doc_type, args.clause)
    path.parent.mkdir(parents=True, exist_ok=True)

    new_data = {
        "standard":    args.standard or "",
        "fallback":    args.fallback or "",
        "walkaway":    args.walkaway or "",
        "notes":       args.notes or "",
        "priority":    args.priority or "Medium",
        "category":    args.category or "General",
        "perspective": args.perspective or "receiving",
    }

    if path.exists():
        old = read_clause(path)
        changed_fields = []
        section_map = {
            "standard":  "Standard Position",
            "fallback":  "Acceptable Fallback",
            "walkaway":  "Walk-Away / Red Line",
            "notes":     "Notes",
        }
        for field, section in section_map.items():
            if new_data[field] and new_data[field] != old.get(section, ""):
                changed_fields.append(section)
        for field in ("priority", "category", "perspective"):
            if new_data[field] and new_data[field] != old.get(field, ""):
                changed_fields.append(field)
        if not changed_fields:
            return "UNCHANGED"
        result = f"UPDATED ({', '.join(changed_fields)})"
    else:
        result = "NEW"

    content = TEMPLATE.format(
        clause=args.clause,
        doc_type=args.doc_type,
        perspective=new_data["perspective"],
        priority=new_data["priority"],
        category=new_data["category"],
        updated=str(date.today()),
        standard=new_data["standard"] or "(not set)",
        fallback=new_data["fallback"] or "(not set)",
        walkaway=new_data["walkaway"] or "(not set)",
        notes=new_data["notes"] or "",
    )
    try:
        path.write_text(content)
    except OSError as e:
        print(f"ERROR: Could not write clause file {path}: {e}", file=sys.stderr)
        sys.exit(1)
    upsert_index(args.clause, args.doc_type, new_data["priority"], new_data["category"])
    return result

def load_clauses(doc_type: str | None = None) -> list[dict]:
    """Load all clauses (optionally filtered by doc_type)."""
    base = playbook_dir()
    results = []
    if doc_type:
        doc_dir = base / doc_type
        if not doc_dir.exists():
            return []
        paths = sorted(doc_dir.glob("*.md"))
    else:
        paths = sorted(base.rglob("*.md"))

    for p in paths:
        try:
            data = read_clause(p)
            data["_file"] = str(p)
            results.append(data)
        except Exception as e:
            print(f"WARNING: Skipping {p}: {e}", file=sys.stderr)
    return results

# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="NDA Playbook CRUD")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--save",        action="store_true", help="Save a clause position")
    group.add_argument("--load",        action="store_true", help="Load clauses")
    group.add_argument("--list",        action="store_true", help="List all clauses (summary)")
    group.add_argument("--export-json", action="store_true", help="Export full playbook as JSON")

    # --save args
    parser.add_argument("--clause",      help="Clause name (e.g. 'CI Definition')")
    parser.add_argument("--doc-type",    default="NDA", help="Document type (default: NDA)")
    parser.add_argument("--standard",   default="", help="Standard position text")
    parser.add_argument("--fallback",   default="", help="Acceptable fallback text")
    parser.add_argument("--walkaway",   default="", help="Walk-away / red line text")
    parser.add_argument("--notes",      default="", help="Context / rationale")
    parser.add_argument("--priority",   default="Medium", choices=["High", "Medium", "Low"])
    parser.add_argument("--category",   default="General", help="Clause category")
    parser.add_argument("--perspective",default="receiving", choices=["receiving", "disclosing"])

    # --load / --export-json args
    parser.add_argument("--output", default="", help="Output JSON file path")

    args = parser.parse_args()

    if args.save:
        if not args.clause:
            parser.error("--save requires --clause")
        result = save_clause(args)
        print(f"RESULT: {result}")
        print(f"File  : {clause_path(args.doc_type, args.clause)}")

    elif args.load:
        clauses = load_clauses(args.doc_type)
        if not clauses:
            print("(no playbook entries found)")
        for c in clauses:
            name     = c.get("clause", c.get("_file", "?"))
            priority = c.get("priority", "?")
            standard = c.get("Standard Position", "(not set)")[:80]
            print(f"[{priority:6s}] {name}")
            print(f"         Standard: {standard}")
            print()

    elif args.list:
        idx = load_index()
        clauses = idx.get("clauses", [])
        if not clauses:
            print("(empty playbook)")
        for c in clauses:
            print(f"{c['doc_type']:6s} | {c['priority']:6s} | {c['clause']}")

    elif args.export_json:
        clauses = load_clauses(args.doc_type)
        output = {"exported": str(date.today()), "clauses": clauses}
        if args.output:
            try:
                Path(args.output).write_text(json.dumps(output, indent=2))
            except OSError as e:
                print(f"ERROR: Could not write export file {args.output}: {e}", file=sys.stderr)
                sys.exit(1)
            print(f"Exported {len(clauses)} clauses to {args.output}")
        else:
            print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
