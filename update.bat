@echo off
chcp 65001 >nul
setlocal

:: ============================================================
::  SONAR Updater
:: ============================================================

set "APP_DIR=%~dp0"
set "UPDATER=%APP_DIR%_updater.py"
set "PYTHON="

:: [1] Ищем рядом
for /d %%A in ("%APP_DIR%WPy\python-*.amd64") do (
  if exist "%%A\python.exe" set "PYTHON=%%A\python.exe"
)

:: [2] Fallback: LandApp.bacup
if not defined PYTHON (
  for /d %%A in ("%APP_DIR%..\LandApp.bacup\WPy\python-*.amd64") do (
    if exist "%%A\python.exe" set "PYTHON=%%A\python.exe"
  )
)

echo.
echo  ================================================
echo   SONAR — Обновление кода из GitHub
echo  ================================================
echo.

if not defined PYTHON (
  echo [ОШИБКА] Python не найден ни рядом, ни в LandApp.bacup.
  pause
  exit /b 1
)

"%PYTHON%" "%UPDATER%"
set UPDATER_EXIT=%ERRORLEVEL%

echo.
pause

:: Если _updater.py вернул 2 — bat обновился, перезапускаем
if "%UPDATER_EXIT%"=="2" (
  echo.
  echo  [!] start SONAR.bat обновился — перезапуск...
  echo.
  start "" cmd /c ""%APP_DIR%start SONAR.bat""
  exit /b 0
)

exit /b 0
