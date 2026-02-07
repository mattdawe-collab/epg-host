import subprocess
import sys
from datetime import datetime

def run_command(cmd):
    """Execute shell command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def push_to_github():
    """Add, commit, and push changes to GitHub"""
    print("[GIT] Adding files...")
    success, _, error = run_command("git add .")
    if not success:
        print(f"[ERROR] Git add failed: {error}")
        return False
    
    # Create commit message with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-Update EPG: {timestamp}"
    
    print(f"[GIT] Committing: {commit_msg}")
    success, _, error = run_command(f'git commit -m "{commit_msg}"')
    if not success:
        if "nothing to commit" in error:
            print("[INFO] No changes to commit")
            return True
        print(f"[ERROR] Git commit failed: {error}")
        return False
    
    print("[GIT] Pushing to origin/main...")
    success, _, error = run_command("git push origin main")
    if not success:
        print(f"[ERROR] Git push failed: {error}")
        return False
    
    print("[SUCCESS] Changes pushed to GitHub!")
    return True

if __name__ == "__main__":
    push_to_github()