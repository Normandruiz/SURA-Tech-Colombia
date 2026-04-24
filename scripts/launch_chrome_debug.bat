@echo off
REM ==============================================================
REM  SURA Tech Colombia - Chrome en modo debug para Playwright
REM
REM  Usa un perfil DEDICADO (no el default del usuario) para que
REM  Chrome permita el puerto de debug. La primera vez vas a tener
REM  que loguearte en Google / Google Ads / Meta / GA4 / Sheets.
REM  Las siguientes corridas reutilizan las cookies.
REM
REM  Este Chrome NO interfiere con tu Chrome normal - se pueden
REM  abrir ambos al mismo tiempo (directorios diferentes).
REM ==============================================================

setlocal

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
set "USER_DATA_DIR=%USERPROFILE%\.suratech_playwright_profile"
set "DEBUG_PORT=9222"

if not exist "%CHROME_EXE%" (
    echo [ERROR] No encuentro Chrome en "%CHROME_EXE%".
    echo         Ajustá CHROME_EXE al inicio del .bat si tu instalación está en otra ruta.
    exit /b 1
)

if not exist "%USER_DATA_DIR%" (
    echo [INFO] Primer uso: creando perfil dedicado en:
    echo        %USER_DATA_DIR%
    mkdir "%USER_DATA_DIR%"
    echo [!] Vas a tener que loguearte en Google una vez.
    echo.
)

echo.
echo Abriendo Chrome-Debug...
echo   Perfil     : %USER_DATA_DIR%
echo   Puerto CDP : %DEBUG_PORT%
echo   URL debug  : http://localhost:%DEBUG_PORT%
echo.

start "" "%CHROME_EXE%" ^
    --remote-debugging-port=%DEBUG_PORT% ^
    --user-data-dir="%USER_DATA_DIR%" ^
    --no-first-run ^
    --no-default-browser-check

endlocal
