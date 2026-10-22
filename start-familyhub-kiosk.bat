@echo off
REM Double-click to start FamilyHub AND open it full-screen (kiosk) in Edge.
REM The server runs in its own window; close that window to stop it.
REM Press Ctrl-W in Edge to leave kiosk mode.
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install -r requirements.txt
)
start "FamilyHub server" cmd /c "call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo Waiting for the server to start...
timeout /t 6 >nul
start msedge --kiosk "http://localhost:8000" --edge-kiosk-type=fullscreen --touch-events=enabled
exit
