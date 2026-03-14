#!/bin/bash
# ========================================================
#   EPG BRIDGE - STATUS CHECKER
# ========================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================"
echo "  EPG BRIDGE - LAST RUN STATUS"
echo "======================================================"
echo ""

# Check if status file exists
if [ -f "logs/last_run_status.txt" ]; then
    echo "Last Run Status:"
    cat logs/last_run_status.txt
    echo ""
else
    echo "No status file found. Script hasn't run yet."
    echo ""
fi

# Show last 5 runs
echo "Last 5 Runs:"
echo "----------------------------------------------------"
if [ -d "logs" ]; then
    ls -lt logs/epg_run_*.log 2>/dev/null | head -5 | while read -r line; do
        filename=$(echo "$line" | awk '{print $NF}')
        timestamp=$(basename "$filename" .log | sed 's/epg_run_//')
        size=$(echo "$line" | awk '{print $5}')
        
        # Extract status from log
        if grep -q "\[SUCCESS\] Changes pushed to GitHub" "$filename" 2>/dev/null; then
            status="✓ SUCCESS"
        elif grep -q "\[ERROR\]" "$filename" 2>/dev/null; then
            status="✗ FAILED"
        else
            status="? UNKNOWN"
        fi
        
        echo "$timestamp - $status ($size bytes)"
    done
else
    echo "No logs directory found."
fi

echo ""
echo "======================================================"
echo ""
echo "Commands:"
echo "  View latest log:     cat logs/latest.log"
echo "  View specific log:   cat logs/epg_run_YYYYMMDD_HHMMSS.log"
echo "  Run EPG bridge:      ./run_epg_bridge.sh"
echo ""
