@echo off
chcp 65001 >nul
cd /d "%~dp0"
title SONAR

echo ============================================
echo  SONAR - Nizhegorodskaya oblast
echo ============================================
echo.

reg add "HKCU\Software\Microsoft\Command Processor" /v DisableUNCCheck /t REG_DWORD /d 1 /f >nul 2>&1

set "APP_DIR=%~dp0"
set "PYTHON="
set "SITEPKG="

:: ============================================================
:: [1] Ищем WPy рядом с этим файлом (основной вариант)
:: ============================================================
for /d %%A in ("%APP_DIR%WPy\python-*.amd64") do (
  if exist "%%A\python.exe" (
    set "PYTHON=%%A\python.exe"
    set "SITEPKG=%%A\Lib\site-packages"
  )
)

:: ============================================================
:: [2] Ищем WPy в любой соседней папке (любое имя: SONAR.Bac, backup и т.п.)
:: ============================================================
if not defined PYTHON (
  for /d %%B in ("%APP_DIR%..\") do (
    for /d %%A in ("%%B\WPy\python-*.amd64") do (
      if exist "%%A\python.exe" (
        set "PYTHON=%%A\python.exe"
        set "SITEPKG=%%A\Lib\site-packages"
        echo  [INFO] Python найден в соседней папке ^(fallback^)
      )
    )
  )
)

:: ============================================================
:: [3] Если WPy не найден — предлагаем запустить install.bat
:: ============================================================
if not defined PYTHON (
  echo.
  echo  [ВНИМАНИЕ] Python не найден!
  echo.
  echo  Папка WPy\ не обнаружена рядом с SONAR.
  echo.
  if exist "%APP_DIR%install.bat" (
    echo  Найден install.bat — запустить его чтобы установить WPy?
    echo.
    set /p INST=  Запустить install.bat? [Enter = да / 0 = нет]: 
    if not "!INST!"=="0" (
      call "%APP_DIR%install.bat"
      :: После установки перезапускаем поиск
      for /d %%A in ("%APP_DIR%WPy\python-*.amd64") do (
        if exist "%%A\python.exe" (
          set "PYTHON=%%A\python.exe"
          set "SITEPKG=%%A\Lib\site-packages"
        )
      )
    )
  ) else (
    echo  install.bat не найден.
    echo  Скопируйте папку WPy\ рядом с этим файлом.
  )
  echo.
)

:: Финальная проверка после возможной установки
if not defined PYTHON (
  echo.
  echo  [ОШИБКА] Python всё ещё не найден. Обратитесь к администратору.
  echo.
  pause
  exit /b 1
)

echo  OK: %PYTHON%
echo.

:: ============================================================
:: Очистка устаревших .pth
:: ============================================================
for %%v in (3.5 3.6 3.7 3.8 3.9) do (
  for %%f in ("%SITEPKG%\*-py%%v-nspkg.pth") do (
    if exist "%%f" del /f /q "%%f"
  )
)
del /f /q "%SITEPKG%\distutils-precedence.pth" 2>nul

:: ============================================================
:: Бекап БД
:: ============================================================
if not exist "%APP_DIR%db\backups" mkdir "%APP_DIR%db\backups"
if exist "%APP_DIR%db\database.db" (
    xcopy /Y /I "%APP_DIR%db\database.db" "%APP_DIR%db\backups\database_%date:~6,4%%date:~3,2%%date:~0,2%.db*" >nul
    echo  Бекап: db\backups\database_%date:~6,4%%date:~3,2%%date:~0,2%.db
) else (
    echo  [ПРЕДУПРЕЖДЕНИЕ] db\database.db не найден
)

"%PYTHON%" -c "import os,glob;files=sorted(glob.glob('db/backups/database_*.db'));[os.remove(f) for f in files[:-5]];print('  Хранится резервных копий: '+str(min(len(files),5)))"
echo.

:: ============================================================
:: Health check
:: ============================================================
"%PYTHON%" -m py_compile app.py
if errorlevel 1 (
  echo.
  echo  [ОШИБКА] Синтаксисеская ошибка в app.py!
  echo.
  pause
  exit /b 1
)
echo  Health check OK.
echo.

:: ============================================================
:: Обновление кода из GitHub
:: ============================================================
if exist "%APP_DIR%update.bat" (
  set /p UPD=  Обновить код из GitHub? [Enter = да / 0 = нет]: 
  if not "%UPD%"=="0" (
    echo.
    call "%APP_DIR%update.bat"
    echo.
  )
)

:: ============================================================
:: Sync changelog
:: ============================================================
set /p SYNC=  Sync changelog с GitHub? [Enter = да / 0 = нет]: 
if not "%SYNC%"=="0" (
  echo.
  "%PYTHON%" "%APP_DIR%sync_changelog.py"
  echo.
)

:: ============================================================
:: Выбор режима
:: ============================================================
:ask_mode
echo  Выбери режим:
echo    [1] Production  (нормальная работа)
echo    [2] Debug       (подробные ошибки, авто-релоад)
echo.
set "MODE_CHOICE="
set /p MODE_CHOICE=  Режим (1/2): 

if "%MODE_CHOICE%"=="1" (
  set "FLASK_ENV=production"
  set "APP_DEBUG=0"
) else if "%MODE_CHOICE%"=="2" (
  set "FLASK_ENV=development"
  set "APP_DEBUG=1"
) else (
  echo  Неверный выбор, введи 1 или 2.
  echo.
  goto ask_mode
)
echo.

:: ============================================================
:: Открыть браузер
:: ============================================================
:ask_open
set "OPEN_CHOICE="
set /p OPEN_CHOICE=  Открыть браузер? [1 = да / 0 = нет]: 
if "%OPEN_CHOICE%"=="1" (
  start "" http://127.0.0.1:5000
) else if "%OPEN_CHOICE%"=="0" (
  rem skip
) else (
  echo  Введи 1 или 0.
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

:: ============================================================
:: Запуск сервера
:: ============================================================
:start_server
echo  Сервер запущен... Для остановки нажмите Ctrl+C
echo.

set FLASK_ENV=%FLASK_ENV%
set APP_DEBUG=%APP_DEBUG%
"%PYTHON%" "%APP_DIR%app.py"

echo.
echo ============================================
echo   Сервер остановлен.
echo ============================================
echo.
echo   [1] Перезапустить
echo   [2] Выйти

echo.
set "CHOICE="
set /p CHOICE=  Выбор (1/2): 
if "%CHOICE%"=="1" goto start_server

:quit
exit /b 0
