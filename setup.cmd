@echo off
REM Einmalige Einrichtung von Qualli-ERP (Python-Umgebung, Pakete, Oberfläche).
setlocal
cd /d "%~dp0"

echo [1/4] Python-Umgebung anlegen ...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv || goto :error
)

echo [2/4] Python-Pakete installieren ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :error

echo [3/4] Desktop-App installieren ...
pushd qualli-erp-desktop
call npm install --no-fund --no-audit || goto :error_pop
echo [4/4] Oberflaeche bauen ...
call npm run build || goto :error_pop
popd

echo.
echo Fertig. Starten mit: start.cmd
echo Beispieldaten anlegen (optional): .venv\Scripts\python.exe seed.py
exit /b 0

:error_pop
popd
:error
echo.
echo FEHLER bei der Einrichtung. Bitte Meldungen oben pruefen.
exit /b 1
