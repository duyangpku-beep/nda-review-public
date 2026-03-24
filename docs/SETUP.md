# Setup Guide

Step-by-step installation instructions for `nda-review-skill`.

---

## Prerequisites

- **Python 3.10+** — check with `python3 --version`
- **Claude Code** — installed and working (`/help` in any terminal)
- **pip** — bundled with Python; check with `pip3 --version`

Optional but recommended:
- **pandoc** — improves DOCX text extraction quality
  macOS: `brew install pandoc` | Linux: `sudo apt install pandoc`

---

## Method 1: Manual Install (Recommended)

### Step 1 — Clone the repo into Claude's skills directory

```bash
git clone https://github.com/<user>/nda-review-skill \
    ~/.claude/skills/nda-review
```

### Step 2 — Run install.sh

```bash
bash ~/.claude/skills/nda-review/install.sh
```

This will:
- Create `~/.nda-skill/` with the correct directory structure
- Symlink `~/.nda-skill/scripts/` → `~/.claude/skills/nda-review/scripts/`
- Copy `.env.example` → `~/.nda-skill/.env`
- Install Python dependencies (`python-docx`, `lxml`, `requests`)

### Step 3 — Edit your .env

```bash
open ~/.nda-skill/.env    # macOS
nano ~/.nda-skill/.env    # Linux / terminal
```

At minimum, set:
```bash
NDA_SKILL_REVIEWER_NAME="Your Name"
```

### Step 4 — Verify in Claude Code

Open a new Claude Code session and run:
```
/nda-review --setup
```

You should see a confirmation that setup is complete.

---

## Method 2: OpenClaw

If you have OpenClaw installed:

```bash
openclaw install github.com/<user>/nda-review-skill
```

Then run `/nda-review --setup` to complete configuration.

---

## Method 3: pip install + manual skill registration

```bash
# 1. Install Python dependencies
pip install python-docx lxml requests

# 2. Create data directory
mkdir -p ~/.nda-skill/playbook/NDA ~/.nda-skill/reviews
echo '{"clauses":[],"last_updated":null}' > ~/.nda-skill/playbook/index.json

# 3. Clone scripts somewhere accessible
git clone https://github.com/<user>/nda-review-skill /tmp/nda-review-skill

# 4. Symlink scripts
ln -sf /tmp/nda-review-skill/scripts ~/.nda-skill/scripts

# 5. Copy .env template
cp /tmp/nda-review-skill/.env.example ~/.nda-skill/.env

# 6. Register the skill with Claude Code
mkdir -p ~/.claude/skills
ln -sf /tmp/nda-review-skill ~/.claude/skills/nda-review
```

---

## Directory Structure After Install

```
~/.nda-skill/
├── .env                ← Your personal config (never committed to git)
├── playbook/
│   ├── index.json      ← Fast lookup index
│   └── NDA/            ← One .md file per clause position
└── reviews/            ← Past review summaries

~/.claude/skills/nda-review/
├── SKILL.md            ← Claude Code skill entry point
├── scripts/            ← Python scripts (also linked from ~/.nda-skill/scripts/)
├── templates/          ← Sample NDA
└── docs/               ← This documentation
```

---

## Updating

```bash
cd ~/.claude/skills/nda-review
git pull
# Re-run install only if requirements changed:
pip install -r requirements.txt
```

---

## Uninstall

```bash
# Remove skill files
rm -rf ~/.claude/skills/nda-review

# Optionally remove your playbook data
# WARNING: this deletes all your saved positions
rm -rf ~/.nda-skill
```

---

## Troubleshooting

### `/nda-review` not found
Make sure the skill directory name is exactly `nda-review`:
```bash
ls ~/.claude/skills/
# Should show: nda-review
```

### `python-docx` import errors
```bash
pip install --upgrade python-docx lxml
python3 -c "import docx; print(docx.__version__)"
```

### `.env` not loading
The scripts look for `~/.nda-skill/.env`. Check it exists:
```bash
cat ~/.nda-skill/.env
```

### Scripts not found
Check the symlink:
```bash
ls -la ~/.nda-skill/scripts
# Should show: scripts -> ~/.claude/skills/nda-review/scripts (or wherever you cloned)
```

If broken, re-run `bash install.sh` or:
```bash
ln -sf ~/.claude/skills/nda-review/scripts ~/.nda-skill/scripts
```
