@ECHO OFF
REM Run this script if you'd like to simulate mant CTF games with your
REM chosen bots.  

TITLE Capture The Flag Competition
CALL game\run.bat "%~dp0competition.py" %*

PAUSE
