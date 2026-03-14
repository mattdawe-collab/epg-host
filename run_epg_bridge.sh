#!/bin/bash
# ========================================================
#   AI EPG BRIDGE v3.0 - NAS AUTOMATION WITH GIT
#   QNAP NAS - Daily cron at 3:00 AM
# ========================================================
set -o pipefail

# --- PATHS (QNAP-specific) ---
PROJECT_DIR="/share/CACHEDEV2_DATA/Python Projects/AI_EPG_Bridge"
PYTHON_BIN="$PROJECT_DIR/venv_nas/bin/python3"
GIT_BIN="/share/CACHEDEV1_DATA/.qpkg/QGit/bin/git"

# Move to project directory
cd "$PROJECT_DIR" || { echo "[ERROR] Project directory not found: $PROJECT_DIR"; exit 1; }

# --- LOGGING ---
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/epg_run_$(date +'%Y%m%d_%H%M%S').log"
LATEST_LOG="$LOG_DIR/latest.log"
STATUS_FILE="$LOG_DIR/last_run_status.txt"

log() {
    echo "$(date +'%H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# --- START ---
log "======================================================"
log "  AI EPG BRIDGE v3.0 - Auto-Update"
log "======================================================"
log "Started at: $(date +'%Y-%m-%d %H:%M:%S')"
log "Working directory: $PROJECT_DIR"
log ""

# --- PREFLIGHT CHECKS ---
for check in ".env:Configuration file" "$PYTHON_BIN:Python3 venv" "$GIT_BIN:Git"; do
    path="${check%%:*}"
    label="${check#*:}"
    if [ ! -e "$path" ]; then
        log "[ERROR] $label not found at: $path"
        echo "FAILED: $(date +'%Y-%m-%d %H:%M:%S') - $label not found" > "$STATUS_FILE"
        exit 1
    fi
done

log "[*] Python: $($PYTHON_BIN --version 2>&1)"
log "[*] Git: $($GIT_BIN --version 2>&1)"
log ""

# Verify git credentials work before doing anything
log "[PREFLIGHT] Checking GitHub access..."
if ! "$GIT_BIN" ls-remote origin HEAD &>/dev/null; then
    log "[ERROR] Cannot reach GitHub remote. Check credentials/network."
    log "  Hint: Run 'git config credential.helper store' then push manually once."
    echo "FAILED: $(date +'%Y-%m-%d %H:%M:%S') - GitHub auth failed" > "$STATUS_FILE"
    exit 1
fi
log "[*] GitHub access verified."
log ""

# --- [1/5] INSTALL DEPENDENCIES (first run only) ---
if [ ! -f "$LOG_DIR/install_check.lock" ]; then
    log "[1/5] First run - Installing dependencies..."
    "$PYTHON_BIN" -m pip install -r requirements.txt >> "$LOG_FILE" 2>&1
    if [ $? -ne 0 ]; then
        log "[ERROR] Failed to install dependencies."
        echo "FAILED: $(date +'%Y-%m-%d %H:%M:%S') - pip install failed" > "$STATUS_FILE"
        exit 1
    fi
    echo "installed" > "$LOG_DIR/install_check.lock"
    log "[SUCCESS] Dependencies installed."
else
    log "[1/5] Dependencies already installed."
fi
log ""

# --- [2/5] GIT PULL ---
log "[2/5] Pulling latest from GitHub..."
"$GIT_BIN" pull origin main >> "$LOG_FILE" 2>&1
PULL_EXIT=$?
if [ $PULL_EXIT -ne 0 ]; then
    log "[WARNING] Git pull failed (exit $PULL_EXIT) - continuing with local copy"
fi
log ""

# --- [3/5] GENERATE EPG ---
log "[3/5] Generating EPG data..."
log "================================================"

# Use tee to capture output AND get reliable exit code (no subshell pipe issue)
"$PYTHON_BIN" src/main.py 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

log "================================================"

if [ $EXIT_CODE -ne 0 ]; then
    log "[ERROR] EPG generation failed (exit $EXIT_CODE)"
    echo "FAILED: $(date +'%Y-%m-%d %H:%M:%S') - EPG generation failed" > "$STATUS_FILE"
    exit 1
fi
log "[SUCCESS] EPG data generated."
log ""

# --- [4/5] DEPLOY EPG ---
log "[4/5] Deploying EPG to root..."
"$PYTHON_BIN" src/deploy_epg.py >> "$LOG_FILE" 2>&1
log ""

# --- [5/5] GIT COMMIT & PUSH ---
log "[5/5] Committing and pushing to GitHub..."

# Targeted git add - only track output files, not everything
"$GIT_BIN" add \
    data/known_matches.json \
    data/epg_repair.xml.gz \
    data/epg_repair.xml \
    epg.xml.gz \
    src/epg.xml.gz \
    logs/missing_channels.txt \
    suggested_matches.json \
    2>> "$LOG_FILE"

"$GIT_BIN" commit -m "Auto-Update EPG: $(date +'%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE" 2>&1
COMMIT_EXIT=$?

if [ $COMMIT_EXIT -ne 0 ]; then
    log "[INFO] No changes to commit."
else
    # Push with one retry
    "$GIT_BIN" push origin main >> "$LOG_FILE" 2>&1
    PUSH_EXIT=$?
    if [ $PUSH_EXIT -ne 0 ]; then
        log "[WARNING] Push failed, retrying in 10s..."
        sleep 10
        "$GIT_BIN" push origin main >> "$LOG_FILE" 2>&1
        PUSH_EXIT=$?
    fi

    if [ $PUSH_EXIT -ne 0 ]; then
        log "[ERROR] Failed to push to GitHub after retry (exit $PUSH_EXIT)"
        echo "PARTIAL: $(date +'%Y-%m-%d %H:%M:%S') - EPG generated but push failed" > "$STATUS_FILE"
        # Don't exit 1 - EPG was generated successfully, push can be retried
    else
        log "[SUCCESS] Changes pushed to GitHub!"
    fi
fi

# --- FINISH ---
log ""
log "======================================================"
log "  Complete - $(date +'%Y-%m-%d %H:%M:%S')"
log "======================================================"

# Symlink latest log
ln -sf "$LOG_FILE" "$LATEST_LOG"

# Save status
echo "SUCCESS: $(date +'%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
log "[STATUS] Last run: SUCCESS"

# Keep only last 30 log files
ls -t "$LOG_DIR"/epg_run_*.log 2>/dev/null | tail -n +31 | xargs -r rm 2>/dev/null

# Only pause if interactive
if [ -t 0 ]; then
    echo ""
    read -p "Press Enter to close..."
fi
