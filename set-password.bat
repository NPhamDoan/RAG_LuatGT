@echo off
REM Doi mat khau admin. Dung: set-password.bat  (hoac)  set-password.bat "matkhau"
cd /d "%~dp0"
backend\.venv\Scripts\python.exe set_password.py %*
