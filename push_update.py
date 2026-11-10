import os
import subprocess
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("github_token", "").strip("\"'")
repo_url = os.getenv("github_repo", "").strip("\"'")

clean_url = repo_url.replace("https://", "")
auth_url = f"https://x-access-token:{token}@{clean_url}"

# Stage & Commit
subprocess.run(["git", "add", "."], check=True)
subprocess.run(["git", "commit", "-m", "feat: add crypto auto-resolution, technical analysis, news and watchlist"], check=True)

# Set authenticated remote & push
subprocess.run(["git", "remote", "set-url", "origin", auth_url], check=True)
res = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
print("Push output:", res.stdout, res.stderr)

# Reset remote URL to clean URL
subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
print("Remote URL reset.")
