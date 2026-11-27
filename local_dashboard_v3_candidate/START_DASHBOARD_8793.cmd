@echo off
cd /d "%~dp0.."
echo ROKT and RAZO local dashboard: http://127.0.0.1:8793/
echo Keep this window open while using the dashboard.
echo This starts the dashboard only; it does not start a search or send email.
python -B -m local_dashboard_v3_candidate.server --port 8793
echo Dashboard stopped. If port 8793 is in use, open the address above instead.
pause
