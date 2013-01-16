@ECHO OFF
REM Run this script if you'd like to connect a python commander
REM across the network to the CTF game server. The game server
REM must be run with one of the commanders specified as game.NetworkCommander.
REM eg. simulate.bat examples.RandomCommander game.NetworkCommander

CALL game\run.bat "%~dp0client.py" %*

PAUSE
