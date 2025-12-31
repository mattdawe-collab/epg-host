#!/bin/bash

# Configuration
PROJECT_DIR="/share/CACHEDEV2_DATA/Python Projects/AI_EPG_Bridge"
PYTHON_BIN="$PROJECT_DIR/venv_nas/bin/python3"
GIT_BIN="/share/CACHEDEV1_DATA/.qpkg/QGit/bin/git"

# Move to the project directory
cd "$PROJECT_DIR" || { echo "Directory not found"; exit 1; }

# 1. Pull latest code
"$GIT_BIN" pull origin main

# 2. Run the Python script (Quotes are CRITICAL here)
"$PYTHON_BIN" main.py

# 3. Automation Push
"$GIT_BIN" add .
"$GIT_BIN" commit -m "Auto-Update EPG: $(date +'%Y-%m-%d %H:%M')"
"$GIT_BIN" push origin main
