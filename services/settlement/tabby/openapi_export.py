"""Writes this service's OpenAPI document to openapi.json (the committed contract).

    python -m tabby.openapi_export

A test fails when the committed file and the code disagree, so the file is
regenerated with this command whenever an endpoint changes.
"""

import json
from pathlib import Path

from tabby.config import Settings
from tabby.main import create_app

OPENAPI_FILE = Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    # Building the app does not touch the database; only starting it does.
    app = create_app(Settings(database_url="mssql://unused"))
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OPENAPI_FILE.write_text(render())
    print(f"wrote {OPENAPI_FILE}")
