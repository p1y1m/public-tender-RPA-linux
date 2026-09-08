"""Download public tender search results from MercadoPublico.cl."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import (
    Download,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


HOME_URL = "https://www.mercadopublico.cl/Home"
DEFAULT_QUERY = "software"
DEFAULT_TIMEOUT_SECONDS = 120


def log(message: str) -> None:
    """Print progress immediately, including when stdout is redirected."""
    print(message, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search Mercado Público and download the public result export."
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f"Public tender search text (default: {DEFAULT_QUERY!r}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
        help="Directory in which to save the downloaded file.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout in seconds for navigation, results, and download generation.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show Chromium (requires a graphical display or xvfb-run on a VM).",
    )
    return parser.parse_args()


def safe_filename(name: str) -> str:
    """Keep a server-supplied filename local to the output directory."""
    filename = Path(name).name
    filename = re.sub(r"[^A-Za-z0-9._ -]+", "_", filename).strip(" .")
    return filename or "mercadopublico-results.csv"


def unique_destination(output_dir: Path, suggested_filename: str) -> Path:
    destination = output_dir / safe_filename(suggested_filename)
    if not destination.exists():
        return destination

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return destination.with_name(f"{destination.stem}-{stamp}{destination.suffix}")


def log_frame_diagnostics(page: Page) -> None:
    log("Frames present at failure:")
    for index, frame in enumerate(page.frames):
        log(f"  [{index}] name={frame.name!r} url={frame.url!r}")


def save_download(download: Download, output_dir: Path) -> Path:
    failure = download.failure()
    if failure:
        raise RuntimeError(f"Mercado Público reported a failed download: {failure}")

    destination = unique_destination(output_dir, download.suggested_filename)
    download.save_as(destination)

    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f"The downloaded file is missing or empty: {destination}")
    return destination


def download_results(
    query: str, output_dir: Path, timeout_seconds: int, headed: bool
) -> Path:
    if not query.strip():
        raise ValueError("The search query cannot be empty.")
    if timeout_seconds <= 0:
        raise ValueError("The timeout must be greater than zero.")

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timeout_ms = timeout_seconds * 1_000

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.set_default_navigation_timeout(timeout_ms)

        try:
            log(f"Opening {HOME_URL}")
            page.goto(HOME_URL, wait_until="domcontentloaded")

            search_box = page.locator("#txtBuscar")
            search_box.wait_for(state="visible")
            search_box.fill(query.strip())

            log(f"Searching public tenders for {query.strip()!r}")
            with page.expect_navigation(
                wait_until="domcontentloaded", timeout=timeout_ms
            ):
                page.locator("#btnBuscar").click()

            # The top page creates this blank iframe and auto-submits a POST form
            # into it. The iframe then loads its results with a second AJAX POST.
            results_frame = page.frame_locator("iframe#form-iframe")
            results_frame.locator("#textoBusqueda").wait_for(state="visible")
            download_link = results_frame.locator("a#descargarCSV")

            log("Waiting for the results component inside iframe#form-iframe")
            try:
                download_link.wait_for(state="visible", timeout=timeout_ms)
            except PlaywrightTimeoutError as exc:
                results_text = results_frame.locator("#searchResults").inner_text(
                    timeout=5_000
                )
                raise RuntimeError(
                    "The results iframe loaded, but no download control appeared. "
                    f"Results text: {results_text.strip()!r}"
                ) from exc

            log("Requesting the server-generated result export")
            with page.expect_download(timeout=timeout_ms) as download_info:
                download_link.click()

            destination = save_download(download_info.value, output_dir)
            log(
                f"Saved {destination.name} "
                f"({destination.stat().st_size:,} bytes) to {output_dir}"
            )
            return destination
        except Exception:
            log_frame_diagnostics(page)
            raise
        finally:
            context.close()
            browser.close()


def main() -> int:
    args = parse_args()
    try:
        download_results(args.query, args.output_dir, args.timeout, args.headed)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
