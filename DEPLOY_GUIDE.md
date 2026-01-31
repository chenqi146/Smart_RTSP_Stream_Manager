# Quick reference guide for deployment scripts

# ============================================
# Deployment Scripts Overview
# ============================================

# 1. deploy_simple.ps1
#    - Uploads ALL files (simple but slow)
#    Usage: .\deploy_simple.ps1 ubuntu@192.168.54.188

# 2. deploy_smart.ps1 (RECOMMENDED)
#    - Uses rsync if available (fast, only changed files)
#    - Falls back to file-by-file upload if rsync not available
#    Usage: .\deploy_smart.ps1 ubuntu@192.168.54.188 /data

# 3. deploy_git.ps1
#    - Only uploads files changed in git (requires git)
#    - Best for projects using git version control
#    Usage: .\deploy_git.ps1 ubuntu@192.168.54.188 /data

# 4. deploy_timestamp.ps1
#    - Only uploads files modified in last N hours
#    - Good for quick updates after recent changes
#    Usage: .\deploy_timestamp.ps1 ubuntu@192.168.54.188 /data 24
#           (uploads files modified in last 24 hours)

# ============================================
# Quick Commands
# ============================================

# Update version only:
# python update_version.py

# Upload all files (simple):
# .\deploy_simple.ps1 ubuntu@192.168.54.188

# Upload only changed files (smart, recommended):
# .\deploy_smart.ps1 ubuntu@192.168.54.188 /data

# Upload git changed files:
# .\deploy_git.ps1 ubuntu@192.168.54.188 /data

# Upload files modified in last 24 hours:
# .\deploy_timestamp.ps1 ubuntu@192.168.54.188 /data 24

# Upload files modified in last 1 hour (very quick):
# .\deploy_timestamp.ps1 ubuntu@192.168.54.188 /data 1

