@echo off
cd /d "D:\AIagent项目"

rem Read the API key from the registry (works even without restarting the PC)
set "DEEPSEEK_API_KEY="
for /f "tokens=3" %%a in ('reg query "HKCU\Environment" /v DEEPSEEK_API_KEY 2^>nul') do set "DEEPSEEK_API_KEY=%%a"

if not defined DEEPSEEK_API_KEY (
    echo [WARN] DEEPSEEK_API_KEY not found in your environment.
    echo Run this once in a terminal:  setx DEEPSEEK_API_KEY "your-key"
    echo Then double-click this file again.
    pause
    exit /b 1
)

echo Starting the Code Repair Agent UI... browser will open automatically.
echo If it does not open, visit http://localhost:8501
python -m streamlit run app.py
pause
