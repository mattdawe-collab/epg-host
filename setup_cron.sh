#!/bin/bash
# ========================================================
#   QNAP CRON SETUP for AI EPG Bridge
#   Run this once on the NAS to install the daily schedule
# ========================================================

PROJECT_DIR="/share/CACHEDEV2_DATA/Python Projects/AI_EPG_Bridge"
CRON_ENTRY="0 3 * * * cd \"$PROJECT_DIR\" && ./run_epg_bridge.sh >> \"$PROJECT_DIR/logs/cron.log\" 2>&1"
QNAP_CRONTAB="/etc/config/crontab"

echo "======================================================"
echo "  AI EPG Bridge - Cron Setup"
echo "======================================================"
echo ""
echo "This will schedule the EPG bridge to run daily at 3:00 AM."
echo ""

# Check if we're on QNAP (has /etc/config/crontab)
if [ -f "$QNAP_CRONTAB" ]; then
    echo "Detected QNAP system."
    echo ""

    # Check if entry already exists
    if grep -q "run_epg_bridge.sh" "$QNAP_CRONTAB" 2>/dev/null; then
        echo "[WARNING] Cron entry already exists:"
        grep "run_epg_bridge" "$QNAP_CRONTAB"
        echo ""
        echo "To update, remove the old entry first, then re-run this script."
        exit 0
    fi

    echo "Adding cron entry to $QNAP_CRONTAB..."
    echo ""
    echo "Entry: $CRON_ENTRY"
    echo ""

    read -p "Proceed? (y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$CRON_ENTRY" >> "$QNAP_CRONTAB"
        crontab "$QNAP_CRONTAB"
        echo ""
        echo "[SUCCESS] Cron entry installed!"
        echo "The EPG bridge will run daily at 3:00 AM."
        echo ""
        echo "Verify with: crontab -l | grep epg"
    else
        echo "Cancelled."
    fi
else
    # Standard Linux crontab
    echo "Standard Linux system detected."
    echo ""
    echo "Add this line to your crontab (crontab -e):"
    echo ""
    echo "  $CRON_ENTRY"
    echo ""
    echo "Or run: (crontab -l 2>/dev/null; echo '$CRON_ENTRY') | crontab -"
fi

echo ""
echo "======================================================"
echo ""
echo "Useful commands:"
echo "  Check schedule:   crontab -l | grep epg"
echo "  View cron log:    tail -f \"$PROJECT_DIR/logs/cron.log\""
echo "  Manual run:       cd \"$PROJECT_DIR\" && ./run_epg_bridge.sh"
echo "  Check status:     cat \"$PROJECT_DIR/logs/last_run_status.txt\""
echo ""
