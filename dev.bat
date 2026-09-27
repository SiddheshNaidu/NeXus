@echo off
setlocal EnableDelayedExpansion
rem =============================================================================
rem  dev.bat — NEXUS unified dev launcher (Windows)
rem
rem  Starts the FastAPI backend + Next.js frontend in separate windows.
rem  Auto-detects the Python virtual environment regardless of how it was named.
rem
rem  Usage:
rem    dev.bat         — starts both servers
rem    dev.bat stop    — kills both servers started by a previous run
rem =============================================================================

set "REPO_ROOT=%~dp0"
rem Strip trailing backslash
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "BACKEND_DIR=%REPO_ROOT%\backend"
set "FRONTEND_DIR=%REPO_ROOT%\frontend"
set "PID_FILE=%REPO_ROOT%\.dev_pids.txt"

rem ── Colour shim (works on Windows 10+) ───────────────────────────────────────
for /f %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"

rem ── --stop handler ────────────────────────────────────────────────────────────
if /i "%~1"=="stop" (
  if not exist "%PID_FILE%" (
    echo [nexus] No PID file found — nothing to stop.
    goto :eof
  )
  for /f "tokens=*" %%P in (%PID_FILE%) do (
    taskkill /PID %%P /F >nul 2>&1 && echo [nexus] Killed PID %%P
  )
  del /f /q "%PID_FILE%" >nul 2>&1
  echo [nexus] All dev processes stopped.
  goto :eof
)

rem ── Sanity-check directories ───────────────────────────────────────────────────
if not exist "%BACKEND_DIR%" (
  echo [nexus] ERROR: backend\ not found at %BACKEND_DIR%
  exit /b 1
)
if not exist "%FRONTEND_DIR%" (
  echo [nexus] ERROR: frontend\ not found at %FRONTEND_DIR%
  exit /b 1
)

rem ── Detect Python virtual environment ─────────────────────────────────────────
rem Checks a priority-ordered list of well-known locations, then falls back to
rem a DIR search for any activate.bat within 3 directory levels.
set "VENV_ACTIVATE="

set "CANDIDATES[0]=%BACKEND_DIR%\.venv\Scripts\activate.bat"
set "CANDIDATES[1]=%BACKEND_DIR%\venv\Scripts\activate.bat"
set "CANDIDATES[2]=%BACKEND_DIR%\.env\Scripts\activate.bat"
set "CANDIDATES[3]=%BACKEND_DIR%\env\Scripts\activate.bat"
set "CANDIDATES[4]=%REPO_ROOT%\.venv\Scripts\activate.bat"
set "CANDIDATES[5]=%REPO_ROOT%\venv\Scripts\activate.bat"
set "CANDIDATES[6]=%REPO_ROOT%\.env\Scripts\activate.bat"
set "CANDIDATES[7]=%REPO_ROOT%\env\Scripts\activate.bat"

for /l %%i in (0,1,7) do (
  if "!VENV_ACTIVATE!"=="" (
    if exist "!CANDIDATES[%%i]!" (
      set "VENV_ACTIVATE=!CANDIDATES[%%i]!"
    )
  )
)

rem Fallback: recursive DIR search (catches any custom-named venv)
if "!VENV_ACTIVATE!"=="" (
  for /f "delims=" %%F in ('dir /s /b "%REPO_ROOT%\activate.bat" 2^>nul ^| findstr /i "Scripts\\activate.bat"') do (
    if "!VENV_ACTIVATE!"=="" set "VENV_ACTIVATE=%%F"
  )
)

if "!VENV_ACTIVATE!"=="" (
  echo [nexus] ERROR: No Python virtual environment found.
  echo.
  echo   Expected one of:
  echo     backend\.venv\   backend\venv\   .venv\   venv\
  echo     ^(or any *\Scripts\activate.bat within the repo^)
  echo.
  echo   Create one with:  python -m venv backend\.venv
  exit /b 1
)

echo [nexus] Found virtual environment: !VENV_ACTIVATE!

rem ── Check required tools ──────────────────────────────────────────────────────
where node >nul 2>&1 || (echo [nexus] ERROR: 'node' not found. Install Node.js first. & exit /b 1)
where npm  >nul 2>&1 || (echo [nexus] ERROR: 'npm' not found. Install Node.js first.  & exit /b 1)

rem ── Ensure frontend node_modules exist ───────────────────────────────────────
if not exist "%FRONTEND_DIR%\node_modules" (
  echo [nexus] node_modules not found — running npm install...
  npm install --prefix "%FRONTEND_DIR%" || (echo [nexus] ERROR: npm install failed. & exit /b 1)
)

rem ── Copy .env.example → .env if .env is absent ───────────────────────────────
if not exist "%BACKEND_DIR%\.env" (
  if exist "%BACKEND_DIR%\.env.example" (
    copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
    echo [nexus] WARN: .env was missing — copied from .env.example.
    echo         Edit %BACKEND_DIR%\.env with real credentials.
  )
)

rem ── Seed the database with deterministic dev users ───────────────────────────
rem Runs every startup but is fully idempotent (ON CONFLICT DO NOTHING).
rem Set SKIP_SEED=1 in environment to bypass — e.g. set SKIP_SEED=1 && dev.bat
if /i not "!SKIP_SEED!"=="1" (
  echo [nexus] Seeding dev users into the database ^(idempotent^)...
  call "!VENV_ACTIVATE!" && cd /d "%BACKEND_DIR%" && python seed_test_data.py
  if errorlevel 1 (
    echo [nexus] WARN: Seed failed — backend may start without test users. Is the DB running?
  ) else (
    echo [nexus] Database seed OK.
  )
  cd /d "%REPO_ROOT%"
)

rem ── Clear previous PID file ───────────────────────────────────────────────────
if exist "%PID_FILE%" del /f /q "%PID_FILE%"

rem ── Launch backend in a new window ────────────────────────────────────────────
echo [nexus] Starting FastAPI backend on http://localhost:8000 ...
start "NEXUS — Backend" /min cmd /c ^
  "call "!VENV_ACTIVATE!" && cd /d "%BACKEND_DIR%" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > "%REPO_ROOT%\.backend.log" 2>&1"

rem Give the shell a moment to register the new process
timeout /t 1 /nobreak >nul

rem Capture backend PID by matching the uvicorn command line
for /f "tokens=2" %%P in ('tasklist /fi "IMAGENAME eq python.exe" /fo table /nh 2^>nul') do (
  for /f "tokens=*" %%C in ('wmic process where "ProcessId=%%P" get CommandLine /value 2^>nul ^| findstr /i "uvicorn"') do (
    echo %%P >> "%PID_FILE%"
  )
)

rem ── Launch frontend in a new window ───────────────────────────────────────────
echo [nexus] Starting Next.js frontend on http://localhost:3000 ...
start "NEXUS — Frontend" /min cmd /c ^
  "cd /d "%FRONTEND_DIR%" && npm run dev > "%REPO_ROOT%\.frontend.log" 2>&1"

timeout /t 1 /nobreak >nul

rem Capture node PID for the Next.js dev server
for /f "tokens=2" %%P in ('tasklist /fi "IMAGENAME eq node.exe" /fo table /nh 2^>nul') do (
  echo %%P >> "%PID_FILE%"
)

rem ── Done ──────────────────────────────────────────────────────────────────────
echo.
echo   [OK] NEXUS is running
echo.
echo        Frontend  -^>  http://localhost:3000
echo        Backend   -^>  http://localhost:8000/docs
echo.
echo        Logs:  .backend.log  ^|  .frontend.log
echo        Stop:  dev.bat stop
echo.

endlocal
