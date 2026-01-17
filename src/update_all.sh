#!/bin/bash

# 1. The "Magic Path" we just found
PYTHON="/share/CACHEDEV2_DATA/.qpkg/Python3/opt/python3/bin/python3"

# 2. Go to your Project Folder
cd "/share/CACHEDEV2_DATA/Python Projects/AI_EPG_Bridge"

# 3. Run the AI Sequence
echo "Starting Hunt..."
$PYTHON src/hunt_missing.py

echo "Building EPG..."
$PYTHON src/main.py

# 4. Deploy
echo "Deploying..."
cp data/epg_repair.xml.gz epg.xml.gz

# 5. Push to GitHub
git config user.email "nas@automation"
git config user.name "QNAP NAS"

git add epg.xml.gz data/known_matches.json
git commit -m "NAS Auto-Update"
git push
echo "Done!"
