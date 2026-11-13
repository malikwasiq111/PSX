#!/usr/bin/env bash
cd "$(dirname "$0")" && pip install -r requirements.txt && cd BACKEND && uvicorn main:app --port 8000
