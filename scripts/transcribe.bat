@echo off
REM Drag and drop an audio file onto this .bat to transcribe it
REM Uses the "therapy" profile by default (2 speakers, local, identify on)
call conda activate scribe
smoke-signal transcribe "%~1" --profile therapy --identify
pause
