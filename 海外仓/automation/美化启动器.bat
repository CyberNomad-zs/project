@echo off
rem Graphical launcher for the automation (opens gui.py in a window).
cd /d "%~dp0"
where pythonw >nul 2>nul && ( start "" pythonw "%~dp0gui.py" & goto :eof )
where python  >nul 2>nul && ( start "" python  "%~dp0gui.py" & goto :eof )
py -3.12 "%~dp0gui.py"
