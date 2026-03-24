#!/usr/bin/env python3
"""
notebook_sync.py — Sync NDA playbook to a configured notebook adapter.

Supported adapters:
  markdown     — Copy .md files to a local folder
  obsidian     — PUT to Obsidian Local REST API
  notion       — Create/update pages in a Notion database
  apple_notes  — Create notes via AppleScript (macOS only)

Usage:
  python3 notebook_sync.py --adapter markdown
  python3 notebook_sync.py --adapter obsidian
  python3 notebook_sync.py --adapter notion
  python3 notebook_sync.py --adapter apple_notes

Config is read from ~/.nda-skill/.env (see .env.example).
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── .env loader ───────────────────────────────────────────────────────────────

def load_env(env_path: Path | None = None) -> dict:
    """Load key=value pairs from a .env file into a dict (does not modify os.environ)."""
    if env_path is None:
        env_path = Path.home() / ".nda-skill" / ".env"
    config = {}
    if not env_path.exists():
        return config
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            config[k.strip()] = v.strip().strip('"').strip("'")
    return config


def cfg(key: str, config: dict, default: str = "") -> str:
    """Resolve a config value: env var overrides .env file."""
    return os.environ.get(key) or config.get(key) or default


# ── Playbook loader ────────────────────────────────────────────────────────────

def load_playbook_files(playbook_dir: Path) -> list[tuple[str, str]]:
    """Return list of (relative_path, content) for all .md files in playbook_dir."""
    results = []
    for p in sorted(playbook_dir.rglob("*.md")):
        rel = p.relative_to(playbook_dir)
        results.append((str(rel), p.read_text()))
    return results


# ── Adapter: Markdown folder ───────────────────────────────────────────────────

def sync_markdown(playbook_dir: Path, config: dict) -> None:
    target_raw = cfg("NOTEBOOK_MARKDOWN_PATH", config)
    if not target_raw:
        raise ValueError("NOTEBOOK_MARKDOWN_PATH is not set in .env")
    target = Path(target_raw).expanduser()
    target.mkdir(parents=True, exist_ok=True)

    files = load_playbook_files(playbook_dir)
    count = 0
    for rel, content in files:
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        count += 1
        print(f"  → {dest}")

    print(f"✅ Markdown sync: {count} file(s) copied to {target}")


# ── Adapter: Obsidian REST API ─────────────────────────────────────────────────

def sync_obsidian(playbook_dir: Path, config: dict) -> None:
    try:
        import requests
        import urllib3
    except ImportError:
        print("ERROR: requests is required for Obsidian adapter. Run: pip install requests")
        sys.exit(1)

    base_url = cfg("OBSIDIAN_API_URL", config, "https://127.0.0.1:27124")
    api_key  = cfg("OBSIDIAN_API_KEY", config)
    vault_path = cfg("OBSIDIAN_VAULT_PATH", config, "Legal/NDA Playbook")
    verify_ssl_raw = cfg("OBSIDIAN_VERIFY_SSL", config, "true")
    verify_ssl = verify_ssl_raw.lower() not in ("false", "0", "no")

    if not api_key:
        raise ValueError("OBSIDIAN_API_KEY is not set in .env")

    if not verify_ssl:
        # Suppress only for localhost connections to Obsidian's self-signed cert
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "text/markdown",
    }

    files = load_playbook_files(playbook_dir)
    count = 0
    for rel, content in files:
        note_path = f"{vault_path}/{rel}".replace("\\", "/")
        url = f"{base_url}/vault/{note_path}"
        try:
            resp = requests.put(url, data=content.encode("utf-8"), headers=headers, verify=verify_ssl)
        except requests.RequestException as e:
            print(f"  ✗ {note_path} — connection error: {e}")
            continue
        if resp.status_code in (200, 201, 204):
            print(f"  ✓ {note_path}")
            count += 1
        else:
            print(f"  ✗ {note_path} — HTTP {resp.status_code}: {resp.text[:100]}")

    print(f"✅ Obsidian sync: {count}/{len(files)} file(s) written")


# ── Adapter: Notion ───────────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> dict:
    fm_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    meta = {}
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    return meta


def _extract_section(content: str, section: str) -> str:
    match = re.search(rf"^## {re.escape(section)}\n(.*?)(?=^## |\Z)", content, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def sync_notion(playbook_dir: Path, config: dict) -> None:
    # NOTE: This adapter always creates new Notion pages (POST /pages).
    # Re-running will create duplicates. Deduplicate by Name property in Notion,
    # or implement a search-then-patch flow if idempotency is needed.
    try:
        import requests
    except ImportError:
        print("ERROR: requests is required for Notion adapter. Run: pip install requests")
        sys.exit(1)

    token = cfg("NOTION_TOKEN", config)
    db_id = cfg("NOTION_DATABASE_ID", config)

    if not token:
        raise ValueError("NOTION_TOKEN is not set in .env")
    if not db_id:
        raise ValueError("NOTION_DATABASE_ID is not set in .env")

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    files = load_playbook_files(playbook_dir)
    count = 0
    for rel, content in files:
        meta = _parse_frontmatter(content)
        clause    = meta.get("clause", Path(rel).stem)
        doc_type  = meta.get("doc-type", "NDA")
        priority  = meta.get("priority", "Medium")
        category  = meta.get("category", "General")
        standard  = _extract_section(content, "Standard Position")
        fallback  = _extract_section(content, "Acceptable Fallback")
        walkaway  = _extract_section(content, "Walk-Away / Red Line")
        notes     = _extract_section(content, "Notes")

        page_data = {
            "parent": {"database_id": db_id},
            "properties": {
                "Name":             {"title": [{"text": {"content": clause}}]},
                "Document Type":    {"select": {"name": doc_type}},
                "Priority":         {"select": {"name": priority}},
                "Clause Category":  {"select": {"name": category}},
                "Standard Position":{"rich_text": [{"text": {"content": standard[:2000]}}]},
                "Acceptable Fallback":{"rich_text": [{"text": {"content": fallback[:2000]}}]},
                "Walk-Away / Red Line":{"rich_text": [{"text": {"content": walkaway[:2000]}}]},
                "Notes":            {"rich_text": [{"text": {"content": notes[:2000]}}]},
            },
        }

        try:
            resp = requests.post(
                "https://api.notion.com/v1/pages",
                json=page_data,
                headers=headers,
            )
        except requests.RequestException as e:
            print(f"  ✗ {clause} — connection error: {e}")
            continue
        if resp.status_code == 200:
            print(f"  ✓ Created Notion page: {clause}")
            count += 1
        else:
            print(f"  ✗ {clause} — HTTP {resp.status_code}: {resp.text[:150]}")

    print(f"✅ Notion sync: {count}/{len(files)} page(s) created")


# ── Adapter: Apple Notes ──────────────────────────────────────────────────────

APPLE_SCRIPT_TEMPLATE = """\
tell application "Notes"
    tell account "iCloud"
        if not (exists folder "{folder}") then
            make new folder with properties {{name:"{folder}"}}
        end if
        set targetFolder to folder "{folder}"
        set noteContent to "{content}"
        set noteTitle to "{title}"
        make new note at targetFolder with properties {{name:noteTitle, body:noteContent}}
    end tell
