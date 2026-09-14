@echo off
REM PrivacyBridge — launcher Windows (mostra una finestra console: usare
REM al posto del .vbs solo per debug).
cd /d "%~dp0"
if exist "venv\Scripts\pythonw.exe" (
    "venv\Scripts\pythonw.exe" "src\avvio.py"
) else (
    "venv\Scripts\python.exe" "src\avvio.py"
)
