@echo off
call .\venv\Scripts\activate
pip install -r requirements.txt
flet pack .\main.py --name watl --onedir -y
pause