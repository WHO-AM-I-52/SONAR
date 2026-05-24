@echo off
chcp 65001 >nul
cd /d "%~dp0"
title SONAR - Ustanovka

echo.
echo ============================================================
echo   SONAR - Ustanovka / pervonachalnaya nastroyka
echo ============================================================
echo.

set "APP_DIR=%~dp0"
set "PYTHON="
set "SITEPKG="
set "WPY_DIR=%APP_DIR%WPy"
set "TOOLS_PY=%APP_DIR%tools\python313\python.exe"

:: ============================================================
:: SHAG 1: Ishchem Python
:: ============================================================
echo [1/5] Poisk Python...

:: Snachala ishchem v WPy (esli uzhe byl ustanovlen ranee)
for /d %%A in ("%WPY_DIR%\python-*.amd64") do (
  if exist "%%A\python.exe" (
    set "PYTHON=%%A\python.exe"
    set "SITEPKG=%%A\Lib\site-packages"
  )
)

if defined PYTHON (
  echo  OK (WPy): %PYTHON%
  goto :install_deps
)

:: Proverka tools\python313
if exist "%TOOLS_PY%" (
  echo  Nayden portativny Python v tools\python313
  echo  Kopiruyu v WPy\python313...
  if not exist "%WPY_DIR%" mkdir "%WPY_DIR%"
  xcopy /E /I /Y /Q "%APP_DIR%tools\python313" "%WPY_DIR%\python313"
  set "PYTHON=%WPY_DIR%\python313\python.exe"
  set "SITEPKG=%WPY_DIR%\python313\Lib\site-packages"
  echo  OK: %PYTHON%
  goto :install_deps
)

:: Nichego ne nashli
echo.
echo  [VNIMANIE] Python ne nayden.
echo.
echo  Vyberi variant:
echo    [1] Ukazat put k python.exe vruchnuyu
echo    [0] Vyyti
echo.
set "CHOICE="
set /p CHOICE=  Vybor (1/0): 
if "%CHOICE%"=="1" goto :manual_path
goto :quit

:manual_path
echo.
set "MANUAL_PY="
set /p MANUAL_PY=  Put k python.exe: 
if "%MANUAL_PY%"=="" goto :no_python
if exist "%MANUAL_PY%" (
  set "PYTHON=%MANUAL_PY%"
  for %%X in ("%MANUAL_PY%") do set "SITEPKG=%%~dpXLib\site-packages"
  echo  OK: %PYTHON%
  goto :install_deps
)
echo  [OSHIBKA] Fayl ne nayden.

:no_python
echo.
echo  [OSHIBKA] Python ne nayden. Ustanovka nevozmozhna.
echo.
pause
exit /b 1

:: ============================================================
:: SHAG 2: Proverka pip
:: ============================================================
:install_deps
echo.
echo [2/5] Proverka pip...

"%PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo  pip ne nayden, ustanovka...
  if exist "%APP_DIR%tools\python313\get-pip.py" (
    "%PYTHON%" "%APP_DIR%tools\python313\get-pip.py" --quiet
    echo  OK: pip ustanovlen.
  ) else (
    "%PYTHON%" -m ensurepip --upgrade >nul 2>&1
    echo  OK: pip cherez ensurepip.
  )
) else (
  echo  OK: pip est.
)

:: ============================================================
:: SHAG 3: Zavisimosti
:: ============================================================
echo.
echo [3/5] Ustanovka zavisimostey iz requirements.txt...

if not exist "%APP_DIR%requirements.txt" (
  echo  [WARN] requirements.txt ne nayden - propusk.
  goto :create_dirs
)

"%PYTHON%" -m pip install --quiet -r "%APP_DIR%requirements.txt"
if errorlevel 1 (
  echo  [OSHIBKA] Ne udalos ustanovit zavisimosti.
  echo  Proverte podklyucheniye k Internetu.
  pause
  exit /b 1
)
echo  OK: zavisimosti ustanovleny.

:: ============================================================
:: SHAG 4: Papki i BD
:: ============================================================
:create_dirs
echo.
echo [4/5] Sozdaniye papok...

for %%D in (db uploads reports db\backups) do (
  if not exist "%APP_DIR%%%D" (
    mkdir "%APP_DIR%%%D"
    echo  Sozdana: %%D
  ) else (
    echo  Uzhe est: %%D
  )
)

echo.
echo  Podgotovka bazy dannykh...

if exist "%APP_DIR%db\database.db" (
  echo  BD uzhe est - ne trogaem.
  goto :create_env
)
if exist "%APP_DIR%db\db_template.db" (
  copy /Y "%APP_DIR%db\db_template.db" "%APP_DIR%db\database.db" >nul
  echo  OK: BD sozdana iz shablona.
  goto :create_env
)
if exist "%APP_DIR%db.py" (
  "%PYTHON%" "%APP_DIR%db.py"
  if errorlevel 1 (
    echo  [WARN] db.py vernul oshibku.
  ) else (
    echo  OK: BD initializirovana.
  )
) else (
  echo  [WARN] db.py ne nayden. BD budet sozdana pri zapuske.
)

:: ============================================================
:: SHAG 5: .env
:: ============================================================
:create_env
echo.
echo [5/5] Proverka .env...

if exist "%APP_DIR%.env" (
  echo  .env uzhe est - ne trogaem.
) else (
  "%PYTHON%" -c "import secrets; open('.env','w').write('SECRET_KEY=' + secrets.token_hex(32) + '\n')"
  echo  OK: .env sozdan.
)

echo.
echo ============================================================
echo   Ustanovka zavershena!
echo.
echo   Teper zapusti: start SONAR.bat
echo ============================================================
echo.
pause
exit /b 0

:quit
exit /b 0
