"""Google Sheets tools for Hermes (registered via plugins/google_sheets)."""

from __future__ import annotations

from typing import Any, Dict, List

from .client import (
    GoogleSheetsAPIError,
    GoogleSheetsAuthError,
    GoogleSheetsClient,
    GoogleSheetsError,
)
from tools.registry import tool_error, tool_result


def _gsheets_client() -> GoogleSheetsClient:
    return GoogleSheetsClient()


def _gsheets_tool_error(exc: Exception) -> str:
    if isinstance(exc, GoogleSheetsAuthError):
        return tool_error(str(exc))
    if isinstance(exc, GoogleSheetsAPIError):
        return tool_error(str(exc), status_code=exc.status_code)
    return tool_error(f"Google Sheets tool failed: {type(exc).__name__}: {exc}")


def _handle_get_spreadsheet_metadata(args: dict, **kw) -> str:
    spreadsheet_id = str(args.get("spreadsheet_id") or "").strip()
    if not spreadsheet_id:
        return tool_error("spreadsheet_id is required")
    client = _gsheets_client()
    try:
        data = client.get_spreadsheet_metadata(spreadsheet_id)
        props = data.get("properties", {})
        return tool_result({
            "spreadsheet_id": props.get("spreadsheetId", spreadsheet_id),
            "title": props.get("title", ""),
            "locale": props.get("locale", ""),
            "timezone": props.get("timeZone", ""),
            "url": props.get("spreadsheetUrl", ""),
            "sheets": [
                {
                    "sheet_id": s["properties"].get("sheetId"),
                    "title": s["properties"].get("title"),
                    "sheet_type": s["properties"].get("sheetType", "GRID"),
                    "row_count": s["properties"].get("gridProperties", {}).get("rowCount"),
                    "column_count": s["properties"].get("gridProperties", {}).get("columnCount"),
                }
                for s in data.get("sheets", [])
            ],
        })
    except Exception as exc:
        return _gsheets_tool_error(exc)


def _handle_list_worksheets(args: dict, **kw) -> str:
    spreadsheet_id = str(args.get("spreadsheet_id") or "").strip()
    if not spreadsheet_id:
        return tool_error("spreadsheet_id is required")
    client = _gsheets_client()
    try:
        worksheets = client.list_worksheets(spreadsheet_id)
        return tool_result({"worksheets": worksheets})
    except Exception as exc:
        return _gsheets_tool_error(exc)


def _handle_read_range(args: dict, **kw) -> str:
    spreadsheet_id = str(args.get("spreadsheet_id") or "").strip()
    sheet_name = str(args.get("sheet_name") or "").strip()
    range_a1 = str(args.get("range_a1") or "").strip()
    if not spreadsheet_id or not range_a1:
        return tool_error("spreadsheet_id and range_a1 are required")
    client = _gsheets_client()
    try:
        data = client.read_range(spreadsheet_id, sheet_name, range_a1)
        return tool_result({
            "range": data.get("range", ""),
            "values": data.get("values", []),
        })
    except Exception as exc:
        return _gsheets_tool_error(exc)


def _handle_search_rows(args: dict, **kw) -> str:
    spreadsheet_id = str(args.get("spreadsheet_id") or "").strip()
    sheet_name = str(args.get("sheet_name") or "").strip()
    filter_spec = args.get("filter_spec", {})
    if not isinstance(filter_spec, dict):
        return tool_error("filter_spec must be an object")
    if not spreadsheet_id:
        return tool_error("spreadsheet_id is required")
    client = _gsheets_client()
    try:
        results = client.search_rows(spreadsheet_id, sheet_name, filter_spec)
        return tool_result({"results": results, "count": len(results)})
    except Exception as exc:
        return _gsheets_tool_error(exc)


def _validate_values(values: Any, label: str = "values") -> List[List[Any]]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list")
    for i, row in enumerate(values):
        if not isinstance(row, list):
            raise ValueError(f"{label}[{i}] must be a list of cell values")
    return values


def _handle_update_cells(args: dict, **kw) -> str:
    spreadsheet_id = str(args.get("spreadsheet_id") or "").strip()
    sheet_name = str(args.get("sheet_name") or "").strip()
    range_a1 = str(args.get("range_a1") or "").strip()
    values_raw = args.get("values")

    if not spreadsheet_id or not range_a1 or values_raw is None:
        return tool_error("spreadsheet_id, range_a1, and values are required")
    try:
        values = _validate_values(values_raw)
    except ValueError as e:
        return tool_error(str(e))
    if not values:
        return tool_error("values must be a non-empty list of rows")

    client = _gsheets_client()
    try:
        result = client.update_cells(spreadsheet_id, sheet_name, range_a1, values)
        return tool_result({
            "success": True,
            "updated_cells": result.get("updatedCells", 0),
            "updated_range": result.get("updatedRange", ""),
            "updated_rows": result.get("updatedRows", 0),
            "updated_columns": result.get("updatedColumns", 0),
        })
    except Exception as exc:
        return _gsheets_tool_error(exc)


