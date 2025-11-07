& .\venv\Scripts\Activate.ps1
pip install -r .\requirements.txt
flet pack .\main.py --name watl --onedir -y
Compress-Archive -Path .\dist\watl -DestinationPath .\watl.zip -Force
Read-Host "Press Enter to Exit..."