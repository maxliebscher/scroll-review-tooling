@echo off
setlocal

cd /d "%~dp0"

echo Starting Scroll Review Local App on 127.0.0.1...
echo This app is local-only. It does not upload data or run OCR/inference.
echo If the browser does not open, manually open http://127.0.0.1:8765/
python scripts\operator_server.py %*

endlocal
