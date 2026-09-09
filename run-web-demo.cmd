@echo off
setlocal

where node >nul 2>nul || (
  echo Node nao encontrado. Instale Node 24 e tente novamente.
  exit /b 1
)

python --version || exit /b 1
node web\scripts\build.mjs || exit /b 1
python -m ai_service_desk web-demo --host 127.0.0.1 --port 8000
