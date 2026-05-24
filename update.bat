@echo off
chcp 65001 >nul
setlocal

:: ============================================================
::  SONAR Updater
:: ============================================================

set "APP_DIR=%~dp0"
set "UPDATER=%APP_DIR%_updater.py"
set "PYTHON="

:: [1] Ищем WPy рядом с update.bat (основной вариант)
for /d %%A in ("%APP_DIR%WPy\python-*.amd64") do (
  if exist "%%A\python.exe" set "PYTHON=%%A\python.exe"
)

:: [2] Ищем WPy в соседних папках (любое имя — SONAR.Bac, LandApp.bacup и т.п.)
if not defined PYTHON (
  for /d %%B in ("%APP_DIR%..\") do (
    for /d %%A in ("%%B\WPy\python-*.amd64") do (
      if exist "%%A\python.exe" set "PYTHON=%%A\python.exe"
    )
  )
)

:: [3] Fallback: системный Python
if not defined PYTHON (
  where python >nul 2>&1 && set "PYTHON=python"
)

echo.
echo  ================================================
echo   SONAR — Обновление кода из GitHub
echo  ================================================
echo.

if not defined PYTHON (
  echo  [ОШИБКА] Python не найден.
  echo  Убедись что папка WPy находится рядом с SONAR.
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
