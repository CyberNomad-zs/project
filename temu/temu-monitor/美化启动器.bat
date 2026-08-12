@echo off
rem Graphical launcher - opens gui.py
cd /d "%~dp0."
where pythonw >nul 2>nul && ( start "" pythonw "gui.py" & goto :eof )
if exist "%LocalAppData%\Programs\Python\Python312\pythonw.exe" (
  start "" "%LocalAppData%\Programs\Python\Python312\pythonw.exe" "gui.py"
  goto :eof
)
where python >nul 2>nul && ( start "" python "gui.py" & goto :eof )
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  start "" "%LocalAppData%\Programs\Python\Python312\python.exe" "gui.py"
  goto :eof
)
py -3.12 "gui.py"
if errorlevel 1 (
  echo.
  echo  [ERR] Python not found. Install Python 3.12 or use start-menu.bat
  echo.
  pause
)
