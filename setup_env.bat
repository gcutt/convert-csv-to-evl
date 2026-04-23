@echo off
python3.12 -m venv .venv
REM python -m venv .venv
call .venv\Scripts\activate
REM pip install --upgrade pip
pip install -r requirements.txt
