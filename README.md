# OBS Tools

Windows engineering tools for **Ocean Bottom Seismometer (OBS)** data simulation, TCP integration testing, and conversion of OBS USB binary logs to MiniSEED.

This repository contains the source used by the current operational OBS Tools build.

## Current baseline

| Component | Version | Purpose |
|---|---:|---|
| OBS Tools Launcher | v2.8 | Main application launcher |
| OBS TCP Simulator | v10.7 | Command/telemetry and raw ADC TCP simulator |
| BIN-to-MiniSEED Converter | v5.11 | Offline OBS USB BIN conversion to MiniSEED |

## Main capabilities

### OBS TCP Simulator

The simulator provides the two OBS TCP channels used by the runtime software:

- **TCP 54300** — command and telemetry
- **TCP 54301** — bulk raw ADC data

Raw ADC transport is fixed to:

| Channel | Physical meaning | MiniSEED seismic channel |
|---|---|---|
| CH0 | Geophone N | EHN |
| CH1 | Geophone E | EHE |
| CH2 | Geophone Z | EHZ |
| CH3 | AUX | Not exported as seismic waveform |

The TCP bulk payload preserves the original channel order:

```text
CH0, CH1, CH2, CH3
```

with **128 ADC frames × 4 channels = 512 words = 2048 bytes** per payload.

The simulator supports:

- generated ADC waveforms for integration tests;
- playback of actual OBS `.bin` files;
- automatic measured sample-rate calculation for BIN playback;
- depth, temperature, roll, pitch, and yaw telemetry sourced from BIN records;
- source-aware `XCHM1` behavior:
  - generated/control mode: `XCHM1` is transmitted;
  - BIN playback mode: `XCHM1` is not transmitted because VMON/controller-health fields are not present in the USB BIN record;
- UTC-based `TIME1`, OBS device time, and emulated USB BIN filenames.

### BIN-to-MiniSEED Converter

The converter reads OBS USB binary logs and produces MiniSEED seismic waveform files.

Operational rules:

- OBS timestamps and `OBS_YYYYMMDD_HHMMSS.bin` filenames are interpreted as **UTC**.
- Header sample rate is treated as nominal/reference information.
- Effective sample rate is measured automatically from:
  ```text
  delta(data_cnt) / delta(record UTC timestamp)
  ```
- Record timestamp semantics are locked to **record write time**.
- First-sample UTC is reconstructed from:
  ```text
  first record-write UTC - (frames_per_record - 1) / Measured Fs
  ```
- Continuous waveform timing follows `data_cnt + Measured Fs`.
- Gaps remain gaps; the converter does not zero-fill or resample the seismic waveform.
- MiniSEED waveform output contains only CH0/CH1/CH2 as EHN/EHE/EHZ.
- CH3/AUX remains available in the original source data but is not written as a seismic MiniSEED channel.

## Repository structure

```text
OBS Tool Bin Converter/
├── assets/
│   ├── icons/
│   └── logos/
├── main_tools_v2_8.py
├── OBS_SIM.py
├── obs_bin_to_miniseed.py
├── build_obs_tools_exe.bat
├── README_BUILD.txt
├── requirements.txt
├── .gitignore
└── README.md
```

## Requirements

Recommended environment:

- Windows 10 or Windows 11
- Python installed and available in `PATH`
- Git for source-control workflow

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

The current dependency set is:

- PySide6
- NumPy
- ObsPy
- PyInstaller

`tkinter` is used by the simulator and is normally included with the standard Windows Python installer.

## Run from source

From the repository directory:

```powershell
python .\main_tools_v2_8.py
```

The launcher can start the simulator and converter from the same source tree.

You can also run the tools individually:

```powershell
python .\OBS_SIM.py
python .\obs_bin_to_miniseed.py
```

## Build the Windows executable

A build script is already included:

```text
build_obs_tools_exe.bat
```

Run it from the repository folder:

```powershell
.\build_obs_tools_exe.bat
```

The script:

1. verifies the required source files;
2. checks Python and required packages;
3. removes previous PyInstaller output;
4. builds the application using **PyInstaller one-dir mode**;
5. runs launcher, simulator, and converter GUI smoke tests;
6. reports the final executable location.

Successful output:

```text
dist\OBS_TOOLS\OBS_TOOLS.exe
```

For deployment to another Windows PC, copy the **entire** folder:

```text
dist\OBS_TOOLS\
```

Do not copy only `OBS_TOOLS.exe`, because a PyInstaller one-dir build also requires the accompanying runtime files.

Python is not required on the target PC.

## Build configuration

The supplied build script intentionally uses:

- PyInstaller `--onedir`
- PySide6
- bundled OBS assets
- hidden imports for the simulator and converter
- ObsPy MiniSEED support
- exclusions for:
  - PyQt5
  - PyQt6
  - PySide2
  - legacy PySide

The Qt exclusions prevent multiple Qt bindings from being collected into the same executable build.

## BIN format compatibility

Current OBS firmware uses:

- 20-byte file header
- 30-byte packed record header
- 4 ADC channels
- 128 frames per record

A 34-byte record-header variant is retained in the tools only for compatibility with older documentation/logs.

For authoritative field definitions, use the firmware-side OBS binary log format specification applicable to the log being processed.

## Time policy

The current OBS Tools baseline uses UTC consistently:

```text
OBS device time  -> UTC
TIME1            -> UTC
BIN filename     -> UTC
BIN record time  -> UTC
MiniSEED output  -> UTC
```

No local timezone offset is added during BIN conversion.

## Git workflow

Initial repository setup:

```powershell
cd "C:\_RMI\2026\OBS\OBS Tool Bin Converter"

git init
git add .
git commit -m "Initial OBS Tools operational baseline"
git branch -M main
```

After creating an empty repository on GitHub, connect it:

```powershell
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

For subsequent updates:

```powershell
git status
git add .
git commit -m "Update OBS Tools"
git push
```

## Source-control policy

The repository intentionally excludes:

- `build/`
- `dist/`
- generated `.spec` files
- Python caches
- local virtual environments
- raw `.bin` recordings
- generated MiniSEED files
- local conversion outputs and logs

This keeps Git focused on source code, documentation, and application assets.

## Operational notes

Before processing or replaying operational data:

- verify the expected OBS BIN format;
- verify channel mapping CH0=N, CH1=E, CH2=Z, CH3=AUX;
- verify the UTC time basis;
- review the automatically measured sample rate;
- preserve source BIN files unchanged.

## Project status

This repository is intended for the OBS engineering and operational software workflow. Release binaries should be generated from a clean, committed source revision so that each executable build can be traced back to a specific Git commit.
