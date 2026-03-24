# Notebook Integrations

The `nda-review-skill` can sync your local playbook to four notebook adapters.
Configure your preferred adapter in `~/.nda-skill/.env`.

---

## Choosing an Adapter

| Adapter | Best for | Requires |
|---------|---------|---------|
| `markdown` | Any Markdown editor (Obsidian, iA Writer, VS Code) | Nothing — built-in |
| `obsidian` | Obsidian power users with Local REST API | Community plugin |
| `notion` | Teams sharing a Notion workspace | Notion internal integration |
| `apple_notes` | macOS users wanting native sync | macOS only |

Set your choice in `~/.nda-skill/.env`:
```bash
NOTEBOOK_ADAPTER=markdown  # or obsidian | notion | apple_notes
```

---

## Adapter 1: Markdown Folder

The simplest adapter — copies playbook `.md` files to any local folder.
Works with Obsidian, iA Writer, VS Code, Typora, and any other Markdown editor.

### Config

```bash
NOTEBOOK_ADAPTER=markdown
NOTEBOOK_MARKDOWN_PATH=~/Documents/Legal/NDA Playbook
```

### How it works
- Creates the target directory if it doesn't exist
- Copies all files from `~/.nda-skill/playbook/` preserving the sub-folder structure
- Safe to run multiple times — overwrites with the latest version

### Usage
```
/nda-review --sync
```

---

## Adapter 2: Obsidian

Syncs directly to an Obsidian vault via the
[Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) community plugin.

### Setup

1. Open Obsidian → Settings → Community Plugins → Browse
2. Search for "Local REST API" → Install → Enable
3. In the plugin settings, note your API key
4. Add to `~/.nda-skill/.env`:

```bash
NOTEBOOK_ADAPTER=obsidian
OBSIDIAN_API_URL=https://127.0.0.1:27124
OBSIDIAN_API_KEY=<your-key-from-plugin-settings>
OBSIDIAN_VAULT_PATH=Legal/NDA Playbook
OBSIDIAN_VERIFY_SSL=false
```

> **Note on SSL:** Obsidian's Local REST API uses a self-signed certificate for localhost.
> Set `OBSIDIAN_VERIFY_SSL=false` only for this local connection — it does not affect
> any external HTTPS connections.

### How it works
- Sends a `PUT /vault/{path}` request for each clause file
- Creates files (and intermediate folders) in your vault automatically
- Safe to re-run — updates existing files

### Prerequisites
- Obsidian must be running when you sync
- The REST API plugin must be enabled

### Usage
```
/nda-review --sync
```

---

## Adapter 3: Notion

Creates pages in a Notion database, one page per clause position.

### Setup

#### 1. Create a Notion integration
1. Go to https://www.notion.so/my-integrations
2. Click "New integration" → give it a name (e.g., "NDA Playbook Sync")
3. Select the workspace where your database lives
4. Copy the **Internal Integration Secret** (starts with `ntn_` or `secret_`)

#### 2. Create or identify your database
Your database should have these properties:

| Property name | Type |
|---------------|------|
| Name | Title |
| Document Type | Select |
| Priority | Select |
| Clause Category | Select |
| Standard Position | Rich text |
| Acceptable Fallback | Rich text |
| Walk-Away / Red Line | Rich text |
| Notes | Rich text |

#### 3. Share the database with your integration
Open the database in Notion → click "..." → Connections → Add connection → select your integration

#### 4. Get the database ID
Open the database in Notion browser. The URL looks like:
`https://www.notion.so/MyDatabase-XXXXXXXXXXXXXXXXXXXXXXXXXXXXX`
The database ID is the 32-character hex string at the end (with or without hyphens).

#### 5. Add to .env

```bash
NOTEBOOK_ADAPTER=notion
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### How it works
- Creates one new page per clause file (does not update existing pages in this version)
- Maps frontmatter fields to Notion properties
- Truncates text to 2000 characters per field (Notion API limit for rich text)

### Usage
```
/nda-review --sync
```

---

## Adapter 4: Apple Notes

Creates notes in Apple Notes via AppleScript. macOS only.

### Setup

No credentials required. Optionally configure the target folder:

```bash
NOTEBOOK_ADAPTER=apple_notes
APPLE_NOTES_FOLDER=NDA Playbook
```

The folder will be created in your iCloud account if it doesn't exist.

### How it works
- Uses `osascript` to call the Notes app
- Creates one note per clause file in the configured folder
- Note title = clause name; note body = full Markdown content

### Limitations
- macOS only
- Creates new notes on each sync (does not update existing notes)
- Apple Notes may strip some Markdown formatting
- Large playbooks (50+ notes) may be slow due to AppleScript overhead

### Usage
```
/nda-review --sync
```

---

## Running Sync Manually

You can also run the sync script directly:

```bash
# Use adapter from .env
python3 ~/.nda-skill/scripts/notebook_sync.py

# Override adapter
python3 ~/.nda-skill/scripts/notebook_sync.py --adapter obsidian

# Use a different playbook directory
python3 ~/.nda-skill/scripts/notebook_sync.py --playbook-dir ~/my-other-playbook
```

---

## Troubleshooting

### Markdown: "No such file or directory"
Check that `NOTEBOOK_MARKDOWN_PATH` is set and the parent directory exists:
```bash
mkdir -p "$(python3 -c "import os; print(os.path.expanduser('~/Documents/Legal'))")"
```

### Obsidian: HTTP 401
The API key is wrong or not set. Check `OBSIDIAN_API_KEY` in `.env` matches
the key shown in the Local REST API plugin settings.

### Obsidian: Connection refused
Obsidian must be running. The plugin only serves requests while Obsidian is open.

### Notion: HTTP 404
The database ID is wrong, or the integration hasn't been given access to the database.
Share the database with your integration via the Notion UI (... → Connections).

### Notion: HTTP 400 "is not a property that exists"
Your database is missing one of the expected property names.
Check the property names in your database match exactly (case-sensitive).

### Apple Notes: AppleScript error
Make sure Notes.app is allowed to be controlled by Script Editor / Terminal:
System Preferences → Privacy & Security → Automation → allow Terminal to control Notes.