end tell
"""


def sync_apple_notes(playbook_dir: Path, config: dict) -> None:
    if sys.platform != "darwin":
        raise EnvironmentError("Apple Notes adapter requires macOS")

    folder = cfg("APPLE_NOTES_FOLDER", config, "NDA Playbook")
    files = load_playbook_files(playbook_dir)
    count = 0

    for rel, content in files:
        title = Path(rel).stem.replace("-", " ").title()
        # Escape for AppleScript
        escaped = content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        escaped = escaped.replace("{", "{{").replace("}", "}}")
        script = APPLE_SCRIPT_TEMPLATE.format(
            folder=folder,
            title=title,
            content=escaped[:8000],  # Apple Notes truncates very large notes
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✓ {title}")
            count += 1
        else:
            print(f"  ✗ {title} — {result.stderr.strip()[:100]}")

    print(f"✅ Apple Notes sync: {count}/{len(files)} note(s) created")


# ── Main ───────────────────────────────────────────────────────────────────────

ADAPTERS = {
    "markdown":    sync_markdown,
    "obsidian":    sync_obsidian,
    "notion":      sync_notion,
    "apple_notes": sync_apple_notes,
}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Sync NDA playbook to a notebook adapter")
    parser.add_argument(
        "--adapter",
        choices=list(ADAPTERS.keys()),
        help="Notebook adapter (overrides NOTEBOOK_ADAPTER in .env)",
    )
    parser.add_argument(
        "--playbook-dir",
        default="",
        help="Playbook directory (default: ~/.nda-skill/playbook)",
    )
    args = parser.parse_args()

    config = load_env()

    adapter_name = args.adapter or cfg("NOTEBOOK_ADAPTER", config, "markdown")
    if adapter_name not in ADAPTERS:
        print(f"ERROR: Unknown adapter '{adapter_name}'. Choose from: {', '.join(ADAPTERS)}")
        sys.exit(1)

    playbook_root_raw = args.playbook_dir or cfg("NDA_SKILL_PLAYBOOK_DIR", config, "~/.nda-skill/playbook")
    playbook_root = Path(playbook_root_raw).expanduser()

    if not playbook_root.exists():
        print(f"ERROR: Playbook directory not found: {playbook_root}")
        print("Run /nda-review --setup first, then /nda-review --learn to build your playbook.")
        sys.exit(1)

    print(f"Syncing playbook to [{adapter_name}] adapter...")
    print(f"  Source: {playbook_root}")
    print()

    try:
        ADAPTERS[adapter_name](playbook_root, config)
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Check ~/.nda-skill/.env and ensure the required keys are set.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
