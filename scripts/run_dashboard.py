"""Launch the SIEIS Streamlit dashboard.

Usage:
    python scripts/run_dashboard.py
"""

import os
import sys
import subprocess

# Ensure we're in the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

dashboard_path = os.path.join(project_root, "src", "app", "dashboard", "app.py")

print("🚀 Starting SIEIS Dashboard...")
print(f"   Dashboard path: {dashboard_path}")
print(f"   URL: http://localhost:8501")
print("   Press Ctrl+C to stop\n")

subprocess.run([
    sys.executable, "-m", "streamlit", "run",
    dashboard_path,
    "--server.port", "8501",
    "--server.address", "0.0.0.0",
    "--browser.gatherUsageStats", "false",
], check=True)
