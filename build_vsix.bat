@echo off
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is missing. Install Node.js, then run this file again.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm is missing. Install Node.js with npm, then run this file again.
  pause
  exit /b 1
)

echo Building Codex Linker VSIX...
call cmd /c npm install --no-save @vscode/vsce
if errorlevel 1 (
  echo Failed to install packaging tool.
  pause
  exit /b 1
)

call cmd /c npx @vscode/vsce package --allow-missing-repository
if errorlevel 1 (
  echo Failed to build VSIX.
  pause
  exit /b 1
)

echo.
echo Done.
echo The VSIX file is in this folder.
pause
