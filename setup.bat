@echo off
REM Double-click this once, the first time, to install what the tool needs.
cd /d "%~dp0"
echo Installing requirements...
echo.
where python >nul 2>nul && (python -m pip install -r requirements.txt & pause & goto :eof)
where py >nul 2>nul && (py -m pip install -r requirements.txt & pause & goto :eof)
if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" -m pip install -r requirements.txt
    pause
    goto :eof
)
echo Could not find Python. Install it from python.org/downloads first.
pause
