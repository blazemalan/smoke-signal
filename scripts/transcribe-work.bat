@echo off
REM Drag and drop an audio file onto this .bat to transcribe a work meeting
call conda activate scribe
scribe transcribe "%~1" --profile work --identify
pause
