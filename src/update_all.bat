@echo off
echo ========================================================
echo        AI EPG BRIDGE - AUTOMATED UPDATE SEQUENCE
echo ========================================================

REM 1. Move to Project Root
cd /d "Y:\AI_EPG_Bridge"

REM 2. Run the Hunt (Finds new matches)
echo.
echo [1/4] Hunting for missing channels...
python src/hunt_missing.py

REM 3. Run the Builder (Creates the database)
echo.
echo [2/4] Building new EPG data...
python src/main.py

REM 4. Prepare the File (Copy compressed file to root)
echo.
echo [3/4] Staging file for release...
copy /Y "data\epg_repair.xml.gz" "epg.xml.gz"

REM 5. Push to GitHub
echo.
echo [4/4] Pushing to GitHub...
git add epg.xml.gz data/known_matches.json
git commit -m "Auto-update: Fresh EPG and new matches"
git push

echo.
echo ========================================================
echo                  UPDATE COMPLETE!
echo    Your TinyURL is now serving the latest data.
echo ========================================================
pause