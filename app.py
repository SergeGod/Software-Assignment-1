"""Entry point: `python app.py` starts Tabby as a single process."""

import uvicorn

from tabby.config import HOST, load_settings
from tabby.main import create_app

if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(create_app(settings), host=HOST, port=settings.port)
