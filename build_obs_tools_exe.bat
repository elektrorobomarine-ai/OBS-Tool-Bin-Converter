@echo off
setlocal EnableExtensions
title OBS TOOLS - BUILD EXE

cd /d "%~dp0"

echo ============================================================
echo OBS TOOLS - WINDOWS EXECUTABLE BUILD
echo ============================================================
echo.

set "MAIN=main_tools_v2_8.py"
set "SIM=OBS_SIM.py"
set "CONV=obs_bin_to_miniseed.py"
set "APP=OBS_TOOLS"

echo [1/6] Checking source files...
for %%F in ("%MAIN%" "%SIM%" "%CONV%") do (
    if not exist "%%~F" (
        echo ERROR: File tidak ditemukan: %%~F
        goto :fail
    )
)
echo Source files OK.
echo.

echo [2/6] Checking Python and packages...
python --version
if errorlevel 1 (
    echo ERROR: Python tidak ditemukan di PATH.
    goto :fail
)

python -c "import PyInstaller, PySide6, numpy, obspy; print('PyInstaller', PyInstaller.__version__); print('PySide6', PySide6.__version__); print('NumPy', numpy.__version__); print('ObsPy', obspy.__version__)"
if errorlevel 1 (
    echo.
    echo ERROR: Package build/runtime belum lengkap.
    echo Jalankan:
    echo   python -m pip install -U pyinstaller PySide6 numpy obspy
    goto :fail
)
echo.

echo [3/6] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist\%APP%" rmdir /s /q "dist\%APP%"
if exist "%APP%.spec" del /q "%APP%.spec"
echo Clean OK.
echo.

echo [4/6] Building %APP%.exe...
echo This can take several minutes.
echo.

set "ICON_OPT="
if exist "assets\icons\Prameya_rev.ico" (
    set "ICON_OPT=--icon=assets\icons\Prameya_rev.ico"
)

set "DATA_OPT="
if exist "assets" (
    set "DATA_OPT=--add-data=assets;assets"
)

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name "%APP%" ^
    --paths "%CD%" ^
    %ICON_OPT% ^
    %DATA_OPT% ^
    --hidden-import "%SIM:.py=%" ^
    --hidden-import "%CONV:.py=%" ^
    --hidden-import "obspy.io.mseed" ^
    --collect-all "obspy" ^
    --exclude-module "PyQt5" ^
    --exclude-module "PyQt6" ^
    --exclude-module "PySide2" ^
    --exclude-module "PySide" ^
    "%MAIN%"

if errorlevel 1 goto :fail

if not exist "dist\%APP%\%APP%.exe" (
    echo ERROR: EXE tidak terbentuk.
    goto :fail
)

echo.
echo [5/6] Running packaged GUI smoke tests...

"dist\%APP%\%APP%.exe" --self-test-gui
if errorlevel 1 (
    echo ERROR: Launcher GUI smoke test gagal.
    goto :fail
)

"dist\%APP%\%APP%.exe" --module simulator --self-test-gui
if errorlevel 1 (
    echo ERROR: Simulator GUI smoke test gagal.
    goto :fail
)

"dist\%APP%\%APP%.exe" --module converter --self-test-gui
if errorlevel 1 (
    echo ERROR: Converter GUI smoke test gagal.
    goto :fail
)

echo.
echo [6/6] BUILD PASSED
echo ============================================================
echo EXE:
echo   %CD%\dist\%APP%\%APP%.exe
echo.
echo Untuk PC target, copy SELURUH folder:
echo   %CD%\dist\%APP%
echo.
echo Python tidak diperlukan di PC target.
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo BUILD FAILED
echo ============================================================
echo Baca error di atas.
echo.
echo Jika ingin simpan log:
echo   build_obs_tools_exe.bat ^> build_error.txt 2^>^&1
echo.
pause
exit /b 1
