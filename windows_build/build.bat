@echo off
setlocal
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
rem Use an isolated environment; never install over the developer's pygame.
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -m venv windows_build\.venv
if errorlevel 1 exit /b 1
goto environment_ready
:use_python
python -m venv windows_build\.venv
if errorlevel 1 exit /b 1
:environment_ready
set "BUILD_PYTHON=%CD%\windows_build\.venv\Scripts\python.exe"
"%BUILD_PYTHON%" -c "import sys,struct,platform; assert sys.platform == 'win32' and struct.calcsize('P') == 8 and platform.machine().upper() in ('AMD64','X86_64'), 'Build requires Windows x64 Python'; assert (3,12) <= sys.version_info[:2] <= (3,14), 'Use Python 3.12 through 3.14'"
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" -m pip install --only-binary=:all: -r windows_build\requirements-build.txt
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" -m pip check
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" -m PyInstaller --noconfirm --distpath windows_build\dist --workpath windows_build\build windows_build\WalkingTheWalk.spec
if errorlevel 1 exit /b 1
exit /b 0
