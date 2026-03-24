#!/usr/bin/env bash
# install.sh — One-time setup for nda-review-skill
# Usage: bash install.sh [--no-pip]
set -e

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
NDA_HOME="$HOME/.nda-skill"
NO_PIP=false

for arg in "$@"; do
  case $arg in
    --no-pip) NO_PIP=true ;;
  esac
done

echo "▶ Installing nda-review-skill..."
echo "  Skill directory : $SKILL_DIR"
echo "  Data directory  : $NDA_HOME"
echo ""

# 1. Create directory structure
mkdir -p "$NDA_HOME/playbook/NDA"
mkdir -p "$NDA_HOME/reviews"
echo "  ✓ Created $NDA_HOME/{playbook/NDA, reviews}"

# 2. Symlink scripts so SKILL.md can always find them at a stable path
if [ -L "$NDA_HOME/scripts" ]; then
  rm "$NDA_HOME/scripts"
fi
ln -sf "$SKILL_DIR/scripts" "$NDA_HOME/scripts"
echo "  ✓ Symlinked scripts → $NDA_HOME/scripts"

# 3. Copy .env.example → ~/.nda-skill/.env if not present
if [ ! -f "$NDA_HOME/.env" ]; then
  cp "$SKILL_DIR/.env.example" "$NDA_HOME/.env"
  echo "  ✓ Created $NDA_HOME/.env (from .env.example)"
  echo ""
  echo "  ⚠  ACTION REQUIRED: Edit $NDA_HOME/.env to configure your settings."
  echo "     At minimum, set NDA_SKILL_REVIEWER_NAME."
else
  echo "  ✓ $NDA_HOME/.env already exists — skipping copy"
fi

# 4. Create empty playbook index if absent
INDEX="$NDA_HOME/playbook/index.json"
if [ ! -f "$INDEX" ]; then
  echo '{"clauses": [], "last_updated": null}' > "$INDEX"
  echo "  ✓ Created empty playbook index"
fi

# 5. Install Python dependencies
if [ "$NO_PIP" = false ]; then
  echo ""
  echo "▶ Installing Python dependencies..."
  PIP_CMD=""
  command -v pip3 &>/dev/null && PIP_CMD="pip3"
  command -v pip  &>/dev/null && [ -z "$PIP_CMD" ] && PIP_CMD="pip"

  if [ -z "$PIP_CMD" ]; then
    echo "  ⚠  pip not found. Install manually: pip install python-docx lxml requests"
  else
    # Try normal install first; fall back to --user for externally-managed environments (PEP 668)
    if $PIP_CMD install python-docx lxml requests --quiet 2>/dev/null; then
      echo "  ✓ Python dependencies installed"
    elif $PIP_CMD install python-docx lxml requests --user --quiet 2>/dev/null; then
      echo "  ✓ Python dependencies installed (--user)"
    else
      echo "  ⚠  pip install failed. Try one of:"
      echo "       pip install python-docx lxml requests --user"
      echo "       pip install python-docx lxml requests --break-system-packages"
      echo "       python3 -m venv ~/.nda-skill/venv && source ~/.nda-skill/venv/bin/activate && pip install python-docx lxml requests"
    fi
  fi
fi

echo ""
echo "✅ nda-review-skill installed successfully."
echo ""
echo "Next steps:"
echo "  1. Edit ~/.nda-skill/.env (set your name, notebook adapter)"
echo "  2. Run: /nda-review --learn    (build your NDA playbook)"
echo "  3. Run: /nda-review path/to/nda.docx   (review a real NDA)"
