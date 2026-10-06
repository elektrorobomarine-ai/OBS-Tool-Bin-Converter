OBS TOOLS - BUILD READY

Included baseline:
- main_tools_v2_8.py
- OBS_SIM.py              -> OBS TCP Simulator v10.7
- obs_bin_to_miniseed.py  -> BIN-to-MiniSEED Converter v5.11
- assets/
- build_obs_tools_exe.bat

Build:
1. Extract ZIP.
2. Open the extracted folder.
3. Double-click build_obs_tools_exe.bat
   or run it from Command Prompt.

Required on build PC:
- Python
- PyInstaller
- PySide6
- NumPy
- ObsPy

Output:
dist\OBS_TOOLS\OBS_TOOLS.exe

For another PC, copy the WHOLE folder:
dist\OBS_TOOLS\

The target PC does not need Python.

Build policy:
- ONE-DIR
- PySide6 retained
- PyQt5/PyQt6/PySide2/PySide excluded to avoid Qt-binding conflicts
- Simulator and converter are dispatched as separate child processes from the same EXE
