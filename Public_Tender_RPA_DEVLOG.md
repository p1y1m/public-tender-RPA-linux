# Public Tender RPA — Development Log

**Author:** Pedro Yanez Melendez

## Project Summary

This project automates the search and handling of public tender information from Chile's Mercado Público platform.

It contains two automation layers:

1. **Browser RPA** using Python + Playwright to search public tenders and download the official CSV export.
2. **Desktop RPA** using Python + PyAutoGUI to open the downloaded CSV in LibreOffice Calc and interact with it using visible mouse and keyboard actions.

The project uses only public web pages and local files. It does not require personal email accounts, credentials, private data, or secret API keys.

---

## Objective

Create a small but complete RPA project that demonstrates practical automation skills to IT managers and recruiters while remaining safe to publish publicly on GitHub.

The workflow was intentionally designed to:
- run on Debian Linux;
- use public information only;
- avoid credentials and personal accounts;
- automate both browser and desktop tasks;
- produce a visible and verifiable output;
- remain simple enough to reproduce and explain.

---

## Environment

Development and testing were performed on:
- Debian Linux virtual machine on Google Cloud Platform
- Python 3.11
- Visual Studio Code
- Python virtual environment (`.venv`)
- Playwright
- Chromium for Playwright
- PyAutoGUI
- LibreOffice Calc
- X11 / Xvfb support for graphical automation

---

## 1. Browser RPA — Mercado Público

### Goal

Automatically:
1. Open Mercado Público.
2. Search for public tenders using a configurable search term.
3. Reach the tender results.
4. Detect the results component correctly.
5. Trigger the official results export.
6. Download the generated CSV into the local `output/` folder.

### Main file

`main.py`

### Default search

```text
software
```

A different search term can be supplied through the command line.

### Important implementation detail

Mercado Público does not render the search results directly in the main document.  
The results are loaded inside:

```text
iframe#form-iframe
```

Inside that iframe, the download control is dynamically generated as:

```text
a#descargarCSV
```

The automation waits for the iframe and its dynamically loaded content before requesting the download.

### Main workflow

The browser automation:
- opens `https://www.mercadopublico.cl/Home`;
- fills the Mercado Público search field;
- submits the search;
- waits for the result iframe;
- waits for the download control;
- listens for the browser download event before clicking;
- saves the CSV in `output/`;
- avoids overwriting an existing file by generating a timestamped filename when needed;
- validates that the downloaded file exists and is not empty;
- closes the browser cleanly.

### Example execution

```bash
source .venv/bin/activate
python main.py
```

Different search term:

```bash
python main.py --query "licencias de software"
```

Visible Chromium:

```bash
python main.py --headed
```

### Verified result

The browser RPA was tested end to end successfully.

A successful run:
- opened Mercado Público;
- searched for software-related tenders;
- reached the public search results;
- generated the official result export;
- downloaded a non-empty CSV into `output/`.

Example generated file:

```text
output/ListaLicitaciones.csv
```

The number of tender records can change because Mercado Público contains live public data.

---

## 2. Desktop RPA — LibreOffice Calc

### Goal

Add a classic desktop-RPA layer that visibly controls the desktop using mouse and keyboard actions.

### Main file

`desktop_rpa.py`

### Workflow

The desktop automation:
1. Finds the newest Mercado Público CSV in `output/`.
2. Validates that the CSV is non-empty and has the expected tender structure.
3. Launches LibreOffice Calc.
4. Visibly moves the mouse pointer.
5. Opens Calc's file-open dialog.
6. Types the CSV path using keyboard automation.
7. Opens the CSV.
8. Accepts the detected semicolon-separated import configuration.
9. Waits until the spreadsheet is visibly loaded.
10. Clicks inside the spreadsheet.
11. Uses `Ctrl+Home`.
12. Uses `Ctrl+F`.
13. Searches for the word `software`.
14. Selects the first matching result.
15. Captures a verification screenshot.
16. Closes the isolated LibreOffice Calc process cleanly unless `--keep-open` is requested.

### Example execution

```bash
source .venv/bin/activate
python desktop_rpa.py
```

Leave Calc open:

```bash
python desktop_rpa.py --keep-open
```

Different search text:

```bash
python desktop_rpa.py --search-text "licencias"
```

### Verified result

The desktop RPA was tested end to end successfully.

It:
- opened the downloaded Mercado Público CSV;
- imported it correctly into LibreOffice Calc;
- performed visible mouse and keyboard interactions;
- searched the spreadsheet;
- selected a matching cell;
- produced a screenshot as evidence;
- closed Calc cleanly.

Example screenshot output:

```text
output/desktop_rpa.png
```

---

## Problems Solved During Development

### Download control initially could not be located

The link was visible in the browser but Playwright could not find it in the top-level document.

**Cause:** the results and download control were inside a dynamically loaded iframe.

**Solution:** explicitly target `iframe#form-iframe` and wait for `a#descargarCSV`.

### Fixed waits were unreliable

Early tests used long fixed delays while waiting for Mercado Público.

**Improvement:** replace fixed waits with explicit Playwright waits for navigation, iframe content, page elements, and download events.

### PyAutoGUI dependency issue on Debian

PyAutoGUI attempted to load the optional MouseInfo component, which expected Debian Tk bindings.

The desktop RPA does not use MouseInfo.

**Solution:** provide a small local stub for the unused MouseInfo API before importing PyAutoGUI.

### Screenshot dependency issue

The usual PyAutoGUI screenshot path expected utilities that were not installed on the VM.

**Solution:** use Pillow's native X11 `ImageGrab` support.

### LibreOffice state detection

Early tests based only on screen pixel changes could produce false positives.

**Solution:** inspect actual X11 window titles and wait for specific application/dialog states before continuing.

---

## Project Files

### Important source files

```text
main.py
desktop_rpa.py
DEVLOG.md
```

### Runtime/generated files

```text
output/
    ListaLicitaciones.csv
    desktop_rpa.png
```

### Files that should normally NOT be published

```text
.venv/
__pycache__/
get-pip.py
```

The virtual environment is machine-specific and unnecessary in GitHub.

---

## Privacy and Safety

The project was intentionally designed to be safe for public demonstration.

It does **not** use:
- email accounts;
- personal credentials;
- passwords;
- private company systems;
- personal customer data;
- secret API keys;
- authenticated Mercado Público sessions.

The browser RPA uses only publicly accessible Mercado Público pages.

The desktop RPA uses only the public CSV downloaded by the browser RPA and local LibreOffice Calc.

---

## Current Status

**Project status: Finished and working.**

The project demonstrates:
- public website browser automation;
- dynamic iframe handling;
- automated data export;
- file validation;
- configurable command-line execution;
- desktop mouse and keyboard automation;
- LibreOffice integration on Linux;
- screenshot-based execution evidence;
- error handling and timeouts;
- privacy-safe automation design.

The remaining work is portfolio packaging only, such as GitHub upload, screenshots, and LinkedIn publication.

---

## Recruiter-Friendly Summary

Built an end-to-end RPA solution that automatically searches Chilean public tenders, downloads structured results, and performs desktop interactions with the generated data.

The solution combines browser automation and classic desktop RPA on Debian Linux while using only public information and requiring no personal credentials or private systems.
