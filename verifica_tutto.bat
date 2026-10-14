@echo off
REM verifica_tutto.bat — Esegue le suite di test su Windows. Attiva il
REM virtualenv se presente, lancia pytest, stampa un riepilogo.
REM NB: mai eseguito su Windows reale (vedi BLOCCHI.md).

setlocal enabledelayedexpansion
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"

echo ----------------------------------------------------------------
echo PrivacyBridge -- verifica_tutto
echo Data: %DATE% %TIME%
for /f "delims=" %%v in ('python --version 2^>^&1') do echo Python: %%v
echo ----------------------------------------------------------------

echo.
echo ^>^> Suite motore + documenti (incl. OCR)
echo ----------------------------------------------------------------
python -m pytest tests\test_motore.py tests\test_documenti.py -v --tb=short
set rc_backend=%errorlevel%

echo.
echo ^>^> Suite tassonomia PII (recognizer deterministici)
echo ----------------------------------------------------------------
python -m pytest tests\test_tassonomia.py -v --tb=short
set rc_tax=%errorlevel%

echo.
echo ^>^> Suite avversariale (500+ casi sistematici)
echo ----------------------------------------------------------------
python -m pytest tests\test_avversariale.py -q --tb=short
set rc_avv=%errorlevel%

echo.
echo ^>^> Matrice input
echo ----------------------------------------------------------------
python -m benchmark.matrice_input
set rc_mat=%errorlevel%

echo.
echo ^>^> Suite garanzie (6 garanzie di prodotto)
echo ----------------------------------------------------------------
python -m pytest tests\test_garanzie.py -v --tb=short
set rc_g=%errorlevel%

echo.
echo ^>^> Suite interfaccia (Playwright, Chromium headless)
echo ----------------------------------------------------------------
python -m pytest tests\test_interfaccia.py -v --tb=short
set rc_ui=%errorlevel%

echo.
echo ----------------------------------------------------------------
echo Riepilogo
echo ----------------------------------------------------------------
echo   backend    : rc=%rc_backend%
echo   tassonomia : rc=%rc_tax%
echo   avversarial: rc=%rc_avv%
echo   matrice    : rc=%rc_mat%
echo   garanzie   : rc=%rc_g%
echo   interfaccia: rc=%rc_ui%
echo ----------------------------------------------------------------

if not %rc_backend%==0 goto :fail
if not %rc_tax%==0 goto :fail
if not %rc_avv%==0 goto :fail
if not %rc_mat%==0 goto :fail
if not %rc_g%==0 goto :fail
if not %rc_ui%==0 goto :fail
echo STATO: OK -- tutte le suite passate.
exit /b 0

:fail
echo STATO: FALLITO
exit /b 1
