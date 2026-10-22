@echo off
REM Double-click to start FamilyHub on Windows (Surface Pro test).
REM Then open Edge to http://localhost:8000
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo First-time setup: creating environment...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
echo.
echo FamilyHub is starting. Open Edge to:  http://localhost:8000
echo (Close this window to stop it.)
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