def _handle_add_worksheet(args: dict, **kw) -> str:
    spreadsheet_id = str(args.get("spreadsheet_id") or "").strip()
    title = str(args.get("title") or "").strip()
    if not spreadsheet_id:
        return tool_error("spreadsheet_id is required")
    if not title:
        return tool_error("title is required")
    client = _gsheets_client()
    try:
        sheet = client.add_worksheet(
            spreadsheet_id,
            title,
            index=args.get("index"),
            grid_rows=args.get("grid_rows", 1000),
            grid_columns=args.get("grid_columns", 26),
        )
        return tool_result({
            "success": True,
            "sheet": sheet,
        })
    except Exception as exc:
        return _gsheets_tool_error(exc)


def _handle_append_row(args: dict, **kw) -> str:
    spreadsheet_id = str(args.get("spreadsheet_id") or "").strip()
    sheet_name = str(args.get("sheet_name") or "").strip()
    values_raw = args.get("values")

    if not spreadsheet_id or values_raw is None:
        return tool_error("spreadsheet_id and values are required")
    if not isinstance(values_raw, list):
        return tool_error("values must be a list of cell values")

    if values_raw and isinstance(values_raw[0], list):
        values = values_raw[0]
    else:
        values = values_raw

    client = _gsheets_client()
    try:
        result = client.append_row(spreadsheet_id, sheet_name, values)
        return tool_result({
            "success": True,
            "updated_range": result.get("updates", {}).get("updatedRange", ""),
            "updated_cells": result.get("updates", {}).get("updatedCells", 0),
        })
    except Exception as exc:
        return _gsheets_tool_error(exc)


def _handle_batch_update(args: dict, **kw) -> str:
    spreadsheet_id = str(args.get("spreadsheet_id") or "").strip()
    sheet_name = str(args.get("sheet_name") or "").strip()
    operations = args.get("operations")

    if not spreadsheet_id or not operations:
        return tool_error("spreadsheet_id and operations are required")
    if not isinstance(operations, list) or not operations:
        return tool_error("operations must be a non-empty list")

    client = _gsheets_client()
    try:
        result = client.batch_update(spreadsheet_id, sheet_name, operations)
        return tool_result({
            "success": True,
            "responses": result.get("replies", []),
            "spreadsheet_id": result.get("spreadsheetId", spreadsheet_id),
        })
    except Exception as exc:
        return _gsheets_tool_error(exc)


COMMON_STRING = {"type": "string"}
SPREADSHEET_ID = {
    "type": "string",
    "description": "The ID from the spreadsheet URL (e.g., '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms')",
}
SHEET_NAME = {
    "type": "string",
    "description": "The name of the worksheet/sheet tab (e.g., 'Sheet1'). Optional if the sheet name is embedded in the range.",
}
RANGE_A1 = {
    "type": "string",
    "description": "A1 notation range (e.g., 'A1:C10' or 'A:A' for a full column)",
}

GET_SPREADSHEET_METADATA_SCHEMA = {
    "name": "get_spreadsheet_metadata",
    "description": "Get metadata about a Google Spreadsheet including title, locale, timezone, and all worksheet info.",
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": SPREADSHEET_ID,
        },
        "required": ["spreadsheet_id"],
    },
}

LIST_WORKSHEETS_SCHEMA = {
    "name": "list_worksheets",
    "description": "List all worksheets (tabs/sheets) in a Google Spreadsheet with their IDs, types, row counts, and column counts.",
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": SPREADSHEET_ID,
        },
        "required": ["spreadsheet_id"],
    },
}

READ_RANGE_SCHEMA = {
    "name": "read_range",
    "description": "Read cell values from a specified range in a Google Sheet. Returns a 2D array of values.",
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": SPREADSHEET_ID,
            "sheet_name": SHEET_NAME,
            "range_a1": RANGE_A1,
        },
        "required": ["spreadsheet_id", "range_a1"],
    },
}

