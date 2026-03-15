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


def push_to_github(verbose=False):
    """Add, commit, and push changes to GitHub. Returns True on success."""
    success, _, error = run_command("git add .")
    if not success:
        if verbose:
            print(f"    Git add failed: {error}")
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-Update EPG: {timestamp}"

    success, _, error = run_command(f'git commit -m "{commit_msg}"')
    if not success:
        if "nothing to commit" in error:
            return True
        if verbose:
            print(f"    Git commit failed: {error}")
        return False

    success, _, error = run_command("git push origin main")
    if not success:
        if verbose:
            print(f"    Git push failed: {error}")
        return False

    return True


if __name__ == "__main__":
    import console_ui as ui
    ui.banner("PUSH TO GITHUB")
    if push_to_github(verbose=True):
        ui.success("Changes pushed to GitHub!")
    else:
        ui.error("Push failed")
