@echo off
echo === Build Frontend ===
cd /d %~dp0frontend
call npm run build
echo.
echo Build output: frontend\dist\
echo Co the phuc vu tu backend (static files) hoac dung rieng.
pause
