@echo off
chcp 65001 >nul
cd /d "%~dp0"
title SONAR - Land App

echo ============================================
echo  SONAR - Nizhny Novgorod
echo ============================================
echo.

reg add "HKCU\Software\Microsoft\Command Processor" /v DisableUNCCheck /t REG_DWORD /d 1 /f >nul 2>&1

set "APP_DIR=%~dp0"
set "PYTHON="
set "SITEPKG="

:: [1] Ishchem Python ryadom (WPy\ v papke LandApp)
for /d %%A in ("%APP_DIR%WPy\python-*.amd64") do (
  if exist "%%A\python.exe" (
    set "PYTHON=%%A\python.exe"
    set "SITEPKG=%%A\Lib\site-packages"
  )
)

:: [2] Fallback: ishchem v LandApp.bacup
if not defined PYTHON (
  for /d %%A in ("%APP_DIR%..\LandApp.bacup\WPy\python-*.amd64") do (
    if exist "%%A\python.exe" (
      set "PYTHON=%%A\python.exe"
      set "SITEPKG=%%A\Lib\site-packages"
      echo  [INFO] Python nayden v LandApp.bacup (fallback)
    )
  )
)

:: [3] TODO: v budushchem -- install.bat skachayet WPy avtomaticheski
:: if not defined PYTHON call "%APP_DIR%install.bat"

if not defined PYTHON (
  echo.
  echo  [ERROR] Python ne nayden!
  echo.
  echo  Varianty resheniya:
  echo    1. Skopiruy WPy\ iz LandApp.bacup v papku ryadom s etim faylom
  echo    2. Zapusti install.bat (poyavitsya v budushchey versii)
  echo.
  pause
  exit /b 1
)

echo  OK: %PYTHON%
echo.

:: Ochistka starykh .pth
echo Cleaning old .pth packages...
for %%v in (3.5 3.6 3.7 3.8 3.9) do (
  for %%f in ("%SITEPKG%\*-py%%v-nspkg.pth") do (
    if exist "%%f" del /f /q "%%f"
  )
)
del /f /q "%SITEPKG%\distutils-precedence.pth" 2>nul
echo Done.
echo.

:: Bekap bazy dannykh
if not exist "%APP_DIR%db\backups" mkdir "%APP_DIR%db\backups"
echo Creating database backup...
if exist "%APP_DIR%db\database.db" (
    xcopy /Y /I "%APP_DIR%db\database.db" "%APP_DIR%db\backups\database_%date:~6,4%%date:~3,2%%date:~0,2%.db*" >nul
    echo Backup: db\backups\database_%date:~6,4%%date:~3,2%%date:~0,2%.db
) else (
    echo [WARN] db\database.db ne nayden -- bekap propushchen
)
echo.

"%PYTHON%" -c "import os,glob;files=sorted(glob.glob('db/backups/database_*.db'));[os.remove(f) for f in files[:-5]];print('Backups kept: '+str(min(len(files),5)))"
echo.

:: Health check
echo Running health check...
"%PYTHON%" -m py_compile app.py
if errorlevel 1 (
  echo.
  echo [ERROR] Syntax error in app.py -- fix and restart.
  echo.
  pause
  exit /b 1
)
echo Health check OK.
echo.

:: Obnovleniye koda iz GitHub
if exist "%APP_DIR%update.bat" (
  set /p UPD=Obnovit kod iz GitHub? [Enter = da / 0 = net]: 
  if not "%UPD%"=="0" (
    echo.
    call "%APP_DIR%update.bat"
    echo.
  )
)

:: Sync changelog
set /p SYNC=Sync changelog s GitHub? [Enter = da / 0 = net]: 
if not "%SYNC%"=="0" (
  echo.
  "%PYTHON%" "%APP_DIR%sync_changelog.py"
  echo.
)

:: Vybor rezhima
:ask_mode
echo Select mode:
echo   [1] Production  (normal work)
echo   [2] Debug       (detailed errors, auto-reload)
echo.
set "MODE_CHOICE="
set /p MODE_CHOICE=Mode (1/2): 

if "%MODE_CHOICE%"=="1" (
  set "FLASK_ENV=production"
  set "APP_DEBUG=0"
) else if "%MODE_CHOICE%"=="2" (
  set "FLASK_ENV=development"
  set "APP_DEBUG=1"
) else (
  echo Invalid choice, enter 1 or 2.
  echo.
  goto ask_mode
)
echo.

:: Otkryt brauzer
:ask_open
set "OPEN_CHOICE="
set /p OPEN_CHOICE=Otkryt brauser? [1 = da / 0 = net]: 
if "%OPEN_CHOICE%"=="1" (
  start "" http://127.0.0.1:5000
) else if "%OPEN_CHOICE%"=="0" (
  rem skip
) else (
  echo Enter 1 or 0.
  echo.
  goto ask_open
)

:: IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
  set ip=%%a
  goto :found
)
:found
set ip=%ip: =%

echo.
echo ============================================
echo  Local:   http://127.0.0.1:5000
echo  Network: http://%ip%:5000
echo ============================================
echo.

:: Zapusk servera
:start_server
echo Server is running... Press Ctrl+C to stop.
echo.

set FLASK_ENV=%FLASK_ENV%
set APP_DEBUG=%APP_DEBUG%
"%PYTHON%" "%APP_DIR%app.py"

echo.
echo ============================================
echo   Server stopped.
echo ============================================
echo.
echo   [1] Restart server
echo   [2] Exit
echo.
set "CHOICE="
set /p CHOICE=Choice (1/2): 
if "%CHOICE%"=="1" goto start_server

:quit
exit /b 0