SEARCH_ROWS_SCHEMA = {
    "name": "search_rows",
    "description": "Search for rows matching a filter spec in a Google Sheet. Filters are applied client-side after reading the sheet data.",
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": SPREADSHEET_ID,
            "sheet_name": SHEET_NAME,
            "filter_spec": {
                "type": "object",
                "description": "Filter specification with optional query, column_index, range, and case_sensitive fields",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text to search for in cells (substring match, case-insensitive by default)",
                    },
                    "column_index": {
                        "type": "integer",
                        "description": "0-based column index to restrict search to; omit to search all columns",
                    },
                    "range": {
                        "type": "string",
                        "description": "A1 range to search within (default: 'A:ZZ')",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search should be case-sensitive (default: false)",
                    },
                },
            },
        },
        "required": ["spreadsheet_id"],
    },
}

UPDATE_CELLS_SCHEMA = {
    "name": "update_cells",
    "description": "Update cell values in a Google Sheet at a specified range. Provide a 2D array of values matching the target dimensions.",
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": SPREADSHEET_ID,
            "sheet_name": SHEET_NAME,
            "range_a1": RANGE_A1,
            "values": {
                "type": "array",
                "description": "2D array of cell values. Each inner array is a row. Example: [['Name', 'Age'], ['Alice', 30]]",
                "items": {
                    "type": "array",
                    "items": {},
                },
            },
        },
        "required": ["spreadsheet_id", "range_a1", "values"],
    },
}

APPEND_ROW_SCHEMA = {
    "name": "append_row",
    "description": "Append a new row of values to the end of a Google Sheet. Values should be a flat list of cell values for one row.",
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": SPREADSHEET_ID,
            "sheet_name": SHEET_NAME,
            "values": {
                "type": "array",
                "description": "Flat list of cell values for the new row. Example: ['Alice', 30, 'Engineer']",
                "items": {},
            },
        },
        "required": ["spreadsheet_id", "values"],
    },
}

ADD_WORKSHEET_SCHEMA = {
    "name": "add_worksheet",
    "description": "Create a brand-new worksheet (tab/sheet) in a Google Spreadsheet. Requires service account auth (API key is read-only).",
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": SPREADSHEET_ID,
            "title": {
                "type": "string",
                "description": "Title for the new worksheet tab.",
            },
            "index": {
                "type": "integer",
                "description": "0-based position to insert the sheet; omitted = last position.",
            },
            "grid_rows": {
                "type": "integer",
                "description": "Number of rows for the new sheet (default: 1000).",
            },
            "grid_columns": {
                "type": "integer",
                "description": "Number of columns for the new sheet (default: 26).",
            },
        },
        "required": ["spreadsheet_id", "title"],
    },
}

BATCH_UPDATE_SCHEMA = {
    "name": "batch_update",
    "description": "Execute multiple sheet operations in a single API call for efficiency. Supports: update_cells, append_cells, delete_rows, insert_rows, update_sheet_properties, add_sheet.",
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": SPREADSHEET_ID,
            "sheet_name": SHEET_NAME,
            "operations": {
                "type": "array",
                "description": "List of operations to perform. Each operation has a 'type' field and type-specific parameters.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["update_cells", "append_cells", "delete_rows", "insert_rows", "update_sheet_properties", "add_sheet"],
                        },
                        "sheet_id": {"type": "integer", "description": "Sheet ID (from list_worksheets) - defaults to 0"},
                        "range": {"type": "string", "description": "A1 range for update_cells"},
                        "cell_value": {"type": "object", "description": "Cell value for repeatCell operations"},
                        "start_row": {"type": "integer"},
                        "end_row": {"type": "integer"},
                        "start_col": {"type": "integer"},
                        "end_col": {"type": "integer"},
                        "rows": {"type": "array", "description": "Rows of cell values for append_cells"},
                        "start_index": {"type": "integer", "description": "Start index for delete_rows/insert_rows"},
                        "end_index": {"type": "integer", "description": "End index for delete_rows/insert_rows"},
                        "inherit_before": {"type": "boolean", "description": "For insert_rows: whether new row inherits properties from the row before"},
                        "title": {"type": "string", "description": "New title for update_sheet_properties / add_sheet"},
                        "grid_rows": {"type": "integer", "description": "Row count for add_sheet (default: 1000)"},
                        "grid_columns": {"type": "integer", "description": "Column count for add_sheet (default: 26)"},
                        "index": {"type": "integer", "description": "0-based position for add_sheet"},
                    },
                    "required": ["type"],
                },
            },
        },
        "required": ["spreadsheet_id", "operations"],
    },
}
