"""Thin Google Sheets v4 API client used by Hermes google_sheets tools.

Supports two auth modes:
1. Service account (GOOGLE_SHEETS_CREDENTIALS) — full read/write
2. API key (GOOGLE_SHEETS_API_KEY) — read-only, public sheets only
"""

from __future__ import annotations

import json
import os
import time
import base64
from typing import Any, Dict, List, Optional

import httpx


class GoogleSheetsError(RuntimeError):
    """Base Google Sheets tool error."""


class GoogleSheetsAuthError(GoogleSheetsError):
    """Raised when credentials are missing or invalid."""


class GoogleSheetsAPIError(GoogleSheetsError):
    """Structured Google Sheets API failure."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleSheetsClient:
    def __init__(self) -> None:
        creds = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "").strip()
        api_key = os.getenv("GOOGLE_SHEETS_API_KEY", "").strip()

        self._api_key = api_key or None
        self._creds = None
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

        if creds:
            if creds.startswith("{"):
                self._creds = json.loads(creds)
            else:
                path = os.path.expanduser(creds)
                if not os.path.isfile(path):
                    raise GoogleSheetsAuthError(
                        f"GOOGLE_SHEETS_CREDENTIALS points to '{path}' but file does not exist."
                    )
                with open(path) as f:
                    self._creds = json.loads(f.read())
        elif not api_key:
            raise GoogleSheetsAuthError(
                "Set GOOGLE_SHEETS_CREDENTIALS (service account JSON) or "
                "GOOGLE_SHEETS_API_KEY for the Google Sheets plugin."
            )

    def _ensure_token(self) -> Optional[str]:
        if self._api_key:
            return None
        if not self._creds:
            return None

        now = time.time()
        if self._access_token and now < self._token_expiry - 60:
            return self._access_token

        private_key = self._creds.get("private_key", "")
        client_email = self._creds.get("client_email", "")
        token_uri = self._creds.get("token_uri", "https://oauth2.googleapis.com/token")

        if not private_key or not client_email:
            raise GoogleSheetsAuthError(
                "Service account JSON is missing 'private_key' or 'client_email'."
            )

        now_ts = int(now)
        jwt_payload = {
            "iss": client_email,
            "scope": " ".join(_SCOPES),
            "aud": token_uri,
            "iat": now_ts,
            "exp": now_ts + 3600,
        }
        header = {"alg": "RS256", "typ": "JWT"}

        def b64encode(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        body = b64encode(json.dumps(header).encode()) + "." + b64encode(json.dumps(jwt_payload).encode())

        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend

        key_bytes = private_key.encode()
        if "-----BEGIN PRIVATE KEY-----" not in private_key:
            key_bytes = (
                "-----BEGIN PRIVATE KEY-----\n" + private_key + "\n-----END PRIVATE KEY-----"
            ).encode()

        private_key_obj = serialization.load_pem_private_key(
            key_bytes, password=None, backend=default_backend()
        )
        signature = private_key_obj.sign(body.encode(), padding.PKCS1v15(), hashes.SHA256())
        jwt = body + "." + b64encode(signature)

        resp = httpx.post(
            token_uri,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt},
            timeout=30,
        )
        if resp.status_code != 200:
            raise GoogleSheetsAuthError(
                f"Failed to obtain access token: {resp.status_code} {resp.text}"
            )
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = now_ts + data.get("expires_in", 3600)
        return self._access_token

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
    ) -> Any:
        query_params = dict(params or {})
        headers = {"Content-Type": "application/json"}

        token = self._ensure_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif self._api_key:
            query_params["key"] = self._api_key

        url = f"{_API_BASE}{path}"
        resp = httpx.request(
            method,
            url,
            headers=headers,
            params=query_params,
            json=json_body,
            timeout=30,
        )
        if resp.status_code >= 400:
            detail = resp.text.strip()
            try:
                payload = resp.json()
                if isinstance(payload, dict):
                    err = payload.get("error", {})
                    if isinstance(err, dict):
                        detail = err.get("message", detail)
                    elif isinstance(err, str):
                        detail = err
            except Exception:
                pass
            raise GoogleSheetsAPIError(
                detail, status_code=resp.status_code, response_body=resp.text
            )
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def get_spreadsheet_metadata(self, spreadsheet_id: str) -> dict:
        return self._request("GET", f"/{spreadsheet_id}")

    def add_worksheet(
        self,
        spreadsheet_id: str,
        title: str,
        *,
        index: int | None = None,
        grid_rows: int = 1000,
        grid_columns: int = 26,
    ) -> dict:
        payload = {
            "addSheet": {
                "properties": {
                    "title": title,
                    "gridProperties": {
                        "rowCount": grid_rows,
                        "columnCount": grid_columns,
                    },
                },
            },
        }
        if index is not None:
            payload["addSheet"]["properties"]["index"] = index
        result = self._request(
            "POST",
            f"/{spreadsheet_id}:batchUpdate",
            json_body={"requests": [payload]},
        )
        props = result["replies"][0]["addSheet"]["properties"]
        return {
            "sheet_id": props.get("sheetId"),
            "title": props.get("title"),
            "index": props.get("index"),
            "sheet_type": props.get("sheetType", "GRID"),
            "grid_rows": props.get("gridProperties", {}).get("rowCount"),
            "grid_columns": props.get("gridProperties", {}).get("columnCount"),
        }

    def list_worksheets(self, spreadsheet_id: str) -> list:
        data = self._request("GET", f"/{spreadsheet_id}")
        sheets = data.get("sheets", [])
        return [
            {
                "sheet_id": s["properties"].get("sheetId"),
                "title": s["properties"].get("title"),
                "index": s["properties"].get("index"),
                "sheet_type": s["properties"].get("sheetType", "GRID"),
                "grid_rows": s["properties"].get("gridProperties", {}).get("rowCount"),
                "grid_columns": s["properties"].get("gridProperties", {}).get("columnCount"),
            }
            for s in sheets
        ]

    def read_range(self, spreadsheet_id: str, sheet_name: str, range_a1: str) -> dict:
        full_range = f"'{sheet_name}'!{range_a1}" if sheet_name else range_a1
        return self._request("GET", f"/{spreadsheet_id}/values/{full_range}")

    def search_rows(
        self, spreadsheet_id: str, sheet_name: str, filter_spec: dict
    ) -> list:
        raw = self.read_range(
            spreadsheet_id, sheet_name, filter_spec.get("range", "A:ZZ")
        )
        values = raw.get("values", [])
        query = str(filter_spec.get("query", "")).strip().lower()
        column_index = filter_spec.get("column_index")
        case_sensitive = filter_spec.get("case_sensitive", False)

        if not values:
            return []

        if column_index is not None:
            if query:
                results = []
                for i, row in enumerate(values):
                    cell = str(row[column_index]) if column_index < len(row) else ""
                    if not case_sensitive:
                        cell = cell.lower()
                    if query in cell:
                        results.append({"row": i + 1, "data": row})
                return results
            return [{"row": i + 1, "data": row} for i, row in enumerate(values)]

        if query:
            results = []
            for i, row in enumerate(values):
                for cell in row:
                    cell_str = str(cell)
                    if not case_sensitive:
                        cell_str = cell_str.lower()
                    if query in cell_str:
                        results.append({"row": i + 1, "data": row})
                        break
            return results
        return [{"row": i + 1, "data": row} for i, row in enumerate(values)]

    def update_cells(
        self, spreadsheet_id: str, sheet_name: str, range_a1: str, values: List[List[Any]]
    ) -> dict:
        full_range = f"'{sheet_name}'!{range_a1}" if sheet_name else range_a1
        return self._request(
            "PUT",
            f"/{spreadsheet_id}/values/{full_range}",
            json_body={"values": values},
            params={"valueInputOption": "USER_ENTERED"},
        )

    def append_row(
        self, spreadsheet_id: str, sheet_name: str, values: List[Any]
    ) -> dict:
        full_range = f"'{sheet_name}'!A:Z" if sheet_name else "A:Z"
        return self._request(
            "POST",
            f"/{spreadsheet_id}/values/{full_range}:append",
            json_body={"values": [values]},
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
        )

    def batch_update(
        self, spreadsheet_id: str, sheet_name: str, operations: List[Dict[str, Any]]
    ) -> dict:
        requests = []
        for op in operations:
            op_type = op.get("type", "").lower()
            if op_type == "update_cells":
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": op.get("sheet_id", 0),
                            "startRowIndex": op.get("start_row"),
                            "endRowIndex": op.get("end_row"),
                            "startColumnIndex": op.get("start_col"),
                            "endColumnIndex": op.get("end_col"),
                        },
                        "cell": {
                            "userEnteredValue": op.get("cell_value", {})
                        },
                        "fields": "userEnteredValue",
                    }
                })
            elif op_type == "append_cells":
                requests.append({
                    "appendCells": {
                        "sheetId": op.get("sheet_id", 0),
                        "rows": [{"values": [{"userEnteredValue": v} for v in row]} for row in op.get("rows", [])],
                        "fields": "userEnteredValue",
                    }
                })
            elif op_type == "delete_rows":
                requests.append({
                    "deleteDimension": {
                        "range": {
                            "sheetId": op.get("sheet_id", 0),
                            "dimension": "ROWS",
                            "startIndex": op.get("start_index", 0),
                            "endIndex": op.get("end_index", 1),
                        }
                    }
                })
            elif op_type == "insert_rows":
                requests.append({
                    "insertDimension": {
                        "range": {
                            "sheetId": op.get("sheet_id", 0),
                            "dimension": "ROWS",
                            "startIndex": op.get("start_index", 0),
                            "endIndex": op.get("end_index", 1),
                        },
                        "inheritBefore": op.get("inherit_before", False),
                    }
                })
            elif op_type == "update_sheet_properties":
                requests.append({
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": op.get("sheet_id", 0),
                            "title": op.get("title"),
                        },
                        "fields": "title",
                    }
                })
            elif op_type == "add_sheet":
                props = {
                    "title": op.get("title", "New Sheet"),
                    "gridProperties": {
                        "rowCount": op.get("grid_rows", 1000),
                        "columnCount": op.get("grid_columns", 26),
                    },
                }
                if op.get("index") is not None:
                    props["index"] = op["index"]
                if op.get("sheet_id") is not None:
                    props["sheetId"] = op["sheet_id"]
                requests.append({"addSheet": {"properties": props}})
        return self._request(
            "POST",
            f"/{spreadsheet_id}:batchUpdate",
            json_body={"requests": requests},
        )
