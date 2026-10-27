@echo off
echo === Seed du lieu luat vao ChromaDB (khong can UI) ===
echo.
"%~dp0backend\.venv\Scripts\python.exe" "%~dp0seed_data.py" %*
echo.
pause
