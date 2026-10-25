@echo off
setlocal
cd /d "%~dp0"
set "UGLY_NODE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
if exist "..\..\work\receptionist-operator.mjs" if exist "%UGLY_NODE%" (
 "%UGLY_NODE%" --dns-result-order=ipv4first "..\..\work\receptionist-operator.mjs" development serve
 goto finished
)
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" -m streamlit run app.py --server.port=8510
 goto finished
)
echo Open README.md and follow the Python setup instructions first.
:finished
pause

