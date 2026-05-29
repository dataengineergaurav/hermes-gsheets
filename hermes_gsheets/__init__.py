"""Google Sheets integration plugin — user-installed.

Registers 8 tools into the ``google_sheets`` toolset.
"""

from __future__ import annotations

from .tools import (
    ADD_WORKSHEET_SCHEMA,
    APPEND_ROW_SCHEMA,
    BATCH_UPDATE_SCHEMA,
    GET_SPREADSHEET_METADATA_SCHEMA,
    LIST_WORKSHEETS_SCHEMA,
    READ_RANGE_SCHEMA,
    SEARCH_ROWS_SCHEMA,
    UPDATE_CELLS_SCHEMA,
    _handle_add_worksheet,
    _handle_append_row,
    _handle_batch_update,
    _handle_get_spreadsheet_metadata,
    _handle_list_worksheets,
    _handle_read_range,
    _handle_search_rows,
    _handle_update_cells,
)

_TOOLS = (
    ("get_spreadsheet_metadata", GET_SPREADSHEET_METADATA_SCHEMA, _handle_get_spreadsheet_metadata, "📊"),
    ("list_worksheets",          LIST_WORKSHEETS_SCHEMA,          _handle_list_worksheets,          "📋"),
    ("read_range",               READ_RANGE_SCHEMA,               _handle_read_range,               "📖"),
    ("search_rows",              SEARCH_ROWS_SCHEMA,              _handle_search_rows,              "🔍"),
    ("add_worksheet",            ADD_WORKSHEET_SCHEMA,            _handle_add_worksheet,            "🆕"),
    ("update_cells",             UPDATE_CELLS_SCHEMA,             _handle_update_cells,             "✏️"),
    ("append_row",               APPEND_ROW_SCHEMA,               _handle_append_row,               "➕"),
    ("batch_update",             BATCH_UPDATE_SCHEMA,              _handle_batch_update,              "⚡"),
)


def register(ctx) -> None:
    """Register all Google Sheets tools. Called once by the plugin loader."""
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="google_sheets",
            schema=schema,
            handler=handler,
            emoji=emoji,
        )
