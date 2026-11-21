"""Entry point: `python app.py` starts the settlement service."""

import uvicorn

from tabby.config import HOST, load_settings
from tabby.main import create_app
from tabby.observability import setup_logging

if __name__ == "__main__":
    setup_logging()
    settings = load_settings()
    # access_log is off because tabby.observability logs one line per request itself.
    uvicorn.run(create_app(settings), host=HOST, port=settings.port, access_log=False)
