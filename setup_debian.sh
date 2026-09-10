#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Debian system dependencies..."
sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  libreoffice-calc \
  xvfb \
  xfwm4

echo "==> Creating Python virtual environment..."
python3 -m venv .venv

echo "==> Activating virtual environment..."
source .venv/bin/activate

echo "==> Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "==> Installing Playwright Chromium and required browser dependencies..."
python -m playwright install --with-deps chromium

echo
echo "Setup complete."
echo "Run browser RPA with:"
echo "  source .venv/bin/activate && python main.py"
echo
echo "Run desktop RPA from a graphical Debian session with:"
echo "  source .venv/bin/activate && python desktop_rpa.py"
echo
echo "For a virtual X11 display:"
echo "  xvfb-run -a .venv/bin/python desktop_rpa.py"
