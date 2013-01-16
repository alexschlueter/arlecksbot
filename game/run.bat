@ECHO OFF
REM The AI Sandbox comes with a standard version of Python 2.7.3, which
REM is setup here to find all the necessary extension modules.  We use
REM environment variables to point it to the right place, then pass in
REM the full path to the CTF application script along with arguments.

IF ["%AISANDBOX_DIR%"]==[""] SET AISANDBOX_DIR=%LocalAppData%\AiGameDev.com\The AI Sandbox

IF NOT EXIST "%AISANDBOX_DIR%\environment.bat" (
ECHO ERROR! The AI Sandbox has not yet been installed on this machine.
ECHO.
ECHO Please go to the website and download the latest version:
ECHO     http://aisandbox.com/
ECHO.
PAUSE
EXIT
)

CALL "%AISANDBOX_DIR%\environment.bat"
TITLE Capture The Flag Log

SET PYTHONHOME=%AISANDBOX_BIN%
SET PYTHONPATH=%AISANDBOX_BIN%
"%AISANDBOX_BIN%\python.exe" -S %*