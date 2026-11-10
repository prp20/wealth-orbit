@echo off
setlocal
cd /d "%~dp0.."

where uv >nul 2>&1
if errorlevel 1 goto install_uv
goto have_uv

:install_uv
echo uv is not installed. It will install Python 3.13 for this project.
set /p INSTALL_UV=Install uv now? [Y/n] 
if /I "%INSTALL_UV%"=="n" goto no_uv
if /I "%INSTALL_UV%"=="no" goto no_uv
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

:have_uv
where node >nul 2>&1
if errorlevel 1 goto no_node
for /f "usebackq delims=" %%V in (`node -p "process.versions.node.split('.')[0]"`) do set NODE_MAJOR=%%V
if not defined NODE_MAJOR goto no_node
if %NODE_MAJOR% LSS 20 goto old_node

uv python install 3.13
if errorlevel 1 goto failed
uv sync
if errorlevel 1 goto failed
uv run python scripts\setup_guide.py
if errorlevel 1 goto failed
goto done

:no_uv
echo Install uv from https://docs.astral.sh/uv/ and run this script again.
pause
exit /b 1

:no_node
echo Node.js 20 or newer is required to build the UI.
echo winget install OpenJS.NodeJS.LTS
pause
exit /b 1

:old_node
echo Node.js 20 or newer is required. This machine has:
node -v
echo winget install OpenJS.NodeJS.LTS
pause
exit /b 1

:failed
echo Setup stopped because a step failed.
pause
exit /b 1

:done
pause
endlocal
