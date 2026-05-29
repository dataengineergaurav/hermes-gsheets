# hermes-gsheets

Google Sheets plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Read/write spreadsheet metadata, worksheet lists, cell ranges, search rows,
create worksheets, append rows, and execute batch updates.

## Install

### From PyPI

```bash
pip install hermes-gsheets
```

Hermes auto-discovers the plugin on next start via the `hermes_agent.plugins`
entry point.

### From GitHub

```bash
hermes plugins install dataengineergaurav/hermes-gsheets
```

## Enable

```bash
hermes plugins enable google_sheets
```

## Setup

Set one of these environment variables (in `~/.hermes/.env` or your shell):

### Service account (full read/write)

```bash
GOOGLE_SHEETS_CREDENTIALS=/path/to/service-account-key.json
```

Or paste the JSON inline:

```bash
GOOGLE_SHEETS_CREDENTIALS='{"type": "service_account", ...}'
```

### API key (read-only, public sheets only)

```bash
GOOGLE_SHEETS_API_KEY=AIza...
```

## Tools

| Tool | Description |
|------|-------------|
| `get_spreadsheet_metadata` | Title, locale, timezone, URL + all worksheet details |
| `list_worksheets` | Sheet IDs, types, row/column counts |
| `read_range` | Read cell values as 2D array from an A1 range |
| `search_rows` | Client-side substring search across rows |
| `add_worksheet` | Create a brand-new worksheet tab (requires service account) |
| `update_cells` | Write values to a specified range |
| `append_row` | Append a single row of values |
| `batch_update` | Multiple operations (update, append, delete/insert rows, rename sheets, add sheets) in one API call |

## Platform access

To make `google_sheets` available on Telegram (or other gateway platforms), add
it to your `config.yaml`:

```yaml
platform_toolsets:
  telegram:
    - google_sheets
  cli:
    - google_sheets
```

## License

MIT
