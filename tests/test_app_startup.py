"""Startup behaviour the container contract relies on (§7), without HTTP."""

from contextlib import closing

from tabby.config import Settings
from tabby.db import connect
from tabby.main import create_app


def test_app_boots_twice_on_the_same_data_dir_without_duplicating_seed(tmp_path):
    settings = Settings(port=8000, data_dir=tmp_path / "data")

    create_app(settings)  # first boot: empty directory
    app = create_app(settings)  # restart on the same volume

    with closing(connect(settings.db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 9
    paths = set(app.openapi()["paths"])
    assert {"/api/signup", "/api/groups", "/api/groups/{group_id}/settlement"} <= paths
