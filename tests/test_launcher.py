"""Launcher: an outdated running server is detected by its code version and replaced; demo photo sync."""
import threading

from werkzeug.serving import make_server

from app import __main__ as launcher
from app.fakes import placeholder_image
from app.server import create_app
from app.version import code_version
from tests.make_demo import sync_photos


def test_code_version_changes_with_code(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "notes.txt").write_text("ignored")
    v1 = code_version(tmp_path)
    (tmp_path / "notes.txt").write_text("still ignored")
    assert code_version(tmp_path) == v1
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "app.js").write_text("// new")
    assert code_version(tmp_path) != v1


def test_outdated_server_is_replaced(studio):
    app = create_app(studio)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    app.stop_server = server.shutdown
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    info = launcher.running_server(url)
    assert info and info["version"] == code_version()
    assert launcher.replace_server(url, info)
    thread.join(5)
    assert not thread.is_alive() and launcher.running_server(url) is None


def test_busy_server_is_kept(studio):
    app = create_app(studio)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    app.stop_server = server.shutdown
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    gate = threading.Event()
    studio.tasks.start("gen:all", "X", "busy", lambda task: gate.wait(10))
    try:
        assert not launcher.replace_server(url, launcher.running_server(url))
        assert launcher.running_server(url)
    finally:
        gate.set()
        server.shutdown()


def test_demo_gets_new_reference_photos(tmp_path):
    src, dst = tmp_path / "real", tmp_path / "demo"
    placeholder_image(src / "Style" / "a.png", "a")
    dst.mkdir()
    assert sync_photos(src, dst) == 1 and (dst / "Style" / "a.png").exists()
    assert sync_photos(src, dst) == 0  # unchanged files are not copied again
    placeholder_image(src / "Style" / "Sub" / "b.png", "b")
    assert sync_photos(src, dst) == 1 and (dst / "Style" / "Sub" / "b.png").exists()
