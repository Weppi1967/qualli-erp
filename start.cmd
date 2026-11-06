@echo off
REM Startet die Qualli-ERP Desktop-App (das Backend wird automatisch mitgestartet).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst setup.cmd ausfuehren.
  pause
  exit /b 1
)
if not exist "qualli-erp-desktop\dist\index.html" (
  pushd qualli-erp-desktop
  call npm run build
  popd
)
cd qualli-erp-desktop
call npx electron .
