#!/bin/bash

# Configuration
PROJECT_DIR="/volume1/Python Projects/AI_EPG_BRIDGE"
PYTHON_BIN="$PROJECT_DIR/venv_nas/bin/python3"
GIT_BIN="/usr/bin/git"

# Move to the project directory on the NAS
cd "$PROJECT_DIR" || { echo "Directory not found"; exit 1; }

# 1. Pull the latest code (sync with GitHub)
$GIT_BIN pull origin main

# 2. Run the Weekly Python script using the NAS-specific venv
$PYTHON_BIN main.py

# 3. Automation Push
# Stage only the files that change
$GIT_BIN add data/known_matches.json data/epg_repair.xml logs/missing_channels.txt

# Commit with a timestamp
$GIT_BIN commit -m "Auto-Update EPG: $(date +'%Y-%m-%d %H:%M')"

# Push back to your repository
$GIT_BIN push origin main