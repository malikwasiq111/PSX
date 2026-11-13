@echo off
cd /d "%~dp0"
pip install -r requirements.txt
cd BACKEND
start "" http://127.0.0.1:8000
uvicorn main:app --port 8000
