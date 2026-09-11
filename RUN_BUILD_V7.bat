@echo off
cd /d "%~dp0"
python build_v7.py
if errorlevel 1 pause
if exist AI_Provider_Free_Model_Scanner_v7.pyw start "" pythonw AI_Provider_Free_Model_Scanner_v7.pyw
