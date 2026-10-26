import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[6]
    / "internal/core/skills/catalog/screenshot/scripts/take_screenshot.py"
)
_spec = importlib.util.spec_from_file_location("take_screenshot", SCRIPT_PATH)
take_screenshot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(take_screenshot)


@pytest.mark.parametrize(
    "app",
    [
        "TextEdit",
        'App "quoted"',
        "App \\\\ with backslashes",
        'App \\\" quote parity',
        "应用程序",
        "App\nName",
    ],
)
def test_activate_app_passes_application_name_as_an_argument(monkeypatch, app):
    calls = []
    monkeypatch.setattr(
        take_screenshot.subprocess,
        "run",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )

    take_screenshot.activate_app(app)

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0:2] == ["osascript", "-e"]
    assert "tell application (item 1 of argv) to activate" in args[2]
    assert app not in args[2]
    assert args[3] == app
    assert kwargs == {"check": False, "capture_output": True, "text": True}


@pytest.mark.skipif(sys.platform != "darwin", reason="AppleScript is available only on macOS")
@pytest.mark.parametrize("app", ['TextEdit "quoted"', "App \\\\ with backslashes", "应用程序"])
def test_macos_osascript_receives_app_name_without_string_interpolation(app):
    captured = []
    original_run = take_screenshot.subprocess.run

    def capture_run(args, **kwargs):
        captured.append((args, kwargs))
        return None

    take_screenshot.subprocess.run = capture_run
    try:
        take_screenshot.activate_app(app)
    finally:
        take_screenshot.subprocess.run = original_run

    activation_script = captured[0][0][2]
    harmless_script = activation_script.replace(
        "tell application (item 1 of argv) to activate",
        "return item 1 of argv",
    )
    result = subprocess.run(
        ["osascript", "-e", harmless_script, app],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.rstrip("\n") == app
