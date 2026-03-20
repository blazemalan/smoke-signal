@echo off
REM Drag and drop an audio file to enroll a speaker
set /p NAME="Speaker name: "
call conda activate scribe
scribe enroll "%NAME%" "%~1"
pause
