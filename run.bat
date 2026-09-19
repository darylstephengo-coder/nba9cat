@echo off
REM Double-click this file to start the 9-Cat Command Center.
cd /d "%~dp0"
echo Starting the draft tool...
echo.

REM Try each way of calling Python until one works.
where python >nul 2>nul && (python -m streamlit run app.py & goto :eof)
where py >nul 2>nul && (py -m streamlit run app.py & goto :eof)
if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" -m streamlit run app.py
    goto :eof
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" -m streamlit run app.py
    goto :eof
)

echo.
echo Could not find Python on this computer.
echo Install it from python.org/downloads and tick "Add python.exe to PATH".
pause
