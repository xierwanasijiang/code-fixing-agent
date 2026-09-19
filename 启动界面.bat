@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ first.
    pause
    exit /b 1
)

python -c "import streamlit, openai, pytest" >nul 2>nul
if errorlevel 1 (
    echo Missing dependencies: streamlit / openai / pytest.
    set /p INSTALL=Install them now? [Y/N]:
    if /i "%INSTALL%"=="Y" (
        python -m pip install -r requirements.txt
    ) else (
        echo Cannot run without dependencies. Please run manually:
        echo     python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

python -m streamlit run app.py
pause
