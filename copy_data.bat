@echo off
chcp 65001 >nul
setlocal

echo ================================================
echo   Kopirovaniye dannykh v LandApp
echo ================================================
echo.

set "SRC=%~dp0..\LandApp.bacup"
set "DST=%~dp0"

if not exist "%SRC%" (
    echo [OSHIBKA] Papka LandApp.bacup ne naydena:
    echo          %SRC%
    echo.
    echo Ubedis chto LandApp i LandApp.bacup lezhat ryadom.
    pause
    exit /b 1
)

echo Istochnik : %SRC%
echo Naznacheniye: %DST%
echo.

:: -- .env
echo Kopiruju .env...
if exist "%SRC%\.env" (
    copy /Y "%SRC%\.env" "%DST%\.env" >nul
    echo [OK] .env
) else (
    echo [--] .env ne nayden -- propusk
)

:: -- database.db -> db\database.db
echo Kopiruju database.db...
if not exist "%DST%db" mkdir "%DST%db"
if exist "%SRC%\database.db" (
    copy /Y "%SRC%\database.db" "%DST%db\database.db" >nul
    echo [OK] database.db -> db\database.db
) else if exist "%SRC%\db\database.db" (
    copy /Y "%SRC%\db\database.db" "%DST%db\database.db" >nul
    echo [OK] db\database.db -> db\database.db
) else (
    echo [--] database.db ne nayden -- propusk
)

:: -- uploads\
echo Kopiruju uploads\...
if exist "%SRC%\uploads" (
    xcopy /E /I /Y /Q "%SRC%\uploads" "%DST%uploads" >nul
    echo [OK] uploads\
) else (
    echo [--] uploads\ ne nayden -- propusk
)

:: -- reports\
echo Kopiruju reports\...
if exist "%SRC%\reports" (
    xcopy /E /I /Y /Q "%SRC%\reports" "%DST%reports" >nul
    echo [OK] reports\
) else (
    echo [--] reports\ ne nayden -- propusk
)

echo.
echo ================================================
echo  Gotovo! Teper mozhno zapuskat start SONAR.bat
echo ================================================
echo.
pause
