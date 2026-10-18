import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.fakes import FakeAssistant, FakeImageBackend  # noqa: E402
from app.paths import Project  # noqa: E402
from app.server import create_app  # noqa: E402
from app.service import Studio  # noqa: E402
from tests.make_demo import build_catalog, build_synthetic  # noqa: E402

GOLDEN = Path(__file__).parent / "golden"
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"


@pytest.fixture
def proj(tmp_path) -> Project:
    build_synthetic(tmp_path)
    p = Project(tmp_path)
    p.ensure()
    return p


@pytest.fixture
def downloads(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("downloads")


@pytest.fixture
def catalog_dir(tmp_path_factory) -> Path:
    return build_catalog(tmp_path_factory.mktemp("catalog"))


@pytest.fixture
def studio(proj, downloads, catalog_dir):
    opened = []
    s = Studio(proj, FakeAssistant(), FakeImageBackend(), opener=opened.append, echo=False)
    s.save_settings({"downloads_dir": str(downloads), "qa_enabled": True, "max_auto_retries": 1,
                     "catalog_dir": str(catalog_dir)})
    s.opened = opened
    return s


@pytest.fixture
def flask_app(studio):
    app = create_app(studio)
    app.testing = True
    return app


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


def golden_text(name: str, actual: str) -> None:
    """Compare text with tests/golden/<name>; UPDATE_GOLDEN=1 rewrites the baseline."""
    path = GOLDEN / name
    if UPDATE or not path.exists():  # first run (or deliberate update) establishes the baseline
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8", newline="\n")
        return
    assert actual == path.read_text(encoding="utf-8"), f"Regression in {name} (set UPDATE_GOLDEN=1 if intended)"
