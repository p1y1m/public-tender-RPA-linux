"""Classic desktop RPA for inspecting the downloaded public tender CSV.

The browser automation in ``main.py`` produces the CSV. This module uses
PyAutoGUI to visibly drive LibreOffice Calc with mouse and keyboard events.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any

from PIL import ImageGrab


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output"
DEFAULT_SCREENSHOT = DEFAULT_OUTPUT_DIR / "desktop_rpa.png"


def log(message: str) -> None:
    print(message, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Visibly open and search a downloaded Mercado Público CSV in "
            "LibreOffice Calc using PyAutoGUI."
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="CSV to open (default: newest CSV in output/).",
    )
    parser.add_argument(
        "--search-text",
        default="software",
        help="Text to find in Calc after opening the CSV (default: software).",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=DEFAULT_SCREENSHOT,
        help="Path for a screenshot after interaction.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=45,
        help="Seconds to wait for LibreOffice and its dialogs.",
    )
    parser.add_argument(
        "--step-pause",
        type=float,
        default=0.25,
        help="Pause after each PyAutoGUI action so movement remains visible.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Leave Calc open after the interaction instead of closing it.",
    )
    return parser.parse_args()


def resolve_csv(requested_path: Path | None) -> Path:
    if requested_path is not None:
        csv_path = requested_path.expanduser().resolve()
    else:
        candidates = sorted(
            DEFAULT_OUTPUT_DIR.glob("*.csv"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(
                "No CSV exists in output/. Run '.venv/bin/python main.py' first."
            )
        csv_path = candidates[0].resolve()

    if csv_path.suffix.lower() != ".csv":
        raise ValueError(f"Expected a .csv file, received: {csv_path}")
    if not csv_path.is_file() or csv_path.stat().st_size == 0:
        raise FileNotFoundError(f"CSV is missing or empty: {csv_path}")
    return csv_path


def validate_csv(csv_path: Path) -> tuple[int, int]:
    """Validate the local public export before handing it to the GUI."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, delimiter=";")
        rows = list(reader)

    if len(rows) < 2:
        raise ValueError(f"CSV has no tender data rows: {csv_path}")
    if len(rows[0]) < 2 or "IDLicitacion" not in rows[0]:
        raise ValueError(
            "CSV does not look like a Mercado Público tender export: "
            f"header={rows[0]!r}"
        )
    return len(rows) - 1, len(rows[0])


def import_pyautogui() -> Any:
    if not os.environ.get("DISPLAY"):
        raise RuntimeError(
            "No graphical DISPLAY is available. Run from a desktop session or use "
            "'xvfb-run -a .venv/bin/python desktop_rpa.py'."
        )

    # PyAutoGUI imports MouseInfo even though mouse/keyboard automation does not
    # use it. MouseInfo exits the interpreter when Debian's optional Tk bindings
    # are absent, so provide its unused API locally instead of requiring Tk.
    mouseinfo_stub = types.ModuleType("mouseinfo")

    def mouse_info_unavailable() -> None:
        raise RuntimeError("MouseInfo is not used by this desktop RPA.")

    mouseinfo_stub.MouseInfoWindow = mouse_info_unavailable  # type: ignore[attr-defined]
    sys.modules.setdefault("mouseinfo", mouseinfo_stub)

    # PyAutoGUI connects to X11 at import time on Linux, so import it only after
    # giving the user a useful DISPLAY error.
    import pyautogui

    return pyautogui


def capture_screen(destination: Path | None = None) -> Any:
    """Capture X11 with Pillow, avoiding PyScreeze's optional scrot dependency."""
    image = ImageGrab.grab(xdisplay=os.environ.get("DISPLAY"))
    if destination is not None:
        image.save(destination)
    return image


def visible_window_titles() -> list[str]:
    """Return mapped X11 window titles, including WM-reparented clients."""
    from Xlib import X, display

    x_display = display.Display()
    try:
        titles: list[str] = []

        def visit(window: Any) -> None:
            try:
                if window.get_attributes().map_state == X.IsViewable:
                    title = window.get_wm_name()
                    if title:
                        titles.append(str(title))
                for child in window.query_tree().children:
                    visit(child)
            except Exception:
                return

        visit(x_display.screen().root)
        return titles
    finally:
        x_display.close()


