@echo off
setlocal ENABLEDELAYEDEXPANSION

REM === get current USER PATH
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v PATH') do (
    set "PATH_VALUE=%%B"
)

REM === set Python paths
set "PY_PATH=%cd%"
set "LIB_PATH=!PY_PATH!\Lib"
set "SCR_PATH=!PY_PATH!\scripts"

REM === combine all
set "NEW_PATH_VALUE=!PATH_VALUE!;!PY_PATH!;!LIB_PATH!;!SCR_PATH!"

echo === Add Python to USER PATH ===
echo.
echo [Current USER PATH:]
echo ----------------------------
echo !PATH_VALUE!
echo.
echo [Python paths to add:]
echo Root:     !PY_PATH!
echo Lib:      !LIB_PATH!
echo Scripts:  !SCR_PATH!
echo.
echo [NEW USER PATH TO SET:]
echo ----------------------------
echo !NEW_PATH_VALUE!
echo ----------------------------

echo === Confirmation ===
set /p CONFIRM=Do you want to update USER PATH with this value? (y/n): 
if /i not "!CONFIRM!"=="y" (
    echo.
    echo [INFO] Operation cancelled by user.
    pause
    goto :eof
)

echo === Writing to the USER PATH ===
reg add "HKCU\Environment" /v PATH /d "!NEW_PATH_VALUE!" /f

echo.
echo [SUCCESS] USER PATH updated in registry!
echo.
pause
endlocal
