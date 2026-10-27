@echo off
echo === RAG Luat Giao Thong ===
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.

:: Start backend (visible — de xem log)
start "RAG-Backend" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Wait for backend ready (poll port 8000)
echo Dang cho backend khoi dong...
:wait_backend
timeout /t 2 /nobreak >nul
powershell -Command "try { (New-Object Net.Sockets.TcpClient('localhost',8000)).Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto wait_backend
echo Backend san sang.

:: Start frontend (minimized)
start /min "RAG-Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

timeout /t 2 /nobreak >nul
echo Frontend san sang.
echo.
echo Mo http://localhost:5173 de su dung.
echo Dong cua so nay va cua so Backend de dung.
pause
