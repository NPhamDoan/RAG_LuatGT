@echo off
echo === Setup RAG Luat Giao Thong ===
echo.

echo [1/3] Cai dat backend dependencies...
cd /d %~dp0backend
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt --quiet
echo      Done.

echo.
echo [2/3] Tao .env (neu chua co)...
if not exist .env (
    copy .env.example .env
    echo      Tao .env tu .env.example. Vui long dien API key.
) else (
    echo      .env da ton tai, bo qua.
)

echo.
echo [3/3] Cai dat frontend dependencies...
cd /d %~dp0frontend
call npm install --silent
echo      Done.

echo.
echo === Setup hoan tat ===
echo Buoc tiep: dien API key vao backend\.env roi chay run_all.bat
pause
