# Windows x64 build

Run `build.bat` on Windows using x64 CPython 3.12-3.14, an internet connection for the first dependency installation, and an interactive desktop for OpenGL validation. The tested toolchain is CPython 3.14.5 on Windows 11 x64. A GPU driver providing OpenGL 3.3 compatibility is required to play and validate the game. Linux cannot produce this Windows build.

```bat
windows_build\build.bat
```

The script works from any current directory, creates `windows_build/.venv`, checks architecture, installs the versions in `requirements-build.txt`, runs unit regressions, freezes the game with PyInstaller, validates the executable, and creates `WalkingTheWalk-windows-x64.zip` only after every check passes. Any failing command stops the build with a nonzero exit status. Existing build outputs are replaced on rebuild. Compilation and dependency installation are outside the ten-second *test-process* deadline.

Extract the ZIP and distribute the complete `WalkingTheWalk` folder, including `_internal`. Run `WalkingTheWalk.exe`; Python is not required on the target computer. The console is retained for the existing JSON diagnostics and tracebacks. Arguments such as `--windowed --width 1280 --height 800` and `--seed 42` work as in the source game. The build uses a folder distribution so spawned world-generation workers reuse bundled files without extracting another executable per worker.

`launcher.py` calls `multiprocessing.freeze_support()` before importing the game or parsing arguments. `WalkingTheWalk.manifest` declares PerMonitorV2 DPI awareness and ordinary user privileges. All artwork/font data are already embedded in the Python source; there are no asset paths relative to the working directory. The spec includes dynamically selected Win32 OpenGL and NumPy array adapters, with standard pygame/OpenGL/NumPy PyInstaller hooks collecting their libraries.

## Validation

```bat
python windows_build\run_validation.py
python windows_build\run_validation.py --unit-only
python windows_build\run_validation.py --exe windows_build\dist\WalkingTheWalk\WalkingTheWalk.exe --output doc\validation\windows-x64\packaged
```

Each unit batch and each desktop scenario has a ten-second external deadline. A deadline kills only that test's process tree, records failure, and retains its log. Title scenarios target four seconds and gameplay scenarios target seven seconds internally to leave time for imports and clean worker shutdown. Slower machines can fail this strict release gate even when the game itself works; logs distinguish timeout, loading error and failed assertion. An additional ordinary-launch probe runs the normal game CLI from an unrelated temporary working directory and sends WM_CLOSE to its own window, verifying a clean zero-status exit. Tests produce PNG screenshots and JSON/stdout logs. They use actual OpenGL and SDL mouse capture, with controlled held-key/mouse deltas and queued action events so background desktop focus does not make results random. Do not interact with a validation window during a run.

The opt-in `--validate` executable path is a diagnostic harness. Test inventory/cooldown fixtures exist only in that harness and are never applied by normal launch. Build outputs and the environment are ignored by Git; the scripts, report and current Windows evidence are tracked.
