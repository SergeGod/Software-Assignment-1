"""Runtime settings, read only from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

# Always bind every interface so the app is reachable from outside a container.
HOST = "0.0.0.0"
DEFAULT_PORT = 8000
# Next to the source when run locally; the container sets DATA_DIR=/data.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_FILENAME = "tabby.db"


@dataclass(frozen=True)
class Settings:
    port: int
    data_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / DB_FILENAME


def load_settings() -> Settings:
    return Settings(
        port=int(os.environ.get("PORT", DEFAULT_PORT)),
        data_dir=Path(os.environ.get("DATA_DIR", DEFAULT_DATA_DIR)),
    )
