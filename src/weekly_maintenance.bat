@echo off
cd /d Y:\AI_EPG_Bridge

echo [1/2] Running Main EPG Generation...
python src/main.py

echo [2/2] Running Deep Recycle on Missing Channels...
python src/recycle_missing.py

echo Done. Check logs/missing_channels.txt to see what's left.
pause