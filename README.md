# nda-review-skill

A Claude Code skill for reviewing NDAs clause by clause, building a personal negotiation playbook,
and generating track-changes Word documents — with zero cloud dependencies.

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://github.com/anthropics/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- **Triage in seconds** — GREEN / YELLOW / RED classification with an issue table
- **13-point checklist** — covers all critical NDA clauses from CI definition to arbitration
- **Track-changes DOCX** — proper `w:ins`/`w:del` XML; counterparty can accept/reject in Word
- **Personal playbook** — your negotiation positions stored locally in Markdown, never in the cloud
- **Learn mode** — walk through clauses interactively to build your playbook from scratch
- **4 notebook adapters** — sync your playbook to Obsidian, Notion, a Markdown folder, or Apple Notes
- **Zero hardcoded secrets** — all config via `~/.nda-skill/.env`

---

## Quickstart

### 1. Install

```bash
# Clone or install via OpenClaw
git clone https://github.com/<user>/nda-review-skill ~/.claude/skills/nda-review

# Run one-time setup
bash ~/.claude/skills/nda-review/install.sh
```

Or with OpenClaw:
```bash
openclaw install github.com/<user>/nda-review-skill
```

### 2. First run — setup

```
/nda-review --setup
```

### 3. Build your playbook (optional but recommended)

```
/nda-review --learn
```

Walk through a sample Mutual NDA clause by clause. Set your standard, fallback, and
walk-away positions. The skill saves them to `~/.nda-skill/playbook/NDA/`.

### 4. Review a real NDA

```
/nda-review path/to/counterparty_nda.docx
```

Get a triage report with your playbook positions loaded, then generate a redlined DOCX.

---

## Usage

| Command | What it does |
|---------|-------------|
| `/nda-review --setup` | First-run setup wizard |
| `/nda-review --learn` | Build playbook using sample Mutual NDA |
| `/nda-review --learn file.docx` | Build playbook from your own NDA |
| `/nda-review path/to/nda.docx` | Full NDA review + redline |
| `/nda-review --sync` | Push playbook to your configured notebook |

---

## What gets reviewed

The skill checks 13 criteria on every NDA:

1. Mutuality of obligations
2. CI definition — temporal scope (pre-signing coverage)
3. CI definition — oral disclosure confirmation window
4. All four standard carveouts (public domain, prior possession, independent dev, 3rd-party)
5. Permitted disclosees (professional advisors included?)
6. Compelled disclosure clause (advance notice + cooperation)
7. Return/destruction — Receiving Party election
8. Return/destruction — backup system retention exception
9. Confidentiality term (2 vs. 3 vs. 5 years)
10. Governing law jurisdiction
11. Arbitration institution and seat
12. Assignment restrictions
13. Unusual provisions (non-solicitation, non-compete, residuals, injunctive relief)

---

## Playbook Storage

Your playbook lives at `~/.nda-skill/playbook/` — completely private, never committed to git.

```
~/.nda-skill/
├── .env                    ← your config
├── playbook/
│   └── NDA/
│       ├── ci-definition.md
│       ├── permitted-disclosees.md
│       └── ...
└── reviews/
    └── 2026-03-23-Acme-NDA-review.md
```

Each clause file is plain Markdown with YAML frontmatter:
```yaml
---
clause: CI Definition
doc-type: NDA
perspective: receiving
priority: High
category: Confidentiality
---
## Standard Position
On or after signing date only — no pre-signing coverage.

## Acceptable Fallback
Add explicit carveout for pre-signing disclosures with a defined list.

## Walk-Away / Red Line
Unlimited retroactive coverage with no carveout.
```

---

## Notebook Integrations

Sync your playbook to any of:

| Adapter | Config key | Notes |
|---------|-----------|-------|
| `markdown` | `NOTEBOOK_MARKDOWN_PATH` | Copies .md files to any local folder |
| `obsidian` | `OBSIDIAN_API_URL`, `OBSIDIAN_API_KEY` | Requires Local REST API plugin |
| `notion` | `NOTION_TOKEN`, `NOTION_DATABASE_ID` | Creates/updates Notion pages |
| `apple_notes` | (none — macOS only) | Creates notes via AppleScript |

See [docs/NOTEBOOK_INTEGRATIONS.md](docs/NOTEBOOK_INTEGRATIONS.md) for setup instructions.

---

## Security

- **No hardcoded secrets** — all credentials via `~/.nda-skill/.env`
- **`.env` excluded from git** — `.gitignore` blocks it
- **Playbook stays local** — stored in `~/.nda-skill/`, never in the repo
- **SSL verification on by default** — configurable per adapter

---

## Requirements

- Python 3.10+
- `python-docx`, `lxml` (for DOCX generation)
- `requests` (optional — only for Obsidian / Notion adapters)
- `pandoc` (optional — for best-quality text extraction from DOCX)

Install: `pip install python-docx lxml requests`

---

## File Structure

```
nda-review-skill/
├── SKILL.md                    ← Claude Code skill entry point
├── README.md                   ← This file
├── LICENSE                     ← MIT
├── install.sh                  ← One-time setup
├── requirements.txt
├── .env.example                ← Config template
├── .gitignore
├── scripts/
│   ├── playbook.py             ← Playbook CRUD (local JSON + Markdown)
│   ├── generate_redline.py     ← Word track-changes DOCX generation
│   └── notebook_sync.py        ← 4 notebook adapters
├── templates/
│   └── mutual_nda.md           ← Sample Mutual NDA for --learn mode
└── docs/
    ├── SETUP.md
    └── NOTEBOOK_INTEGRATIONS.md
```

---

## License

MIT — see [LICENSE](LICENSE).
