@echo off
title Smoke Signal
cd /d C:\Users\blaze\projects\smoke-signal
set PATH=C:\Users\blaze\miniconda3\envs\scribe\Lib\site-packages\nvidia\cudnn\bin;%PATH%
call conda activate scribe
smoke-signal watch
pause
