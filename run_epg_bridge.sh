#!/bin/bash
# ========================================================
#   AI EPG BRIDGE v2.0 - LAUNCHER WITH GIT AUTOMATION
# ========================================================

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================"
echo "  AI EPG BRIDGE v2.0 - Auto-Push to GitHub"
echo "======================================================"
echo
echo "Working directory: $SCRIPT_DIR"
echo

# Check for .env
if [ ! -f ".env" ]; then
    echo "[ERROR] .env file not found!"
    echo "Please ensure you're running this script from your AI EPG Bridge project directory."
    echo "Current directory: $SCRIPT_DIR"
    read -p "Press Enter to close..."
    exit 1
fi

# Check if this is a Git repository
if [ ! -d ".git" ]; then
    echo "[ERROR] Not a Git repository!"
    echo "Please ensure you're running this script from your AI EPG Bridge project directory."
    echo "Current directory: $SCRIPT_DIR"
    read -p "Press Enter to close..."
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found"
    echo "Please install Python 3.8 or higher."
    read -p "Press Enter to close..."
    exit 1
fi

# Check for Git
if ! command -v git &> /dev/null; then
    echo "[ERROR] Git not found"
    echo "Please install Git."
    read -p "Press Enter to close..."
    exit 1
fi

# Use virtual environment if it exists (optional)
if [ -d "venv" ]; then
    echo "[*] Activating virtual environment (venv)..."
    source venv/bin/activate
elif [ -d "venv_nas" ]; then
    echo "[*] Activating virtual environment (venv_nas)..."
    source venv_nas/bin/activate
else
    echo "[*] No virtual environment found - using system Python"
fi

# Install dependencies if needed
if [ ! -f "logs/install_check.lock" ]; then
    echo "[1/4] First run - Installing dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install dependencies."
        read -p "Press Enter to close..."
        exit 1
    fi
    mkdir -p logs
    echo "installed" > "logs/install_check.lock"
else
    echo "[1/4] Dependencies already installed."
fi

# Pull latest changes from GitHub
echo "[2/4] Syncing with GitHub..."
git pull origin main
if [ $? -ne 0 ]; then
    echo "[WARNING] Git pull failed. Continuing anyway..."
    echo "         (This might be due to merge conflicts or network issues)"
fi
echo

# Run the EPG Bridge
echo "[3/4] Generating EPG data..."
echo
python3 src/main.py
if [ $? -ne 0 ]; then
    echo
    echo "[ERROR] EPG generation failed!"
    echo "Please check the error messages above."
    read -p "Press Enter to close..."
    exit 1
fi
echo

# Push to GitHub
echo "[4/4] Pushing to GitHub..."
git add .
git commit -m "Auto-Update EPG: $(date +'%Y-%m-%d %H:%M:%S')"
if [ $? -ne 0 ]; then
    echo "[INFO] No changes to commit."
else
    git push origin main
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to push to GitHub!"
        echo "Please check your Git credentials and repository access."
        read -p "Press Enter to close..."
        exit 1
    fi
    echo "[SUCCESS] Changes pushed to GitHub!"
fi

echo
echo "======================================================"
echo "  Process Complete - EPG Updated and Published"
echo "======================================================"
echo
read -p "Press Enter to close..."