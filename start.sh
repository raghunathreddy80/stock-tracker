#!/usr/bin/env bash
set -e

# Install Chromium if not already present
if ! command -v chromium &> /dev/null && ! command -v chromium-browser &> /dev/null; then
    echo "==> Installing Chromium..."
    apt-get update -qq
    apt-get install -y -qq chromium chromium-driver
    echo "==> Chromium installed: $(chromium --version 2>/dev/null || chromium-browser --version)"
else
    echo "==> Chromium already available: $(chromium --version 2>/dev/null || chromium-browser --version)"
fi

# Export paths for the app to pick up
export CHROME_BIN=$(command -v chromium || command -v chromium-browser)
export CHROMEDRIVER_PATH=$(command -v chromedriver)
echo "==> CHROME_BIN=$CHROME_BIN"
echo "==> CHROMEDRIVER_PATH=$CHROMEDRIVER_PATH"

# Start the app
exec gunicorn stock_backend:app