def wait_for_window_title(
    text: str,
    timeout_seconds: int,
    description: str,
    also_contains: str | None = None,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    expected = text.casefold()
    second_expected = also_contains.casefold() if also_contains else None
    last_titles: list[str] = []
    while time.monotonic() < deadline:
        last_titles = visible_window_titles()
        for title in last_titles:
            folded_title = title.casefold()
            if expected in folded_title and (
                second_expected is None or second_expected in folded_title
            ):
                return title
        time.sleep(0.25)
    raise TimeoutError(
        f"Timed out waiting for {description}. Visible windows: {last_titles!r}"
    )


def has_window_manager() -> bool:
    from Xlib import X, display

    x_display = display.Display()
    try:
        root = x_display.screen().root
        atom = x_display.intern_atom("_NET_SUPPORTING_WM_CHECK", only_if_exists=True)
        if not atom:
            return False
        return root.get_full_property(atom, X.AnyPropertyType) is not None
    finally:
        x_display.close()


def start_window_manager() -> subprocess.Popen[bytes] | None:
    """Give bare Xvfb a focus-managing WM; leave real desktop WMs untouched."""
    if has_window_manager():
        return None

    window_manager = shutil.which("xfwm4")
    if window_manager is None:
        log("No window manager detected; continuing with bare X11")
        return None

    log("Starting xfwm4 for the virtual desktop")
    process = subprocess.Popen(
        [window_manager, "--compositor=off"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    if process.poll() is not None:
        raise RuntimeError("xfwm4 exited before the desktop automation started.")
    return process


def wait_for_process_exit(process: subprocess.Popen[bytes], timeout_seconds: int) -> bool:
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return False
    return True


def close_calc(pyautogui: Any, process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    log("Closing LibreOffice Calc")
    pyautogui.hotkey("ctrl", "q")
    if wait_for_process_exit(process, 8):
        return

    # This process belongs to this run and uses its own temporary profile.
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def drive_calc(
    csv_path: Path,
    search_text: str,
    screenshot_path: Path,
    startup_timeout: int,
    step_pause: float,
    keep_open: bool,
) -> None:
    if not search_text.strip():
        raise ValueError("The Calc search text cannot be empty.")
    if startup_timeout <= 0:
        raise ValueError("The startup timeout must be greater than zero.")
    if step_pause < 0:
        raise ValueError("The step pause cannot be negative.")

    office_binary = shutil.which("libreoffice") or shutil.which("localc")
    if office_binary is None:
        raise RuntimeError("LibreOffice Calc is not installed or is not on PATH.")

    pyautogui = import_pyautogui()
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = step_pause

    screen_width, screen_height = pyautogui.size()
    if screen_width < 800 or screen_height < 600:
        raise RuntimeError(
            f"Desktop is too small for reliable automation: "
            f"{screen_width}x{screen_height}."
        )

    screenshot_path = screenshot_path.expanduser().resolve()
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(tempfile.mkdtemp(prefix="public-tender-rpa-lo-"))
    command = [
        office_binary,
        f"-env:UserInstallation={profile_dir.as_uri()}",
        "--calc",
        "--nologo",
        "--nofirststartwizard",
        "--norestore",
    ]

    window_manager_process = start_window_manager()
    log(f"Launching LibreOffice Calc on DISPLAY={os.environ['DISPLAY']}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    completed = False

    try:
        calc_title = wait_for_window_title(
            "LibreOffice Calc", startup_timeout, "LibreOffice Calc"
        )
        log(f"Focused desktop window: {calc_title}")
        time.sleep(1)

        # Deliberately move through two points so a human observer can see the
        # pointer travel before the keyboard-driven open operation begins.
        pyautogui.moveTo(
            int(screen_width * 0.15), int(screen_height * 0.20), duration=0.6
        )
        pyautogui.moveTo(
            int(screen_width * 0.50), int(screen_height * 0.45), duration=0.8
        )
        pyautogui.click()

        log(f"Opening local CSV through Calc's file dialog: {csv_path}")
        pyautogui.hotkey("ctrl", "o")
        wait_for_window_title("Open", startup_timeout, "the file-open dialog")
        time.sleep(1)
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.5)
        pyautogui.write(str(csv_path), interval=0.01)
        pyautogui.press("enter")

        import_title = wait_for_window_title(
            "Import", startup_timeout, "the CSV import dialog"
        )
        log(f"Focused desktop window: {import_title}")
        time.sleep(0.75)
        log("Accepting Calc's detected semicolon-separated import settings")
        pyautogui.press("enter")
        document_title = wait_for_window_title(
            csv_path.name,
            startup_timeout,
            "the populated CSV spreadsheet",
            also_contains="LibreOffice Calc",
        )
        log(f"Focused desktop window: {document_title}")
        time.sleep(1)

        # Click within the grid, return to A1, and perform a real in-sheet find.
        pyautogui.moveTo(
            int(screen_width * 0.30), int(screen_height * 0.35), duration=0.8
        )
        pyautogui.click()
        pyautogui.hotkey("ctrl", "home")
        log(f"Searching the spreadsheet for {search_text.strip()!r}")
        pyautogui.hotkey("ctrl", "f")
        pyautogui.write(search_text.strip(), interval=0.08)
        pyautogui.press("enter")
        time.sleep(1)
        pyautogui.press("esc")

        # Finish with another visible pointer move near the spreadsheet grid.
        pyautogui.moveTo(
            int(screen_width * 0.65), int(screen_height * 0.55), duration=0.8
        )
        capture_screen(screenshot_path)
        if not screenshot_path.is_file() or screenshot_path.stat().st_size == 0:
            raise RuntimeError(f"Desktop screenshot was not created: {screenshot_path}")

        log(f"Saved desktop verification screenshot: {screenshot_path}")
        completed = True
        if keep_open:
            log(
                "Calc remains open as requested. Its isolated temporary profile is "
                f"{profile_dir}"
            )
        else:
            close_calc(pyautogui, process)
    finally:
        if not keep_open or not completed:
            if process.poll() is None:
                close_calc(pyautogui, process)
            shutil.rmtree(profile_dir, ignore_errors=True)
        if window_manager_process is not None and window_manager_process.poll() is None:
            window_manager_process.terminate()
            try:
                window_manager_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                window_manager_process.kill()
                window_manager_process.wait(timeout=5)


def main() -> int:
    args = parse_args()
    try:
        csv_path = resolve_csv(args.csv)
        row_count, column_count = validate_csv(csv_path)
        log(
            f"Validated {csv_path.name}: {row_count} public rows, "
            f"{column_count} columns"
        )
        drive_calc(
            csv_path=csv_path,
            search_text=args.search_text,
            screenshot_path=args.screenshot,
            startup_timeout=args.startup_timeout,
            step_pause=args.step_pause,
            keep_open=args.keep_open,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
