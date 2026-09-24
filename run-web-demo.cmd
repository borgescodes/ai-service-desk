@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
pushd "%PROJECT_ROOT%" || exit /b 1
set "PYTHONPATH=%PROJECT_ROOT%src;%PYTHONPATH%"

if exist ".env.local" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env.local") do (
    if /i "%%A"=="JUP_CHAT_PROVIDER" if not defined JUP_CHAT_PROVIDER set "JUP_CHAT_PROVIDER=%%B"
    if /i "%%A"=="GROQ_MODEL" if not defined GROQ_MODEL set "GROQ_MODEL=%%B"
    if /i "%%A"=="GROQ_API_KEY" if not defined GROQ_API_KEY set "GROQ_API_KEY=%%B"
  )
)

where node >nul 2>nul || (
  echo Node nao encontrado. Instale Node 24 e tente novamente.
  popd
  exit /b 1
)

python --version || (
  popd
  exit /b 1
)
node web\scripts\build.mjs || (
  popd
  exit /b 1
)
python -m ai_service_desk web-demo --mode LOCAL_AI --host 127.0.0.1 --port 8000
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
