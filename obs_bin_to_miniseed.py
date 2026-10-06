#!/usr/bin/env python3
"""
OBS Binary Log -> MiniSEED Converter
====================================
GRC-UGM-PERTAMINA OBS
Version: 5.11

Purpose
-------
Fast offline conversion of OBS onboard binary log files (.bin) into a
3-axis NEZ MiniSEED organization and UTC-hour archive:

    CH0 / N -> EHN (editable)
    CH1 / E -> EHE (editable)
    CH2 / Z -> EHZ (editable)
    CH3 / AUX -> intentionally not exported to waveform MiniSEED

Version 3 output layout (aligned with PC MiniSEED recorder v21):
    <base>/YYYY/YYYYMM/YYYYMMDD/YYYYMMDD_HH/
        <STATION>_N_<CH>_YYYYMMDD_HH_NN.mseed
        <STATION>_E_<CH>_YYYYMMDD_HH_NN.mseed
        <STATION>_Z_<CH>_YYYYMMDD_HH_NN.mseed
        record_sensors_YYYYMMDD_HH_NN.csv
        session_metadata_YYYYMMDD_HH_NN.json

HH is UTC. NN is selected by scanning existing files in the UTC-hour folder,
so repeated conversions never overwrite an existing recording set. Conversion
spanning a UTC-hour boundary is split into the corresponding hourly folders.

Output waveform format:
    - one MiniSEED file per OBS seismic N/E/Z component
    - INT32 ADC counts
    - STEIM2 lossless compression
    - 4096-byte MiniSEED records

The converter DOES NOT replay in real time. It reads binary logs as fast as
storage/CPU allow and preserves acquisition gaps as separate MiniSEED trace
segments. Missing samples are never fabricated.

Binary log source format
------------------------
File header: 20 bytes little-endian
    uint32 magic              0x4F425342 ("OBSB")
    uint32 version            1
    uint32 sample_rate_hz
    uint32 channels
    uint32 frames_per_record

Record header fields documented at offsets 0..29 (30-byte packed prefix):
    uint32 magic              0x4F425352 ("OBSR")
    uint32 data_cnt
    uint32 frame_base_idx
    uint8  hours, minutes, seconds, reserved
    uint16 milliseconds, reserved2, depth
    int16  temperature, roll, pitch, yaw

Current firmware validation (OBS_20260911_103602.bin) shows a 30-byte packed
record header followed immediately by the ADC payload. The converter therefore
treats 30 bytes as the CURRENT firmware format and retains 34-byte auto-detection
only for compatibility with the earlier text specification / possible variants.

Raw ADC samples are frame-major / channel-minor uint32 words. The OBS ADC bulk
protocol uses low 24 bits as signed 24-bit ADC counts and the high byte as ADC
status. MiniSEED receives the sign-extended low-24-bit value as INT32 counts.

Timestamp policy
----------------
The log contains time-of-day in each record and the date is inferred from the
standard filename OBS_YYYYMMDD_HHMMSS.bin.

Current OBS Runtime / MiniSEED Recording policy is UTC-locked:
    - all OBS timestamps are UTC
    - OBS_YYYYMMDD_HHMMSS.bin filenames are UTC
    - no local-time offset is applied by this converter

Within a continuous data-counter run, sample timing is generated from the
automatically measured BIN sample rate and data_cnt rather than repeated
record-header clock values. Header sample_rate_hz is retained as nominal/reference
metadata. A data_cnt gap/reset starts a new MiniSEED segment and anchors it to
that record's own RTC timestamp.

Version 3 keeps those reconstructed UTC sample timestamps for archive rotation.
Waveform samples are split exactly at UTC-hour boundaries before writing, so the
YYYY/YYYYMM/YYYYMMDD/YYYYMMDD_HH hierarchy follows the current PC MiniSEED
recorder v21 convention.

Current NEZ / timestamp policy:
    - CH0 remains physical data index 0 and is labeled N (North).
    - CH1 remains physical data index 1 and is labeled E (East).
    - CH2 remains physical data index 2 and is labeled Z (Vertical).
    - CH3 remains AUX in the source stream and is intentionally not exported.
    - Default MiniSEED codes are EHN / EHE / EHZ.
    - No seismic ADC samples are reordered, filtered, decimated, or rescaled.
    - The filename OBS_YYYYMMDD_HHMMSS.bin supplies the base UTC calendar date.
    - Each record header supplies UTC hours/minutes/seconds/milliseconds for the
      acquisition anchor. Within a continuous data_cnt run, exact sample timing is
      reconstructed from data_cnt + measured sample rate.
    - No timezone conversion is applied. Output folder/file YYYYMMDD_HH is UTC.

Dependencies
------------
    pip install PySide6 numpy obspy

No shared_data module and no network connection are required.

Version 4 modular integration:
    - Intended to be launched from the OBS Tools modular main window.
    - Window/taskbar branding uses assets/icons/Prameya_rev.png.
    - Binary parsing, timestamp reconstruction, NEZ mapping, MiniSEED writing,
      gap handling, archive hierarchy and conversion output are unchanged from v3.

Version 5 output-folder workflow:
    - Clicking CONVERT TO MINISEED first opens a folder-selection dialog.
    - The selected folder becomes the output base folder for that conversion.
    - Cancelling the folder dialog cancels the conversion before any files are written.
    - UTC archive hierarchy and all conversion/data-processing behavior are unchanged.

Version 5.1 modernizes the GUI only:
    - Compact marine-instrument header and modern card hierarchy.
    - Cleaner input table, metadata grid, timing/options cards and progress panel.
    - Responsive vertical scrolling is retained for smaller displays.
    - Conversion, binary parsing, NEZ mapping, timestamps, gap handling, archive
      hierarchy, metadata generation and ObsPy verification are unchanged from v5.

Version 5.2 hardening / self-test support:
    - Optional NumPy/ObsPy imports are type-checker friendly while preserving GUI fallback.
    - Windows AppUserModelID setup uses dynamic ctypes lookup.
    - Internal shadowed names and selected broad exception handlers are cleaned up.
    - Adds --self-test-gui for automated PySide6 GUI construction/event-loop smoke tests.
    - Conversion and MiniSEED data semantics are unchanged from v5.1.

Version 5.3 current-firmware alignment / QC:
    - 30-byte record header is the primary format verified from current firmware.
    - 34-byte record headers remain supported as a compatibility variant.
    - Fixes UTC month-folder creation after the v5.2 refactor.
    - Counts non-monotonic per-record RTC observations without using them to distort
      continuous waveform timing; data_cnt + sample rate remain authoritative.
    - Adds non-invasive ADC high-byte QC to metadata: raw status-byte frequencies,
      generic bit-set counts, and CH0..CH3 low-two-bit channel-ID sanity checks.
    - ADC-status QC never changes, filters, or rejects waveform samples.

Version 5.4 land-test alignment:
    - OBS naming is retained; no product rename to Prameya.
    - Seismic output semantics are CH0=X, CH1=Y, CH2=Z with default
      MiniSEED channel codes EH1, EH2 and EHZ.
    - CH3/AUX remains in the source BIN/parser for payload alignment and QC, but
      is intentionally NOT exported to waveform MiniSEED.
    - Adds optional Effective Sample Rate override. Default uses the BIN header;
      legacy sessions can be recovered with a measured rate such as 976.580 Hz.
    - Continuous waveform timing follows data_cnt + effective sample rate.

Version 5.5 NEZ output restoration:
    - Restores OBS seismic mapping to CH0=N, CH1=E, CH2=Z.
    - Default MiniSEED channel codes are EHN, EHE and EHZ.
    - CH3/AUX remains source-only and is intentionally not exported to MiniSEED.
    - Effective sample-rate override and current-firmware BIN handling are unchanged.

Version 5.6 automatic measured-sample-rate conversion:
    - Header/sample_rate_hz is retained as nominal/reference information only.
    - Measured Fs is calculated automatically from the BIN records using the
      same core relation as OBS Sampling Rate Checker v3:
          measured Fs = delta(data_cnt) / delta(record timestamp)
    - MiniSEED waveform timing and trace.stats.sampling_rate use the measured Fs.
    - Manual "Use sample rate from BIN header" and "Effective rate override"
      controls are removed from the GUI.
    - Header Fs, Measured Fs and deviation are displayed as read-only diagnostics.
    - Existing OBS RTC offset / timestamp-meaning controls are intentionally retained.
    - NEZ mapping and CH3/AUX exclusion are unchanged.

Version 5.7 MiniSEED2 sample-rate verification fix:
    - MiniSEED2 cannot represent every arbitrary decimal sampling rate exactly
      because its fixed header uses integer sample-rate factor/multiplier fields.
    - The converter still uses the automatically measured BIN Fs as the requested
      waveform rate. ObsPy/libmseed may store the nearest representable MiniSEED2 rate.
    - Read-back verification now accepts only small MiniSEED2 representation
      quantization instead of requiring impossible 1e-6 Hz equality.
    - The read-back rate and quantization delta are logged for traceability.
    - A real/large sampling-rate mismatch still raises an error.

Version 5.8 UTC-locked OBS USB-BIN timing:
    - Aligns offline BIN conversion with MiniSEED Recording v39 time policy.
    - HARD RULE: OBS timestamps and OBS_YYYYMMDD_HHMMSS.bin filenames are UTC.
    - Removes the obsolete "OBS RTC offset from UTC" GUI/configuration control.
    - BIN filename date and record HH:MM:SS.mmm are interpreted directly as UTC;
      no timezone addition/subtraction is applied during conversion.
    - Record timestamp meaning (first-sample vs last-sample/write-time) remains
      independently selectable because it describes record semantics, not timezone.
    - Measured-Fs, NEZ mapping, CH3/AUX exclusion, gap handling and MiniSEED2
      verification behavior are unchanged from v5.7.

Version 5.9 input-table UTC range display:
    - Replaces the redundant DATE column with FIRST RECORD UTC and LAST RECORD UTC.
    - Record UTC values come from the actual first/last valid BIN record headers,
      not merely from the filename.
    - Human-readable table timestamps use "YYYY-MM-DD HH:MM:SS.mmm UTC" with no
      ISO-8601 "T" separator.
    - Enables horizontal scrolling in the BIN input table so all diagnostic columns
      remain readable on smaller displays.

Version 5.10 locked record-write-time semantics:
    - Removes the operator-selectable record timestamp meaning.
    - BINARY_LOG_FORMAT defines record HH:MM:SS.mmm as the time "when record was written".
    - The record UTC therefore anchors the end of the 128-frame block.
    - First-sample UTC is reconstructed automatically as:
          record_write_utc - (frames_per_record - 1) / measured Fs
    - Continuous waveform timing remains authoritative from data_cnt + measured Fs.
    - UTC policy, measured-Fs analysis, NEZ mapping and CH3/AUX exclusion are unchanged.

Version 5.11 operational waveform-coverage display:
    - Input table now shows FIRST SAMPLE UTC and LAST SAMPLE UTC for operational use.
    - FIRST SAMPLE UTC = first record-write UTC - (frames_per_record - 1) / measured Fs.
    - LAST SAMPLE UTC = last record-write UTC under the locked record-write-time semantics.
    - Record-write UTC anchors remain available internally in metadata for audit.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import struct
import sys
import threading
import traceback
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional


# =============================================================================
# Optional runtime dependencies
# =============================================================================

np: Any = None
NUMPY_AVAILABLE = False
NUMPY_ERROR = ""

try:
    import numpy as _numpy
except (ImportError, OSError) as numpy_import_error:  # pragma: no cover
    NUMPY_ERROR = str(numpy_import_error)
else:
    np = _numpy
    NUMPY_AVAILABLE = True

Stream: Any = None
Trace: Any = None
UTCDateTime: Any = None
obspy_read: Any = None
OBSPY_AVAILABLE = False
OBSPY_ERROR = ""

try:
    from obspy import (
        Stream as _ObsPyStream,
        Trace as _ObsPyTrace,
        UTCDateTime as _ObsPyUTCDateTime,
        read as _obspy_read,
    )
except (ImportError, OSError) as obspy_import_error:  # pragma: no cover
    OBSPY_ERROR = str(obspy_import_error)
else:
    Stream = _ObsPyStream
    Trace = _ObsPyTrace
    UTCDateTime = _ObsPyUTCDateTime
    obspy_read = _obspy_read
    OBSPY_AVAILABLE = True

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def connect_signal(signal_object: Any, slot: Callable[..., Any]) -> None:
    """Connect a Qt bound signal without exposing descriptor internals to static analyzers."""
    signal_object.connect(slot)


# =============================================================================
# Reliable double spin box
# =============================================================================

class ReliableDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox with explicit UP/DOWN buttons for Windows/PySide6.

    The native spin-arrow hit regions can disagree with the glyph positions after
    application styling. Explicit child buttons make mouse stepping deterministic
    while preserving QDoubleSpinBox keyboard, wheel, range, decimal and signal
    semantics.
    """

    _BUTTON_WIDTH = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setAccelerated(True)
        self._spin_up_button = QToolButton(self)
        self._spin_down_button = QToolButton(self)
        self._spin_up_button.setText("▲")
        self._spin_down_button.setText("▼")
        for button in (self._spin_up_button, self._spin_down_button):
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(350)
            button.setAutoRepeatInterval(75)
            button.setStyleSheet(
                """
                QToolButton {
                    background-color: #0E2533;
                    color: #DDEAF2;
                    border: 0px;
                    border-left: 1px solid #24485D;
                    padding: 0px;
                    margin: 0px;
                    font-size: 9px;
                }
                QToolButton:hover { background-color: #17384B; color: #FFFFFF; }
                QToolButton:pressed { background-color: #245B79; color: #FFFFFF; }
                QToolButton:disabled { color: #526B78; background-color: #0A1A24; }
                """
            )
        self._spin_down_button.setStyleSheet(
            self._spin_down_button.styleSheet()
            + "QToolButton { border-top: 1px solid #24485D; }"
        )
        self._spin_up_button.clicked.connect(self._explicit_step_up)
        self._spin_down_button.clicked.connect(self._explicit_step_down)
        self._layout_spin_buttons()

    def _explicit_step_up(self) -> None:
        if self.isEnabled() and not self.isReadOnly():
            self.stepUp()

    def _explicit_step_down(self) -> None:
        if self.isEnabled() and not self.isReadOnly():
            self.stepDown()

    def _layout_spin_buttons(self) -> None:
        width = min(self._BUTTON_WIDTH, max(20, self.height() - 2))
        height = max(2, self.height() - 2)
        upper_height = max(1, height // 2)
        lower_height = max(1, height - upper_height)
        x = max(0, self.width() - width - 1)
        self._spin_up_button.setGeometry(x, 1, width, upper_height)
        self._spin_down_button.setGeometry(x, 1 + upper_height, width, lower_height)
        edit = self.lineEdit()
        if edit is not None:
            edit.setTextMargins(0, 0, width + 3, 0)
        self._spin_up_button.raise_()
        self._spin_down_button.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_spin_buttons()

    def setReadOnly(self, read_only: bool) -> None:
        super().setReadOnly(read_only)
        enabled = not bool(read_only)
        if hasattr(self, "_spin_up_button"):
            self._spin_up_button.setEnabled(enabled)
        if hasattr(self, "_spin_down_button"):
            self._spin_down_button.setEnabled(enabled)


# =============================================================================
# Application constants
# =============================================================================

APP_TITLE = "OBS Binary Log to MiniSEED Converter"
APP_VERSION = "5.11"
APP_USER_MODEL_ID = "GRC.UGM.PERTAMINA.OBS.BIN2MSEED"

BASE_DIR = Path(__file__).resolve().parent
ICON_DIR = BASE_DIR / "assets" / "icons"
APP_ICON_PNG = ICON_DIR / "Prameya_rev.png"

DEFAULT_NETWORK = "RM"
DEFAULT_STATION = "OBS01"
DEFAULT_LOCATION = "00"
DEFAULT_N_CHANNEL = "EHN"
DEFAULT_E_CHANNEL = "EHE"
DEFAULT_Z_CHANNEL = "EHZ"

MSEED_RECLEN = 4096
MSEED_ENCODING = "STEIM2"

# MiniSEED2 encodes sample rate using signed 16-bit integer factor/multiplier
# fields, so an arbitrary measured decimal Fs cannot always survive write/read
# with exact floating-point equality. Keep this tolerance tight enough to catch
# a real wrong-rate file while allowing normal MiniSEED2 representation error.
MSEED_RATE_VERIFY_ABS_TOL_HZ = 0.01
MSEED_RATE_VERIFY_REL_TOL = 1.0e-5

FILE_MAGIC = 0x4F425342
RECORD_MAGIC = 0x4F425352
FORMAT_VERSION = 1

FILE_HEADER = struct.Struct("<IIIII")
assert FILE_HEADER.size == 20

# Current firmware stores exactly the documented packed fields: 30 bytes.
# Keep 34-byte support for compatibility with the earlier text specification.
RECORD_FIELDS = struct.Struct("<III4BHHHhhhh")
assert RECORD_FIELDS.size == 30
RECORD_HEADER_SIZE_CURRENT = 30
RECORD_HEADER_SIZE_COMPAT = 34

FILENAME_RE = re.compile(r"^OBS_(\d{8})_(\d{6})\.bin$", re.IGNORECASE)

# Keep memory bounded while still generating efficient MiniSEED batches.
DEFAULT_FLUSH_SECONDS = 30.0
MAX_FLUSH_SAMPLES = 250_000


# =============================================================================
# Windows application identity / icon
# =============================================================================

def configure_windows_runtime() -> None:
    if os.name != "nt":
        return

    try:
        import ctypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            return
        shell32 = win_dll("shell32", use_last_error=True)
        setter = getattr(shell32, "SetCurrentProcessExplicitAppUserModelID", None)
        if setter is None:
            return
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        setter(APP_USER_MODEL_ID)
    except (OSError, AttributeError, TypeError):
        return


def application_icon() -> QIcon:
    """Use the Prameya artwork consistently for the converter window/taskbar."""
    if APP_ICON_PNG.is_file():
        icon = QIcon(str(APP_ICON_PNG))
        if not icon.isNull():
            return icon
    return QIcon()


configure_windows_runtime()


# =============================================================================
# Data structures
# =============================================================================

@dataclass(frozen=True)
class BinaryLogHeader:
    path: str
    version: int
    sample_rate_hz: int
    channels: int
    frames_per_record: int
    record_header_size: int
    payload_bytes: int
    estimated_records: int
    file_size: int
    filename_datetime: Optional[str]
    measured_sample_rate_hz: Optional[float] = None
    rate_deviation_percent: Optional[float] = None
    measured_rate_duration_s: Optional[float] = None
    measured_rate_frame_delta: Optional[int] = None
    rate_measurement_records: int = 0
    first_record_write_utc: Optional[str] = None
    last_record_write_utc: Optional[str] = None
    first_sample_utc: Optional[str] = None
    last_sample_utc: Optional[str] = None

    @property
    def record_bytes(self) -> int:
        return int(self.record_header_size + self.payload_bytes)

    @property
    def estimated_frames(self) -> int:
        return int(self.estimated_records * self.frames_per_record)

    @property
    def estimated_duration_s(self) -> float:
        rate = (
            float(self.measured_sample_rate_hz)
            if self.measured_sample_rate_hz is not None
            else float(self.sample_rate_hz)
        )
        if rate <= 0:
            return 0.0
        return float(self.estimated_frames) / rate


@dataclass(frozen=True)
class BinaryLogRecord:
    file_path: str
    file_record_index: int
    absolute_offset: int
    data_cnt: int
    frame_base_idx: int
    hours: int
    minutes: int
    seconds: int
    milliseconds: int
    depth_m: float
    temperature_c: float
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    payload: bytes


@dataclass(frozen=True)
class ConverterConfig:
    input_files: tuple[str, ...]
    output_base_folder: str
    network: str
    station: str
    location: str
    n_channel: str
    e_channel: str
    z_channel: str
    write_sensor_csv: bool
    write_metadata_json: bool
    verify_output: bool


@dataclass
class ConversionStats:
    input_files: int = 0
    records_read: int = 0
    records_written: int = 0
    frames_written: int = 0
    gaps_detected: int = 0
    gap_frames: int = 0
    counter_resets: int = 0
    resync_events: int = 0
    truncated_tails: int = 0
    bytes_mseed: int = 0
    segments_started: int = 0
    trace_chunks_written: int = 0
    rtc_nonmonotonic_records: int = 0
    adc_status_channel_id_mismatches: int = 0


# =============================================================================
# Binary log parsing helpers
# =============================================================================

def parse_filename_datetime(path: str | Path) -> Optional[datetime]:
    name = Path(path).name
    match = FILENAME_RE.match(name)
    if not match:
        return None
    try:
        return datetime.strptime(
            match.group(1) + match.group(2),
            "%Y%m%d%H%M%S",
        )
    except ValueError:
        return None


def sort_input_paths(paths: Iterable[str]) -> list[str]:
    def key(path: str):
        dt = parse_filename_datetime(path)
        if dt is not None:
            return 0, dt, Path(path).name.lower()
        try:
            return (
                1,
                datetime.fromtimestamp(Path(path).stat().st_mtime),
                Path(path).name.lower(),
            )
        except OSError:
            return 2, datetime.max, Path(path).name.lower()

    return sorted({str(Path(p).resolve()) for p in paths}, key=key)


def _detect_record_header_size(
    handle,
    *,
    file_size: int,
    payload_bytes: int,
) -> int:
    data_bytes = max(0, int(file_size) - FILE_HEADER.size)
    candidates = (RECORD_HEADER_SIZE_CURRENT, RECORD_HEADER_SIZE_COMPAT)
    marker = struct.pack("<I", RECORD_MAGIC)

    exact = [
        size
        for size in candidates
        if data_bytes > 0 and data_bytes % (size + payload_bytes) == 0
    ]
    if len(exact) == 1:
        return exact[0]

    matched = []
    for size in candidates:
        second_offset = FILE_HEADER.size + size + payload_bytes
        if second_offset + 4 <= file_size:
            handle.seek(second_offset)
            if handle.read(4) == marker:
                matched.append(size)
    if len(matched) == 1:
        return matched[0]

    return RECORD_HEADER_SIZE_CURRENT


def inspect_binary_log(path: str | Path) -> BinaryLogHeader:
    path = str(Path(path).resolve())
    file_size = os.path.getsize(path)

    with open(path, "rb") as handle:
        raw = handle.read(FILE_HEADER.size)
        if len(raw) != FILE_HEADER.size:
            raise ValueError("File lebih pendek dari header OBS 20 byte.")

        magic, version, sample_rate, channels, frames_per_record = (
            FILE_HEADER.unpack(raw)
        )

        if magic != FILE_MAGIC:
            raise ValueError(
                f"Magic file 0x{magic:08X} tidak valid; "
                f"harus 0x{FILE_MAGIC:08X} (OBSB)."
            )
        if version != FORMAT_VERSION:
            raise ValueError(
                f"Format version {version} belum didukung; expected 1."
            )
        if sample_rate <= 0:
            raise ValueError("sample_rate_hz harus > 0.")
        if channels < 3:
            raise ValueError(
                f"Log hanya memiliki {channels} channel; converter 3-axis "
                "memerlukan minimal CH0/CH1/CH2."
            )
        if frames_per_record <= 0:
            raise ValueError("frames_per_record tidak valid.")

        payload_bytes = int(channels * frames_per_record * 4)
        record_header_size = _detect_record_header_size(
            handle,
            file_size=file_size,
            payload_bytes=payload_bytes,
        )
        record_bytes = record_header_size + payload_bytes
        estimated = max(
            0,
            (file_size - FILE_HEADER.size) // record_bytes,
        )

    file_dt = parse_filename_datetime(path)
    header = BinaryLogHeader(
        path=path,
        version=int(version),
        sample_rate_hz=int(sample_rate),
        channels=int(channels),
        frames_per_record=int(frames_per_record),
        record_header_size=int(record_header_size),
        payload_bytes=int(payload_bytes),
        estimated_records=int(estimated),
        file_size=int(file_size),
        filename_datetime=(
            file_dt.isoformat(timespec="seconds") if file_dt else None
        ),
    )

    rate_info = measure_binary_log_sample_rate(header)
    return replace(
        header,
        measured_sample_rate_hz=rate_info["measured_sample_rate_hz"],
        rate_deviation_percent=rate_info["rate_deviation_percent"],
        measured_rate_duration_s=rate_info["measured_rate_duration_s"],
        measured_rate_frame_delta=rate_info["measured_rate_frame_delta"],
        rate_measurement_records=rate_info["rate_measurement_records"],
        first_record_write_utc=rate_info["first_record_write_utc"],
        last_record_write_utc=rate_info["last_record_write_utc"],
        first_sample_utc=rate_info["first_sample_utc"],
        last_sample_utc=rate_info["last_sample_utc"],
    )


def _resync_to_record_magic(handle, start_pos: int) -> Optional[int]:
    marker = struct.pack("<I", RECORD_MAGIC)
    handle.seek(start_pos)
    overlap = b""
    absolute = start_pos

    while True:
        chunk = handle.read(64 * 1024)
        if not chunk:
            return None
        data = overlap + chunk
        index = data.find(marker)
        if index >= 0:
            found = absolute - len(overlap) + index
            handle.seek(found)
            return found
        overlap = data[-3:]
        absolute += len(chunk)


def measure_binary_log_sample_rate(header: BinaryLogHeader) -> dict:
    """Measure actual BIN Fs from data_cnt versus record timestamp.

    Core relation intentionally matches OBS Sampling Rate Checker v3:

        measured Fs = delta(data_cnt) / delta(record timestamp)

    The file-header sample_rate_hz remains nominal/reference metadata only.
    OBS filename and record timestamps are UTC. Because this measurement uses
    only timestamp differences, no timezone conversion is involved.
    """
    base_dt = parse_filename_datetime(header.path)
    if base_dt is None:
        return {
            "measured_sample_rate_hz": None,
            "rate_deviation_percent": None,
            "measured_rate_duration_s": None,
            "measured_rate_frame_delta": None,
            "rate_measurement_records": 0,
            "first_record_write_utc": None,
            "last_record_write_utc": None,
            "first_sample_utc": None,
            "last_sample_utc": None,
        }

    first_dt = None
    last_dt = None
    first_cnt = None
    last_cnt = None
    previous_dt = None
    valid_timestamp_records = 0

    with open(header.path, "rb") as handle:
        handle.seek(FILE_HEADER.size)

        while True:
            record_offset = handle.tell()
            raw_header = handle.read(header.record_header_size)

            if not raw_header:
                break
            if len(raw_header) < header.record_header_size:
                break

            fields = RECORD_FIELDS.unpack(raw_header[: RECORD_FIELDS.size])
            (
                magic,
                data_cnt,
                _frame_base_idx,
                hours,
                minutes,
                seconds,
                _reserved,
                milliseconds,
                _reserved2,
                _depth_raw,
                _temp_raw,
                _roll_raw,
                _pitch_raw,
                _yaw_raw,
            ) = fields

            if magic != RECORD_MAGIC:
                found = _resync_to_record_magic(handle, record_offset + 1)
                if found is None:
                    break
                continue

            # Skip ADC payload efficiently; sampling-rate measurement needs only
            # record timestamps and data_cnt.
            payload_end = handle.tell() + header.payload_bytes
            if payload_end > header.file_size:
                break
            handle.seek(header.payload_bytes, os.SEEK_CUR)

            if not (
                0 <= int(hours) <= 23
                and 0 <= int(minutes) <= 59
                and 0 <= int(seconds) <= 59
                and 0 <= int(milliseconds) <= 999
            ):
                continue

            candidate = datetime(
                base_dt.year,
                base_dt.month,
                base_dt.day,
                int(hours),
                int(minutes),
                int(seconds),
                int(milliseconds) * 1000,
            )

            # Same midnight-rollover rule used by Sampling Rate Checker v3.
            if previous_dt is not None and candidate < previous_dt - timedelta(hours=12):
                while candidate < previous_dt - timedelta(hours=12):
                    candidate += timedelta(days=1)

            if first_dt is None:
                first_dt = candidate
                first_cnt = int(data_cnt)

            last_dt = candidate
            last_cnt = int(data_cnt)
            previous_dt = candidate
            valid_timestamp_records += 1

    if (
        first_dt is None
        or last_dt is None
        or first_cnt is None
        or last_cnt is None
        or valid_timestamp_records < 2
    ):
        measured = None
        duration_s = None
        frame_delta = None
        deviation = None
    else:
        duration_s = float((last_dt - first_dt).total_seconds())
        frame_delta = int(last_cnt) - int(first_cnt)

        if duration_s > 0.0 and frame_delta > 0:
            measured = float(frame_delta) / duration_s
            deviation = (
                (measured - float(header.sample_rate_hz))
                / float(header.sample_rate_hz)
                * 100.0
            )
        else:
            measured = None
            deviation = None

    def _display_utc(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"

    first_sample_dt = None
    last_sample_dt = None
    if (
        measured is not None
        and measured > 0.0
        and first_dt is not None
        and last_dt is not None
    ):
        first_sample_dt = first_dt - timedelta(
            seconds=max(0, int(header.frames_per_record) - 1) / float(measured)
        )
        last_sample_dt = last_dt

    return {
        "measured_sample_rate_hz": measured,
        "rate_deviation_percent": deviation,
        "measured_rate_duration_s": duration_s,
        "measured_rate_frame_delta": frame_delta,
        "rate_measurement_records": int(valid_timestamp_records),
        "first_record_write_utc": _display_utc(first_dt),
        "last_record_write_utc": _display_utc(last_dt),
        "first_sample_utc": _display_utc(first_sample_dt),
        "last_sample_utc": _display_utc(last_sample_dt),
    }


def iter_binary_records(
    header: BinaryLogHeader,
    *,
    event_cb=None,
):
    """Yield BinaryLogRecord objects; resync after corrupted record magic."""
    path = header.path
    with open(path, "rb") as handle:
        handle.seek(FILE_HEADER.size)
        record_index = 0

        while True:
            start_pos = handle.tell()
            raw_header = handle.read(header.record_header_size)

            if len(raw_header) == 0:
                return
            if len(raw_header) < header.record_header_size:
                if event_cb:
                    event_cb(
                        "truncated",
                        f"Truncated record header: {Path(path).name} "
                        f"offset {start_pos}",
                    )
                return

            fields = RECORD_FIELDS.unpack(
                raw_header[: RECORD_FIELDS.size]
            )
            (
                magic,
                data_cnt,
                frame_base_idx,
                hours,
                minutes,
                seconds,
                _reserved,
                milliseconds,
                _reserved2,
                depth_raw,
                temp_raw,
                roll_raw,
                pitch_raw,
                yaw_raw,
            ) = fields

            if magic != RECORD_MAGIC:
                found = _resync_to_record_magic(handle, start_pos + 1)
                if event_cb:
                    event_cb(
                        "resync",
                        (
                            f"Record magic mismatch: {Path(path).name} "
                            f"offset {start_pos}; "
                            + (
                                f"resync -> {found}"
                                if found is not None
                                else "tidak menemukan record berikutnya"
                            )
                        ),
                    )
                if found is None:
                    return
                continue

            payload = handle.read(header.payload_bytes)
            if len(payload) != header.payload_bytes:
                if event_cb:
                    event_cb(
                        "truncated",
                        f"Truncated payload: {Path(path).name} "
                        f"record {record_index + 1}",
                    )
                return

            record_index += 1
            yield BinaryLogRecord(
                file_path=path,
                file_record_index=record_index,
                absolute_offset=start_pos,
                data_cnt=int(data_cnt),
                frame_base_idx=int(frame_base_idx),
                hours=int(hours),
                minutes=int(minutes),
                seconds=int(seconds),
                milliseconds=int(milliseconds),
                depth_m=float(depth_raw) * 0.1,
                temperature_c=float(temp_raw) * 0.01,
                roll_deg=float(roll_raw) * 0.1,
                pitch_deg=float(pitch_raw) * 0.1,
                yaw_deg=float(yaw_raw) * 0.1,
                payload=payload,
            )


def decode_nez_counts(
    payload: bytes,
    *,
    frames_per_record: int,
    channels: int,
):
    if np is None:
        raise RuntimeError("NumPy tidak tersedia.")

    expected_words = int(frames_per_record * channels)
    words = np.frombuffer(payload, dtype="<u4", count=expected_words)
    if words.size != expected_words:
        raise ValueError(
            f"Payload hanya {words.size} words; expected {expected_words}."
        )

    words = words.reshape(frames_per_record, channels)
    low24 = np.bitwise_and(words[:, :3], np.uint32(0x00FFFFFF))
    values = low24.astype(np.int32, copy=True)
    negative = np.not_equal(
        np.bitwise_and(low24, np.uint32(0x00800000)),
        np.uint32(0),
    )
    values[negative] -= np.int32(1 << 24)

    return (
        np.ascontiguousarray(values[:, 0], dtype=np.int32),
        np.ascontiguousarray(values[:, 1], dtype=np.int32),
        np.ascontiguousarray(values[:, 2], dtype=np.int32),
    )


def decode_status_bytes(
    payload: bytes,
    *,
    frames_per_record: int,
    channels: int,
):
    if np is None:
        raise RuntimeError("NumPy tidak tersedia.")
    words = np.frombuffer(
        payload,
        dtype="<u4",
        count=frames_per_record * channels,
    ).reshape(frames_per_record, channels)
    return np.right_shift(words, np.uint32(24)).astype(np.uint8, copy=False)


def create_adc_status_qc(channels: int) -> dict:
    """Create non-invasive QC counters for the raw ADC high/status byte.

    The current firmware observation for CH0..CH3 is that the low two bits track
    the channel index. Other bits are reported generically without assigning an
    undocumented semantic meaning here.
    """
    return {
        "basis": (
            "Raw high byte from each 32-bit ADC word. For CH0..CH3 only, "
            "(status & 0x03) is checked against the channel index. Bits 2..7 "
            "are counted generically; waveform samples are never modified by QC."
        ),
        "total_status_words": 0,
        "channel_id_mismatches": 0,
        "per_channel": [
            {
                "channel_index": int(channel_index),
                "samples": 0,
                "channel_id_mismatches": 0,
                "raw_status_counts": {},
                "bit_set_counts": {
                    f"bit{bit}": 0 for bit in range(2, 8)
                },
            }
            for channel_index in range(int(channels))
        ],
    }


def update_adc_status_qc(qc: dict, status_bytes) -> None:
    """Accumulate ADC high-byte QC without changing waveform data."""
    if np is None:
        raise RuntimeError("NumPy tidak tersedia.")

    matrix = np.asarray(status_bytes, dtype=np.uint8)
    if matrix.ndim != 2:
        raise ValueError("ADC status matrix harus 2-dimensional.")

    rows, columns = matrix.shape
    qc["total_status_words"] += int(rows * columns)

    per_channel = qc["per_channel"]
    for channel_index in range(min(columns, len(per_channel))):
        channel_qc = per_channel[channel_index]
        values = matrix[:, channel_index]
        channel_qc["samples"] += int(values.size)

        unique_values, unique_counts = np.unique(values, return_counts=True)
        raw_counts = channel_qc["raw_status_counts"]
        for status_value, count in zip(unique_values, unique_counts):
            key = f"0x{int(status_value):02X}"
            raw_counts[key] = int(raw_counts.get(key, 0)) + int(count)

        # Verified current-firmware observation for CH0..CH3 only.
        if channel_index < 4:
            mismatch_count = int(
                np.count_nonzero(
                    np.bitwise_and(values, np.uint8(0x03))
                    != np.uint8(channel_index)
                )
            )
            channel_qc["channel_id_mismatches"] += mismatch_count
            qc["channel_id_mismatches"] += mismatch_count

        bit_counts = channel_qc["bit_set_counts"]
        for bit in range(2, 8):
            bit_counts[f"bit{bit}"] += int(
                np.count_nonzero(
                    np.bitwise_and(values, np.uint8(1 << bit))
                )
            )


# =============================================================================
# Timestamp helpers
# =============================================================================

def record_utc_datetime(
    record: BinaryLogRecord,
    *,
    base_date: date,
    day_rollover: int,
) -> datetime:
    """Build the record anchor as an explicit UTC datetime.

    OBS Runtime v39 policy locks both OBS timestamps and BIN filenames to UTC,
    so no timezone offset conversion is permitted here.
    """
    current_date = base_date + timedelta(days=day_rollover)
    return datetime(
        current_date.year,
        current_date.month,
        current_date.day,
        record.hours,
        record.minutes,
        record.seconds,
        record.milliseconds * 1000,
        tzinfo=timezone.utc,
    )


def utc_datetime_to_timestamp_ns(dt_utc: datetime) -> int:
    """Convert an OBS UTC datetime directly to Unix nanoseconds."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt_utc.astimezone(timezone.utc)
    return int(round(dt_utc.timestamp() * 1_000_000_000.0))


def record_write_time_to_first_sample_ns(
    record_write_ns: int,
    *,
    sample_rate_hz: float,
    frames_per_record: int,
) -> int:
    """Convert the BIN record-write UTC anchor to first-sample UTC.

    BINARY_LOG_FORMAT defines record HH:MM:SS.mmm as the time when the record
    was written. The record contains frames_per_record ADC frames, so the first
    frame precedes the record-write/last-frame anchor by (N - 1) / Fs.
    """
    duration_ns = int(
        round(
            max(0, int(frames_per_record) - 1)
            / float(sample_rate_hz)
            * 1_000_000_000.0
        )
    )
    return int(record_write_ns - duration_ns)


# =============================================================================
# MiniSEED helpers
# =============================================================================

def safe_code(value: str, *, max_len: int, field_name: str) -> str:
    value = str(value).strip().upper()
    if not value:
        raise ValueError(f"{field_name} tidak boleh kosong.")
    if len(value) > max_len:
        raise ValueError(
            f"{field_name} maksimal {max_len} karakter untuk MiniSEED2."
        )
    if not re.fullmatch(r"[A-Z0-9]+", value):
        raise ValueError(
            f"{field_name} hanya boleh berisi huruf A-Z dan angka 0-9."
        )
    return value


def validate_channel(value: str, field_name: str) -> str:
    value = safe_code(value, max_len=3, field_name=field_name)
    if len(value) != 3:
        raise ValueError(f"{field_name} harus tepat 3 karakter.")
    return value


def append_miniseed_trace(
    path: Path,
    data,
    *,
    network: str,
    station: str,
    location: str,
    channel: str,
    start_ns: int,
    sample_rate_hz: float,
) -> int:
    if not OBSPY_AVAILABLE:
        raise RuntimeError(f"ObsPy tidak tersedia: {OBSPY_ERROR}")

    trace = Trace(data=np.asarray(data, dtype=np.int32))
    trace.stats.network = network
    trace.stats.station = station
    trace.stats.location = location
    trace.stats.channel = channel
    trace.stats.starttime = UTCDateTime(start_ns / 1_000_000_000.0)
    trace.stats.sampling_rate = float(sample_rate_hz)
    trace.stats.mseed = {"dataquality": "D"}

    stream = Stream(traces=[trace])
    buffer = io.BytesIO()
    stream.write(
        buffer,
        format="MSEED",
        encoding=MSEED_ENCODING,
        reclen=MSEED_RECLEN,
    )
    payload = buffer.getvalue()
    with path.open("ab") as handle:
        handle.write(payload)
    return len(payload)


# =============================================================================
# Conversion worker
# =============================================================================

class ConversionWorker(QThread):
    progress_changed = Signal(int, int, str)
    log_message = Signal(str)
    finished_ok = Signal(str, object)
    failed = Signal(str)

    def __init__(self, config: ConverterConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()
        self.requestInterruption()

    def _check_cancel(self):
        if self._cancel.is_set() or self.isInterruptionRequested():
            raise InterruptedError("Conversion cancelled by user.")

    def _event(self, kind: str, message: str, stats: ConversionStats):
        if kind == "resync":
            stats.resync_events += 1
        elif kind == "truncated":
            stats.truncated_tails += 1
        self.log_message.emit(message)

    def run(self):
        try:
            output = self._convert()
            self.finished_ok.emit(output[0], output[1])
        except InterruptedError as interrupted:
            self.failed.emit(str(interrupted))
        # noinspection PyBroadException
        except Exception:
            # Worker boundary: convert every unexpected failure into a GUI signal.
            self.failed.emit(traceback.format_exc())

    def _convert(self):
        if not NUMPY_AVAILABLE:
            raise RuntimeError(f"NumPy tidak tersedia: {NUMPY_ERROR}")
        if not OBSPY_AVAILABLE:
            raise RuntimeError(f"ObsPy tidak tersedia: {OBSPY_ERROR}")

        cfg = self.config
        paths = sort_input_paths(cfg.input_files)
        if not paths:
            raise ValueError("Tidak ada file input.")

        headers = [inspect_binary_log(path) for path in paths]
        first = headers[0]

        for header in headers[1:]:
            if (
                header.sample_rate_hz != first.sample_rate_hz
                or header.channels != first.channels
                or header.frames_per_record != first.frames_per_record
            ):
                raise ValueError(
                    "Semua file dalam satu conversion harus memiliki "
                    "sample rate, channel count, dan frames/record yang sama.\n\n"
                    f"Reference: Fs={first.sample_rate_hz}, ch={first.channels}, "
                    f"frames={first.frames_per_record}\n"
                    f"Mismatch : {Path(header.path).name}: "
                    f"Fs={header.sample_rate_hz}, ch={header.channels}, "
                    f"frames={header.frames_per_record}"
                )

        network = safe_code(cfg.network, max_len=2, field_name="Network")
        station = safe_code(cfg.station, max_len=5, field_name="Station")
        location = str(cfg.location).strip().upper()
        if len(location) > 2 or (
            location and not re.fullmatch(r"[A-Z0-9]+", location)
        ):
            raise ValueError("Location maksimal 2 karakter A-Z/0-9.")

        channels = (
            validate_channel(cfg.n_channel, "N Channel"),
            validate_channel(cfg.e_channel, "E Channel"),
            validate_channel(cfg.z_channel, "Z Channel"),
        )

        base = Path(cfg.output_base_folder).expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)

        stats = ConversionStats(input_files=len(paths))
        adc_status_qc = create_adc_status_qc(first.channels)
        total_records = max(1, sum(h.estimated_records for h in headers))
        processed_records = 0
        header_sample_rate = float(first.sample_rate_hz)

        measured_headers = [
            header
            for header in headers
            if (
                header.measured_sample_rate_hz is not None
                and header.measured_rate_duration_s is not None
                and header.measured_rate_frame_delta is not None
                and header.measured_rate_duration_s > 0.0
                and header.measured_rate_frame_delta > 0
            )
        ]
        if len(measured_headers) != len(headers):
            unavailable = [
                Path(header.path).name
                for header in headers
                if header not in measured_headers
            ]
            raise ValueError(
                "Measured sampling rate tidak dapat dihitung untuk semua input BIN. "
                "Conversion dihentikan agar MiniSEED tidak memakai Fs nominal/header "
                "secara diam-diam. File: " + ", ".join(unavailable)
            )

        total_rate_frames = sum(
            int(header.measured_rate_frame_delta)
            for header in measured_headers
        )
        total_rate_duration_s = sum(
            float(header.measured_rate_duration_s)
            for header in measured_headers
        )
        current_sample_rate = float(total_rate_frames) / float(total_rate_duration_s)
        sample_rate_source = "measured from BIN: delta(data_cnt) / delta(record timestamp)"

        if not math.isfinite(current_sample_rate) or current_sample_rate <= 0.0:
            raise ValueError("Measured sample rate BIN tidak valid.")

        deviation_percent = (
            (current_sample_rate - header_sample_rate)
            / header_sample_rate
            * 100.0
        )
        self.log_message.emit(
            f"Sampling rate AUTO: header={header_sample_rate:.6f} Hz | "
            f"measured={current_sample_rate:.6f} Hz | "
            f"deviation={deviation_percent:+.6f}%"
        )

        # One NN-indexed output set is allocated per UTC hour touched by this
        # conversion. The allocation rule mirrors miniseed_recording_v21.py:
        # scan existing per-session files, then choose max(NN)+1 without overwrite.
        output_sets: dict[str, dict] = {}

        def hour_floor_from_ns(timestamp_ns: int) -> datetime:
            value = datetime.fromtimestamp(
                int(timestamp_ns) / 1_000_000_000.0,
                tz=timezone.utc,
            )
            return value.replace(minute=0, second=0, microsecond=0)

        def sample_offset_ns(sample_index: int) -> int:
            return int(round(
                int(sample_index) * 1_000_000_000.0 / current_sample_rate
            ))

        def create_output_set(target_hour_utc: datetime) -> dict:
            normalized_hour_utc = target_hour_utc.astimezone(timezone.utc).replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            hour_stamp = normalized_hour_utc.strftime("%Y%m%d_%H")
            hour_key = hour_stamp
            existing = output_sets.get(hour_key)
            if existing is not None:
                return existing

            year_folder = base / f"{normalized_hour_utc.year:04d}"
            month_folder = year_folder / f"{normalized_hour_utc.year:04d}{normalized_hour_utc.month:02d}"
            day_stamp = normalized_hour_utc.strftime("%Y%m%d")
            day_folder = month_folder / day_stamp
            day_folder.mkdir(parents=True, exist_ok=True)

            folder = day_folder / hour_stamp
            folder.mkdir(parents=False, exist_ok=True)

            max_index = 0
            pattern = re.compile(
                rf"_{re.escape(hour_stamp)}_(\d+)\.(?:mseed|csv|json|xml)$",
                re.IGNORECASE,
            )
            try:
                children = list(folder.iterdir())
            except FileNotFoundError:
                children = []

            for child in children:
                if not child.is_file():
                    continue
                match = pattern.search(child.name)
                if match is None:
                    continue
                max_index = max(max_index, int(match.group(1)))

            counter = max_index + 1
            while True:
                file_tag = f"{hour_stamp}_{counter:02d}"
                candidate_names = (
                    f"{station}_N_{channels[0]}_{file_tag}.mseed",
                    f"{station}_E_{channels[1]}_{file_tag}.mseed",
                    f"{station}_Z_{channels[2]}_{file_tag}.mseed",
                    f"record_sensors_{file_tag}.csv",
                    f"session_metadata_{file_tag}.json",
                )
                if not any((folder / name).exists() for name in candidate_names):
                    break
                counter += 1

            out_paths = (
                folder / f"{station}_N_{channels[0]}_{file_tag}.mseed",
                folder / f"{station}_E_{channels[1]}_{file_tag}.mseed",
                folder / f"{station}_Z_{channels[2]}_{file_tag}.mseed",
            )
            sensor_csv = folder / f"record_sensors_{file_tag}.csv"
            metadata_path = folder / f"session_metadata_{file_tag}.json"

            csv_handle = None
            if cfg.write_sensor_csv:
                csv_handle = sensor_csv.open("w", encoding="utf-8", newline="")
                csv_handle.write(
                    "source_file,record_index,data_cnt,frame_base_idx,"
                    "record_time_utc,record_anchor_utc,depth_m,temperature_c,"
                    "roll_deg,pitch_deg,yaw_deg\n"
                )

            item = {
                "hour_utc": normalized_hour_utc,
                "hour_stamp": hour_stamp,
                "hour_key": hour_key,
                "index": int(counter),
                "file_tag": file_tag,
                "folder": folder,
                "out_paths": out_paths,
                "sensor_csv": sensor_csv,
                "metadata_path": metadata_path,
                "sensor_handle": csv_handle,
                "source_files": set(),
                "record_rows": 0,
                "frames_written": 0,
                "bytes_mseed": 0,
                "trace_chunks_written": 0,
                "first_sample_ns": None,
                "last_sample_ns": None,
            }
            output_sets[hour_key] = item
            self.log_message.emit(
                f"UTC hour output -> {folder} | NN={counter:02d}"
            )
            return item

        # Active waveform buffer. It never spans an acquisition gap/reset or UTC
        # hour boundary. Therefore every appended MiniSEED trace has truthful timing.
        axis_buffers = [[], [], []]
        buffered_samples = 0
        buffer_start_ns = None
        active_output: Optional[dict] = None

        flush_limit = min(
            MAX_FLUSH_SAMPLES,
            max(
                first.frames_per_record,
                int(round(DEFAULT_FLUSH_SECONDS * current_sample_rate)),
            ),
        )

        def flush_waveform_buffer():
            nonlocal axis_buffers, buffered_samples, buffer_start_ns
            if buffered_samples <= 0 or buffer_start_ns is None or active_output is None:
                axis_buffers = [[], [], []]
                buffered_samples = 0
                buffer_start_ns = None
                return

            self._check_cancel()
            data_nez = [np.concatenate(parts) for parts in axis_buffers]
            bytes_written = 0
            for axis_data, channel_code, path in zip(
                data_nez,
                channels,
                active_output["out_paths"],
            ):
                bytes_written += append_miniseed_trace(
                    path,
                    axis_data,
                    network=network,
                    station=station,
                    location=location,
                    channel=channel_code,
                    start_ns=int(buffer_start_ns),
                    sample_rate_hz=current_sample_rate,
                )

            stats.bytes_mseed += int(bytes_written)
            stats.trace_chunks_written += 1
            active_output["bytes_mseed"] += int(bytes_written)
            active_output["trace_chunks_written"] += 1

            axis_buffers = [[], [], []]
            buffered_samples = 0
            buffer_start_ns = None

        def append_hour_chunk(
            hour_output: dict,
            nez,
            start_index: int,
            end_index: int,
            chunk_start_ns: int,
            source_file: str,
        ):
            nonlocal active_output, axis_buffers, buffered_samples, buffer_start_ns
            count = int(end_index - start_index)
            if count <= 0:
                return

            if active_output is not hour_output:
                flush_waveform_buffer()
                active_output = hour_output

            if buffer_start_ns is None:
                buffer_start_ns = int(chunk_start_ns)

            for axis in range(3):
                axis_buffers[axis].append(
                    np.ascontiguousarray(nez[axis][start_index:end_index], dtype=np.int32)
                )
            buffered_samples += count

            hour_output["source_files"].add(str(source_file))
            hour_output["frames_written"] += count
            if hour_output["first_sample_ns"] is None:
                hour_output["first_sample_ns"] = int(chunk_start_ns)
            last_sample_ns = int(
                chunk_start_ns + sample_offset_ns(max(0, count - 1))
            )
            hour_output["last_sample_ns"] = last_sample_ns

            if buffered_samples >= flush_limit:
                flush_waveform_buffer()

        # Acquisition-run timing state. Within one continuous data_cnt run, the
        # first record RTC anchors the run and all following sample times come from
        # data_cnt + sample_rate. Gaps/resets start a new anchored run.
        run_start_ns = None
        run_first_cnt = None
        previous_cnt = None
        previous_frames_per_record = None

        # Used only to detect UTC RTC midnight rollover per source file.
        last_tod_ms = None
        day_rollover = 0

        try:
            for file_index, header in enumerate(headers):
                self._check_cancel()
                base_dt = parse_filename_datetime(header.path)
                if base_dt is None:
                    base_dt = datetime.fromtimestamp(
                        Path(header.path).stat().st_mtime,
                        tz=timezone.utc,
                    ).replace(tzinfo=None)
                    self.log_message.emit(
                        f"WARNING: {Path(header.path).name} tidak mengikuti "
                        "OBS_YYYYMMDD_HHMMSS.bin; tanggal memakai file mtime "
                        f"{base_dt.date().isoformat()}."
                    )

                last_tod_ms = None
                day_rollover = 0

                self.log_message.emit(
                    f"Reading {Path(header.path).name} | "
                    f"Fs={header.sample_rate_hz} Hz | ch={header.channels} | "
                    f"frames/record={header.frames_per_record} | "
                    f"record header={header.record_header_size} B"
                )

                def event_cb(kind, message):
                    self._event(kind, message, stats)

                for record in iter_binary_records(header, event_cb=event_cb):
                    self._check_cancel()
                    stats.records_read += 1
                    processed_records += 1

                    tod_ms = (
                        ((record.hours * 60 + record.minutes) * 60 + record.seconds)
                        * 1000
                        + record.milliseconds
                    )
                    if last_tod_ms is not None and tod_ms < last_tod_ms:
                        backward_ms = int(last_tod_ms - tod_ms)
                        if backward_ms > 12 * 3600 * 1000:
                            # Genuine UTC-date rollover around midnight.
                            day_rollover += 1
                        else:
                            # Current firmware can expose non-atomic RTC field
                            # observations around second/minute rollover. Keep
                            # data_cnt + Fs authoritative for continuous timing.
                            stats.rtc_nonmonotonic_records += 1
                    last_tod_ms = tod_ms

                    utc_dt = record_utc_datetime(
                        record,
                        base_date=base_dt.date(),
                        day_rollover=day_rollover,
                    )
                    record_anchor_ns = utc_datetime_to_timestamp_ns(utc_dt)
                    record_anchor_ns = record_write_time_to_first_sample_ns(
                        record_anchor_ns,
                        sample_rate_hz=current_sample_rate,
                        frames_per_record=header.frames_per_record,
                    )

                    new_run = False
                    gap_frames = 0
                    counter_reset = False

                    if previous_cnt is None:
                        new_run = True
                    else:
                        expected = (
                            int(previous_cnt) + int(previous_frames_per_record)
                        ) & 0xFFFFFFFF
                        if record.data_cnt != expected:
                            delta = (int(record.data_cnt) - int(expected)) & 0xFFFFFFFF
                            if delta < 0x80000000:
                                gap_frames = int(delta)
                                stats.gaps_detected += 1
                                stats.gap_frames += gap_frames
                            else:
                                counter_reset = True
                                stats.counter_resets += 1
                            new_run = True

                    if new_run:
                        flush_waveform_buffer()
                        active_output = None
                        stats.segments_started += 1
                        run_start_ns = int(record_anchor_ns)
                        run_first_cnt = int(record.data_cnt)
                        if previous_cnt is not None:
                            if counter_reset:
                                self.log_message.emit(
                                    f"COUNTER RESET/new session at "
                                    f"{Path(record.file_path).name} record "
                                    f"{record.file_record_index}: data_cnt="
                                    f"{record.data_cnt}"
                                )
                            else:
                                self.log_message.emit(
                                    f"DATA GAP at {Path(record.file_path).name} "
                                    f"record {record.file_record_index}: "
                                    f"missing {gap_frames} frame(s)."
                                )

                    if run_start_ns is None or run_first_cnt is None:
                        raise RuntimeError("Internal timing state belum terinisialisasi.")

                    frames_since_run_start = (
                        int(record.data_cnt) - int(run_first_cnt)
                    ) & 0xFFFFFFFF
                    record_data_start_ns = int(
                        run_start_ns + sample_offset_ns(frames_since_run_start)
                    )

                    nez = decode_nez_counts(
                        record.payload,
                        frames_per_record=header.frames_per_record,
                        channels=header.channels,
                    )
                    status_bytes = decode_status_bytes(
                        record.payload,
                        frames_per_record=header.frames_per_record,
                        channels=header.channels,
                    )
                    update_adc_status_qc(adc_status_qc, status_bytes)
                    stats.adc_status_channel_id_mismatches = int(
                        adc_status_qc["channel_id_mismatches"]
                    )

                    # Split one source record at exact UTC-hour boundaries when
                    # necessary. Typical 128-frame records touch at most two hours.
                    record_frames = int(header.frames_per_record)
                    chunk_index = 0
                    first_output_for_record = None
                    while chunk_index < record_frames:
                        chunk_start_ns = int(
                            record_data_start_ns + sample_offset_ns(chunk_index)
                        )
                        hour_utc = hour_floor_from_ns(chunk_start_ns)
                        hour_output = create_output_set(hour_utc)
                        if first_output_for_record is None:
                            first_output_for_record = hour_output

                        next_hour_utc = hour_utc + timedelta(hours=1)
                        next_hour_ns = int(round(next_hour_utc.timestamp() * 1_000_000_000.0))
                        delta_ns = max(1, next_hour_ns - chunk_start_ns)

                        # Number of sample timestamps strictly before the next UTC
                        # hour. Integer ceil(delta * Fs / 1e9) handles non-divisor
                        # sample rates without allowing the next-hour sample into
                        # the previous-hour file.
                        samples_before_boundary = int(
                            math.ceil(
                                (delta_ns * current_sample_rate)
                                / 1_000_000_000.0
                                - 1e-12
                            )
                        )
                        chunk_count = min(
                            record_frames - chunk_index,
                            max(1, samples_before_boundary),
                        )
                        chunk_end = chunk_index + chunk_count

                        append_hour_chunk(
                            hour_output,
                            nez,
                            chunk_index,
                            chunk_end,
                            chunk_start_ns,
                            record.file_path,
                        )
                        stats.frames_written += chunk_count
                        chunk_index = chunk_end

                    stats.records_written += 1

                    # Ancillary sensor values are record-level, not sample-level.
                    # Store one row in the UTC-hour set containing the record's
                    # first waveform sample. If a record straddles an hour boundary,
                    # the waveform is split but this single sensor row remains with
                    # the record start hour.
                    if first_output_for_record is not None:
                        first_output_for_record["source_files"].add(record.file_path)
                        record_csv_handle = first_output_for_record["sensor_handle"]
                        if record_csv_handle is not None:
                            anchor_utc = datetime.fromtimestamp(
                                record_data_start_ns / 1_000_000_000.0,
                                tz=timezone.utc,
                            ).isoformat(timespec="milliseconds")
                            record_csv_handle.write(
                                f'"{Path(record.file_path).name}",'
                                f"{record.file_record_index},{record.data_cnt},"
                                f"{record.frame_base_idx},"
                                f'"{utc_dt.isoformat(timespec="milliseconds")}",'
                                f'"{anchor_utc}",'
                                f"{record.depth_m:.3f},{record.temperature_c:.3f},"
                                f"{record.roll_deg:.3f},{record.pitch_deg:.3f},"
                                f"{record.yaw_deg:.3f}\n"
                            )
                            first_output_for_record["record_rows"] += 1

                    previous_cnt = int(record.data_cnt)
                    previous_frames_per_record = int(header.frames_per_record)

                    percent = int(
                        min(
                            100,
                            round(processed_records * 100.0 / total_records),
                        )
                    )
                    if processed_records % 8 == 0:
                        self.progress_changed.emit(
                            percent,
                            processed_records,
                            f"{Path(header.path).name} record "
                            f"{record.file_record_index}",
                        )

            flush_waveform_buffer()

        finally:
            # Close every per-hour CSV even if conversion is cancelled/raises.
            for hour_output in output_sets.values():
                csv_handle = hour_output.get("sensor_handle")
                hour_output["sensor_handle"] = None
                if csv_handle is not None:
                    try:
                        csv_handle.flush()
                    except OSError:
                        pass
                    try:
                        csv_handle.close()
                    except OSError:
                        pass

        # Per-hour metadata uses the same YYYYMMDD_HH_NN tag as the waveform set.
        # It intentionally identifies this as offline recovery/conversion rather
        # than pretending the file came from the live PC recorder.
        for hour_output in output_sets.values():
            metadata = {
                "application": APP_TITLE,
                "version": APP_VERSION,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "source_format": "OBS binary log v1; current firmware validated with 30-byte record headers",
                "archive_layout": "miniseed_recording_v21-compatible UTC-hour hierarchy",
                "time_basis": "UTC",
                "segment_hour_utc": hour_output["hour_utc"].strftime("%Y-%m-%dT%H:00:00Z"),
                "segment_index_in_hour": int(hour_output["index"]),
                "segment_file_tag": hour_output["file_tag"],
                "segment_folder": hour_output["folder"].name,
                "input_files": sorted(hour_output["source_files"]),
                "all_conversion_input_files": paths,
                "input_headers": [asdict(h) for h in headers],
                "output": {
                    "folder": str(hour_output["folder"]),
                    "network": network,
                    "station": station,
                    "location": location,
                    "channels": {
                        "N": channels[0],
                        "E": channels[1],
                        "Z": channels[2],
                    },
                    "sample_rate_hz": current_sample_rate,
                    "sample_rate_measured_hz": current_sample_rate,
                    "sample_rate_header_hz": header_sample_rate,
                    "sample_rate_deviation_percent": deviation_percent,
                    "sample_rate_source": sample_rate_source,
                    "source_adc_channel_count": int(first.channels),
                    "exported_source_channels": [0, 1, 2],
                    "ignored_source_channels": list(range(3, int(first.channels))),
                    "encoding": "STEIM2 / INT32",
                    "record_length_bytes": MSEED_RECLEN,
                    "files": {
                        "N": hour_output["out_paths"][0].name,
                        "E": hour_output["out_paths"][1].name,
                        "Z": hour_output["out_paths"][2].name,
                        "record_sensors": (
                            hour_output["sensor_csv"].name if cfg.write_sensor_csv else None
                        ),
                        "session_metadata": (
                            hour_output["metadata_path"].name if cfg.write_metadata_json else None
                        ),
                    },
                },
                "time_interpretation": {
                    "obs_time_basis": "UTC",
                    "bin_filename_time_basis": "UTC",
                    "record_timestamp_time_basis": "UTC",
                    "timezone_conversion_applied": False,
                    "record_timestamp_semantics": "record_write_time",
                    "first_sample_anchor_rule": (
                        "record_write_utc - (frames_per_record - 1) / measured_sample_rate_hz"
                    ),
                    "hour_folder_source": "reconstructed waveform sample UTC timestamp",
                    "note": (
                        "OBS_YYYYMMDD_HHMMSS.bin and record-header HH:MM:SS.mmm are interpreted "
                        "directly as UTC. BINARY_LOG_FORMAT defines the record timestamp as the "
                        "time when the record was written, so the first-sample anchor is shifted "
                        "back by (frames_per_record - 1) / measured Fs. Within each continuous "
                        "data_cnt run, waveform timing follows measured Fs + data_cnt. Per-record "
                        "RTC non-monotonic observations are counted for QC but do not distort the "
                        "continuous waveform clock. Gaps/resets start a new trace segment anchored "
                        "from that record-write UTC. Waveform samples are split at UTC-hour boundaries."
                    ),
                },
                "segment_counters": {
                    "waveform_frames_per_axis": int(hour_output["frames_written"]),
                    "sensor_record_rows": int(hour_output["record_rows"]),
                    "bytes_mseed": int(hour_output["bytes_mseed"]),
                    "trace_chunks_written": int(hour_output["trace_chunks_written"]),
                    "rtc_nonmonotonic_records_global": int(
                        stats.rtc_nonmonotonic_records
                    ),
                    "adc_status_channel_id_mismatches_global": int(
                        stats.adc_status_channel_id_mismatches
                    ),
                    "first_sample_utc": (
                        datetime.fromtimestamp(
                            hour_output["first_sample_ns"] / 1_000_000_000.0,
                            tz=timezone.utc,
                        ).isoformat(timespec="milliseconds")
                        if hour_output["first_sample_ns"] is not None
                        else None
                    ),
                    "last_sample_utc": (
                        datetime.fromtimestamp(
                            hour_output["last_sample_ns"] / 1_000_000_000.0,
                            tz=timezone.utc,
                        ).isoformat(timespec="milliseconds")
                        if hour_output["last_sample_ns"] is not None
                        else None
                    ),
                },
                "conversion_stats_global": asdict(stats),
                "adc_status_qc_global": adc_status_qc,
                "notes": [
                    "CH0/CH1/CH2 are exported as N/E/Z respectively; physical sample indices are unchanged.",
                    "Low 24 ADC bits are sign-extended into INT32 counts; high status byte is not stored in waveform MiniSEED.",
                    "MiniSEED requested sample rate is measured automatically from BIN data_cnt versus record timestamps.",
                    "MiniSEED2 may store the nearest representable rate because its header uses integer sample-rate factor/multiplier fields.",
                    "Header sample_rate_hz is retained as nominal/reference metadata only.",
                    "Input-table FIRST/LAST SAMPLE UTC represent operational waveform coverage; record-write UTC anchors remain in input_headers metadata.",
                    "No decimation, interpolation, or synthetic gap filling is applied.",
                    "30-byte record header is the current validated firmware format; 34-byte remains compatibility-only.",
                    "CH3/AUX and any source channel above CH2 are intentionally not exported to waveform MiniSEED.",
                    "NN is selected from existing files in each UTC-hour folder; existing files are never overwritten.",
                    "record_sensors CSV is converter-specific because the onboard .bin format contains no USBL longitude/latitude.",
                ],
            }

            if cfg.write_metadata_json:
                hour_output["metadata_path"].write_text(
                    json.dumps(metadata, indent=2),
                    encoding="utf-8",
                )

        if not output_sets:
            raise RuntimeError("Tidak ada record waveform yang berhasil dikonversi.")

        if cfg.verify_output:
            self.log_message.emit("Verifying generated MiniSEED files with ObsPy...")
            for hour_output in output_sets.values():
                for path, channel_code in zip(hour_output["out_paths"], channels):
                    if not path.exists() or path.stat().st_size <= 0:
                        raise RuntimeError(f"Output tidak terbentuk: {path}")
                    stream = obspy_read(str(path), format="MSEED")
                    if len(stream) <= 0:
                        raise RuntimeError(f"MiniSEED kosong/tidak terbaca: {path.name}")
                    for tr in stream:
                        if tr.stats.channel != channel_code:
                            raise RuntimeError(
                                f"Channel verification mismatch pada {path.name}: "
                                f"{tr.stats.channel} != {channel_code}"
                            )
                        stored_rate = float(tr.stats.sampling_rate)
                        rate_delta_hz = stored_rate - current_sample_rate
                        rate_tolerance_hz = max(
                            MSEED_RATE_VERIFY_ABS_TOL_HZ,
                            abs(current_sample_rate) * MSEED_RATE_VERIFY_REL_TOL,
                        )
                        if abs(rate_delta_hz) > rate_tolerance_hz:
                            raise RuntimeError(
                                f"Sample-rate verification mismatch pada {path.name}: "
                                f"measured/requested={current_sample_rate:.9f} Hz, "
                                f"MiniSEED2 stored={stored_rate:.9f} Hz, "
                                f"delta={rate_delta_hz:+.9f} Hz, "
                                f"tolerance={rate_tolerance_hz:.9f} Hz."
                            )

                        if abs(rate_delta_hz) > 1e-12:
                            self.log_message.emit(
                                f"MiniSEED2 Fs representation: "
                                f"measured/requested={current_sample_rate:.9f} Hz | "
                                f"stored={stored_rate:.9f} Hz | "
                                f"delta={rate_delta_hz:+.9f} Hz"
                            )
            self.log_message.emit("MiniSEED verification: OK")

        self.progress_changed.emit(100, processed_records, "Completed")

        # For one UTC hour open that folder directly. For conversions spanning
        # multiple hours, return the selected archive base so every hour is visible.
        if len(output_sets) == 1:
            result_folder = str(next(iter(output_sets.values()))["folder"])
        else:
            result_folder = str(base)
        return result_folder, stats


# =============================================================================
# GUI
# =============================================================================

class ConverterWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.worker: Optional[ConversionWorker] = None
        self.input_headers: dict[str, BinaryLogHeader] = {}

        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.resize(1240, 840)
        self.setMinimumSize(940, 620)

        icon = application_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Modern compact header ------------------------------------------------
        header = QFrame()
        header.setObjectName("headerCard")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 14, 18, 14)
        hl.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        eyebrow = QLabel("OBS DATA RECOVERY")
        eyebrow.setObjectName("eyebrow")
        title_box.addWidget(eyebrow)

        title = QLabel("OBS Binary Log → MiniSEED")
        title.setObjectName("title")
        title_box.addWidget(title)

        subtitle = QLabel(
            "Offline 3-axis conversion • CH0/N → EHN • CH1/E → EHE • "
            "CH2/Z → EHZ • INT32 + STEIM2"
        )
        subtitle.setObjectName("subtitle")
        title_box.addWidget(subtitle)
        hl.addLayout(title_box, 1)

        badge_col = QVBoxLayout()
        badge_col.setSpacing(5)
        badge_col.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        version_badge = QLabel(f"CONVERTER  v{APP_VERSION}")
        version_badge.setObjectName("versionBadge")
        version_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_col.addWidget(version_badge)

        offline_badge = QLabel("● OFFLINE / NO NETWORK REQUIRED")
        offline_badge.setObjectName("offlineBadge")
        offline_badge.setAlignment(Qt.AlignmentFlag.AlignRight)
        badge_col.addWidget(offline_badge)

        hl.addLayout(badge_col)
        layout.addWidget(header)

        # Workflow summary strip ----------------------------------------------
        summary = QFrame()
        summary.setObjectName("summaryStrip")
        sg = QHBoxLayout(summary)
        sg.setContentsMargins(14, 9, 14, 9)
        sg.setSpacing(12)

        summary_items = (
            ("01 INPUT", "OBS_YYYYMMDD_HHMMSS.bin"),
            ("02 MAP", "N / E / Z"),
            ("03 TIME", "OBS UTC"),
            ("04 WRITE", "MiniSEED2 + metadata"),
            ("05 VERIFY", "ObsPy"),
        )
        for idx, (k, v) in enumerate(summary_items):
            cell = QVBoxLayout()
            cell.setSpacing(1)
            a = QLabel(k)
            a.setObjectName("summaryLabel")
            b = QLabel(v)
            b.setObjectName("summaryValue")
            cell.addWidget(a)
            cell.addWidget(b)
            sg.addLayout(cell, 1)
            if idx < len(summary_items) - 1:
                sep = QFrame()
                sep.setObjectName("summaryDivider")
                sep.setFixedWidth(1)
                sep.setMinimumHeight(30)
                sg.addWidget(sep)

        layout.addWidget(summary)

        # Scrollable workflow --------------------------------------------------
        scroll = QScrollArea()
        scroll.setObjectName("contentScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll, 1)

        content = QWidget()
        content.setObjectName("scrollContent")
        scroll.setWidget(content)

        body = QVBoxLayout(content)
        body.setContentsMargins(2, 2, 8, 4)
        body.setSpacing(12)

        # 01 Input files -------------------------------------------------------
        input_group = QGroupBox("01   OBS BINARY LOG INPUT")
        input_group.setObjectName("sectionCard")
        ig = QVBoxLayout(input_group)
        ig.setContentsMargins(16, 18, 16, 14)
        ig.setSpacing(10)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.add_files_btn = QPushButton("Add .bin Files")
        self.add_files_btn.setObjectName("secondaryButton")
        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.setObjectName("secondaryButton")
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setObjectName("ghostButton")
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("ghostButton")
        buttons.addWidget(self.add_files_btn)
        buttons.addWidget(self.add_folder_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addWidget(self.clear_btn)
        buttons.addStretch(1)
        ig.addLayout(buttons)

        self.file_table = QTableWidget(0, 11)
        self.file_table.setObjectName("fileTable")
        self.file_table.setHorizontalHeaderLabels(
            [
                "FILE",
                "HEADER FS",
                "MEASURED FS",
                "DEV. %",
                "CHANNELS",
                "FRAMES / REC",
                "REC HDR",
                "EST. RECORDS",
                "DURATION",
                "FIRST SAMPLE UTC",
                "LAST SAMPLE UTC",
            ]
        )
        self.file_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.file_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self.file_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.file_table.setShowGrid(False)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.verticalHeader().setDefaultSectionSize(34)

        hh = self.file_table.horizontalHeader()
        hh.setStretchLastSection(False)
        for col in range(11):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        # Long UTC range columns are intentionally allowed to exceed the viewport.
        # QTableWidget then exposes its own horizontal scrollbar as needed.
        self.file_table.setColumnWidth(0, 250)
        self.file_table.setColumnWidth(9, 205)
        self.file_table.setColumnWidth(10, 205)
        self.file_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.file_table.setMinimumHeight(225)
        ig.addWidget(self.file_table)

        self.input_summary = QLabel("No input files selected.")
        self.input_summary.setObjectName("hintPill")
        ig.addWidget(self.input_summary)
        body.addWidget(input_group)

        # 02 Output ------------------------------------------------------------
        output_group = QGroupBox("02   MINISEED OUTPUT & CHANNEL METADATA")
        output_group.setObjectName("sectionCard")
        og = QGridLayout(output_group)
        og.setContentsMargins(16, 18, 16, 14)
        og.setHorizontalSpacing(10)
        og.setVerticalSpacing(9)

        folder_label = QLabel("OUTPUT BASE FOLDER")
        folder_label.setObjectName("fieldLabel")
        og.addWidget(folder_label, 0, 0, 1, 7)

        self.output_edit = QLineEdit(str(BASE_DIR / "recordings" / "miniseed"))
        self.output_edit.setObjectName("wideInput")
        self.output_browse_btn = QPushButton("Browse")
        self.output_browse_btn.setObjectName("secondaryButton")
        og.addWidget(self.output_edit, 1, 0, 1, 6)
        og.addWidget(self.output_browse_btn, 1, 6)

        self.network_edit = QLineEdit(DEFAULT_NETWORK)
        self.station_edit = QLineEdit(DEFAULT_STATION)
        self.location_edit = QLineEdit(DEFAULT_LOCATION)
        self.n_channel_edit = QLineEdit(DEFAULT_N_CHANNEL)
        self.e_channel_edit = QLineEdit(DEFAULT_E_CHANNEL)
        self.z_channel_edit = QLineEdit(DEFAULT_Z_CHANNEL)

        fields = (
            ("NETWORK", self.network_edit),
            ("STATION", self.station_edit),
            ("LOCATION", self.location_edit),
            ("N / CH0", self.n_channel_edit),
            ("E / CH1", self.e_channel_edit),
            ("Z / CH2", self.z_channel_edit),
        )

        for idx, (label, widget) in enumerate(fields):
            row = 2 + (idx // 3) * 2
            col = (idx % 3) * 2
            lab = QLabel(label)
            lab.setObjectName("fieldLabel")
            og.addWidget(lab, row, col, 1, 2)
            og.addWidget(widget, row + 1, col, 1, 2)

        code_note = QLabel(
            "Default MiniSEED codes: RM / OBS01 / 00 / EHN / EHE / EHZ. "
            "Archive: YYYY/YYYYMM/YYYYMMDD/YYYYMMDD_HH with UTC HH and NN "
            "anti-overwrite suffix."
        )
        code_note.setWordWrap(True)
        code_note.setObjectName("hint")
        og.addWidget(code_note, 6, 0, 1, 7)
        body.addWidget(output_group)

        # 03 + 04 side-by-side configuration ----------------------------------
        settings_row = QHBoxLayout()
        settings_row.setSpacing(12)

        time_group = QGroupBox("03   TIME INTERPRETATION")
        time_group.setObjectName("sectionCard")
        tg = QFormLayout(time_group)
        tg.setContentsMargins(16, 18, 16, 14)
        tg.setHorizontalSpacing(16)
        tg.setVerticalSpacing(10)

        self.header_fs_value = QLabel("—")
        self.header_fs_value.setObjectName("hintPill")
        tg.addRow("Header / nominal Fs", self.header_fs_value)

        self.measured_fs_value = QLabel("—")
        self.measured_fs_value.setObjectName("hintPill")
        tg.addRow("Measured Fs", self.measured_fs_value)

        self.fs_deviation_value = QLabel("—")
        self.fs_deviation_value.setObjectName("hintPill")
        tg.addRow("Deviation", self.fs_deviation_value)

        self.miniseed_fs_value = QLabel("AUTO • measured from BIN")
        self.miniseed_fs_value.setObjectName("hintPill")
        tg.addRow("MiniSEED Fs", self.miniseed_fs_value)

        self.record_time_semantics_value = QLabel(
            "RECORD WRITE TIME • AUTO / LOCKED"
        )
        self.record_time_semantics_value.setObjectName("hintPill")
        tg.addRow("Record timestamp semantics", self.record_time_semantics_value)

        note = QLabel(
            "OBS time basis is UTC. BINARY_LOG_FORMAT defines record HH:MM:SS.mmm "
            "as the time when the record was written. The converter therefore "
            "reconstructs the first ADC sample automatically by shifting the record "
            "UTC backward by (frames_per_record - 1) / Measured Fs. Continuous timing "
            "then follows data_cnt + Measured Fs. No timezone offset is applied."
        )
        note.setWordWrap(True)
        note.setObjectName("hint")
        tg.addRow(note)

        options_group = QGroupBox("04   CONVERSION OPTIONS")
        options_group.setObjectName("sectionCard")
        op = QVBoxLayout(options_group)
        op.setContentsMargins(16, 18, 16, 14)
        op.setSpacing(10)

        self.sensor_csv_check = QCheckBox(
            "Write record_sensors_YYYYMMDD_HH_NN.csv"
        )
        self.sensor_csv_check.setChecked(True)

        self.metadata_check = QCheckBox(
            "Write session_metadata_YYYYMMDD_HH_NN.json"
        )
        self.metadata_check.setChecked(True)

        self.verify_check = QCheckBox("Verify generated MiniSEED with ObsPy")
        self.verify_check.setChecked(True)

        op.addWidget(self.sensor_csv_check)
        op.addWidget(self.metadata_check)
        op.addWidget(self.verify_check)

        option_note = QLabel(
            "Only CH0/CH1/CH2 are written as N/E/Z MiniSEED. CH3/AUX is not "
            "exported. Waveform remains raw signed ADC counts; no decimation, "
            "interpolation or synthetic gap filling is introduced."
        )
        option_note.setObjectName("hint")
        option_note.setWordWrap(True)
        op.addWidget(option_note)
        op.addStretch(1)

        settings_row.addWidget(time_group, 3)
        settings_row.addWidget(options_group, 2)
        body.addLayout(settings_row)

        # 05 Progress / log ----------------------------------------------------
        progress_group = QGroupBox("05   CONVERT")
        progress_group.setObjectName("sectionCard")
        pg = QVBoxLayout(progress_group)
        pg.setContentsMargins(16, 18, 16, 14)
        pg.setSpacing(10)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.convert_btn = QPushButton("CONVERT TO MINISEED")
        self.convert_btn.setObjectName("primary")

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.setEnabled(False)

        self.open_output_btn = QPushButton("Open Output Folder")
        self.open_output_btn.setObjectName("secondaryButton")
        self.open_output_btn.setEnabled(False)

        actions.addWidget(self.convert_btn)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.open_output_btn)
        actions.addStretch(1)
        pg.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setObjectName("convertProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        pg.addWidget(self.progress)

        status_row = QHBoxLayout()
        self.status_label = QLabel("● READY")
        self.status_label.setObjectName("status")
        status_row.addWidget(self.status_label)

        status_row.addStretch(1)

        format_label = QLabel("MSEED2  •  INT32  •  STEIM2  •  4096 B")
        format_label.setObjectName("formatBadge")
        status_row.addWidget(format_label)
        pg.addLayout(status_row)

        self.log_box = QLineEdit()
        self.log_box.setObjectName("logLine")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Latest converter message...")
        pg.addWidget(self.log_box)

        body.addWidget(progress_group)
        body.addStretch(1)

        # Signals -------------------------------------------------------------
        self.add_files_btn.clicked.connect(self._add_files)
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear_files)
        self.output_browse_btn.clicked.connect(self._browse_output)
        self.convert_btn.clicked.connect(self._start_conversion)
        self.cancel_btn.clicked.connect(self._cancel_conversion)
        self.open_output_btn.clicked.connect(self._open_output)

        self.last_output_folder: Optional[str] = None

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget, QWidget#scrollContent {
                background: #06131D;
                color: #EAF4F8;
                font-family: "Segoe UI", "Arial";
            }

            QFrame#headerCard {
                background: #091B27;
                border: 1px solid #123142;
                border-radius: 12px;
            }

            QLabel#eyebrow {
                color: #70C9F0;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 1.5px;
            }

            QLabel#title {
                color: #F7FBFD;
                font-size: 23px;
                font-weight: 750;
            }

            QLabel#subtitle {
                color: #86A5B7;
                font-size: 10px;
            }

            QLabel#versionBadge {
                color: #C8EEFF;
                background: #12354A;
                border: 1px solid #245D78;
                border-radius: 10px;
                padding: 5px 10px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 9px;
                font-weight: 800;
            }

            QLabel#offlineBadge {
                color: #71D99A;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 9px;
                font-weight: 750;
            }

            QFrame#summaryStrip {
                background: #081A25;
                border: 1px solid #102E3E;
                border-radius: 10px;
            }

            QLabel#summaryLabel {
                color: #6B8EA2;
                font-size: 8px;
                font-weight: 800;
                letter-spacing: 0.8px;
            }

            QLabel#summaryValue {
                color: #D5E7EF;
                font-size: 9px;
                font-weight: 650;
            }

            QFrame#summaryDivider {
                background: #17384A;
                border: none;
            }

            QScrollArea#contentScroll {
                border: none;
                background: #06131D;
            }

            QGroupBox#sectionCard {
                background: #0C2230;
                border: 1px solid #16384A;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 8px;
                font-weight: 700;
            }

            QGroupBox#sectionCard::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 13px;
                padding: 0 7px;
                color: #CFE4ED;
                background: #0C2230;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 0.8px;
            }

            QLabel {
                color: #DDEBF1;
                background: transparent;
            }

            QLabel#fieldLabel {
                color: #7596A9;
                font-size: 8px;
                font-weight: 800;
                letter-spacing: 0.8px;
            }

            QLabel#hint {
                color: #789BAC;
                font-size: 9px;
                line-height: 1.35;
            }

            QLabel#hintPill {
                color: #9AB7C6;
                background: #091B27;
                border: 1px solid #14384A;
                border-radius: 7px;
                padding: 7px 10px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 9px;
            }

            QLabel#status {
                color: #71D99A;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 10px;
                font-weight: 800;
            }

            QLabel#formatBadge {
                color: #80BBD7;
                background: #091B27;
                border: 1px solid #14384A;
                border-radius: 8px;
                padding: 4px 9px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 8px;
                font-weight: 750;
            }

            QLineEdit, QDoubleSpinBox {
                background: #071923;
                color: #EAF4F8;
                border: 1px solid #21485E;
                border-radius: 6px;
                padding: 7px 9px;
                min-height: 20px;
                selection-background-color: #315F78;
            }

            QLineEdit:focus, QDoubleSpinBox:focus {
                border: 1px solid #3A93BE;
                background: #081D29;
            }

            QLineEdit:read-only {
                color: #AFC7D2;
                background: #071923;
            }

            QTableWidget#fileTable {
                background: #071923;
                alternate-background-color: #091E2A;
                color: #DBE8EE;
                border: 1px solid #173B4E;
                border-radius: 7px;
                selection-background-color: #16445C;
                selection-color: #FFFFFF;
                padding: 0px;
            }

            QHeaderView::section {
                background: #102B3A;
                color: #91AFC0;
                border: none;
                border-right: 1px solid #173B4E;
                border-bottom: 1px solid #173B4E;
                padding: 8px 7px;
                font-size: 8px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }

            QPushButton {
                min-height: 34px;
                background: #143549;
                color: #EAF4F8;
                border: 1px solid #24536A;
                border-radius: 7px;
                padding: 6px 12px;
                font-weight: 700;
            }

            QPushButton:hover {
                background: #1D4960;
                border-color: #3E7C99;
            }

            QPushButton:pressed {
                background: #0F2A39;
            }

            QPushButton:disabled {
                color: #617D8D;
                background: #0A202D;
                border-color: #143244;
            }

            QPushButton#primary {
                background: #2E94C4;
                color: #FFFFFF;
                border: 1px solid #46A4CD;
                padding: 7px 18px;
                font-weight: 800;
            }

            QPushButton#primary:hover {
                background: #3EABD9;
            }

            QPushButton#primary:pressed {
                background: #257EA8;
            }

            QPushButton#secondaryButton {
                background: #123044;
                border-color: #214E65;
            }

            QPushButton#ghostButton {
                background: transparent;
                color: #9DB7C5;
                border-color: #193C4E;
            }

            QPushButton#ghostButton:hover {
                background: #0D2938;
                color: #E7F2F6;
            }

            QPushButton#dangerButton {
                background: #452833;
                color: #FFEFF1;
                border-color: #68404D;
            }

            QPushButton#dangerButton:hover {
                background: #5B303C;
            }

            QCheckBox {
                color: #D6E5EC;
                spacing: 8px;
                padding: 3px 0;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #2A5B73;
                border-radius: 4px;
                background: #071923;
            }

            QCheckBox::indicator:checked {
                background: #2E94C4;
                border-color: #4AABD4;
            }

            QProgressBar#convertProgress {
                background: #071923;
                color: #FFFFFF;
                border: 1px solid #21485E;
                border-radius: 7px;
                text-align: center;
                min-height: 22px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 9px;
                font-weight: 700;
            }

            QProgressBar#convertProgress::chunk {
                background: #2E94C4;
                border-radius: 5px;
            }

            QScrollBar:vertical {
                background: #06131D;
                width: 10px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #1D4256;
                min-height: 30px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background: #2B5C74;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
                height: 0px;
            }

            QToolButton {
                background: #0E2533;
                color: #DDEAF2;
                border: none;
            }
            """
        )

    # ------------------------------------------------------------------ inputs
    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select OBS Binary Log Files",
            "",
            "OBS Binary Log (*.bin);;All Files (*.*)",
        )
        if paths:
            self._ingest_paths(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder Containing OBS .bin Logs",
        )
        if not folder:
            return
        paths = [str(p) for p in Path(folder).glob("*.bin")]
        if not paths:
            QMessageBox.information(
                self,
                APP_TITLE,
                "Tidak ada file .bin pada folder tersebut.",
            )
            return
        self._ingest_paths(paths)

    def _ingest_paths(self, paths):
        errors = []
        for path in sort_input_paths(paths):
            try:
                header = inspect_binary_log(path)
                self.input_headers[header.path] = header
            except (OSError, ValueError, struct.error) as input_error:
                errors.append(f"{Path(path).name}: {input_error}")
        self._refresh_table()
        if errors:
            QMessageBox.warning(
                self,
                APP_TITLE,
                "Sebagian file tidak dapat dipakai:\n\n" + "\n".join(errors[:12]),
            )

    def _refresh_table(self):
        headers = [
            self.input_headers[path]
            for path in sort_input_paths(self.input_headers.keys())
        ]
        self.file_table.setRowCount(len(headers))

        for row, h in enumerate(headers):
            values = (
                Path(h.path).name,
                f"{h.sample_rate_hz:.3f} Hz",
                (
                    f"{h.measured_sample_rate_hz:.6f} Hz"
                    if h.measured_sample_rate_hz is not None
                    else "UNAVAILABLE"
                ),
                (
                    f"{h.rate_deviation_percent:+.6f} %"
                    if h.rate_deviation_percent is not None
                    else "—"
                ),
                str(h.channels),
                str(h.frames_per_record),
                f"{h.record_header_size} B",
                f"{h.estimated_records:,}",
                f"{h.estimated_duration_s:.2f} s",
                h.first_sample_utc or "UNAVAILABLE",
                h.last_sample_utc or "UNAVAILABLE",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setToolTip(h.path)
                    item.setData(Qt.ItemDataRole.UserRole, h.path)
                elif col == 9:
                    item.setToolTip("UTC timestamp of the first ADC sample that will be written to MiniSEED.")
                elif col == 10:
                    item.setToolTip("UTC timestamp of the last ADC sample that will be written to MiniSEED.")
                self.file_table.setItem(row, col, item)

        total_records = sum(h.estimated_records for h in headers)
        total_frames = sum(h.estimated_frames for h in headers)
        if headers:
            header_fs_values = sorted({float(h.sample_rate_hz) for h in headers})
            measured_headers = [
                h for h in headers
                if (
                    h.measured_sample_rate_hz is not None
                    and h.measured_rate_duration_s is not None
                    and h.measured_rate_frame_delta is not None
                    and h.measured_rate_duration_s > 0
                    and h.measured_rate_frame_delta > 0
                )
            ]
            duration = sum(h.estimated_duration_s for h in headers)

            if measured_headers:
                total_rate_frames = sum(
                    int(h.measured_rate_frame_delta) for h in measured_headers
                )
                total_rate_duration = sum(
                    float(h.measured_rate_duration_s) for h in measured_headers
                )
                aggregate_measured = (
                    float(total_rate_frames) / float(total_rate_duration)
                    if total_rate_duration > 0
                    else None
                )
            else:
                aggregate_measured = None

            header_text = (
                f"{header_fs_values[0]:.3f} Hz"
                if len(header_fs_values) == 1
                else ", ".join(f"{x:.3f}" for x in header_fs_values) + " Hz"
            )
            self.header_fs_value.setText(header_text)

            if aggregate_measured is not None:
                reference_header = float(headers[0].sample_rate_hz)
                deviation = (
                    (aggregate_measured - reference_header)
                    / reference_header
                    * 100.0
                )
                self.measured_fs_value.setText(f"{aggregate_measured:.6f} Hz")
                self.fs_deviation_value.setText(f"{deviation:+.6f} %")
                self.miniseed_fs_value.setText(
                    f"{aggregate_measured:.6f} Hz • AUTO / MEASURED FROM BIN"
                )
                measured_text = f"{aggregate_measured:.6f} Hz"
            else:
                self.measured_fs_value.setText("UNAVAILABLE")
                self.fs_deviation_value.setText("—")
                self.miniseed_fs_value.setText("UNAVAILABLE • conversion blocked")
                measured_text = "UNAVAILABLE"

            self.input_summary.setText(
                f"{len(headers)} file(s) • {total_records:,} records • "
                f"{total_frames:,} ADC frames • approx {duration:.2f} s • "
                f"Header Fs={header_text} • Measured Fs={measured_text}"
            )
        else:
            self.input_summary.setText("No input files selected.")
            self.header_fs_value.setText("—")
            self.measured_fs_value.setText("—")
            self.fs_deviation_value.setText("—")
            self.miniseed_fs_value.setText("AUTO • measured from BIN")

    def _remove_selected(self):
        rows = sorted(
            {index.row() for index in self.file_table.selectedIndexes()},
            reverse=True,
        )
        for row in rows:
            item = self.file_table.item(row, 0)
            if item is None:
                continue
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                self.input_headers.pop(str(path), None)
        self._refresh_table()

    def _clear_files(self):
        self.input_headers.clear()
        self._refresh_table()

    # ------------------------------------------------------------------ output
    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Base Folder",
            self.output_edit.text().strip() or str(BASE_DIR),
        )
        if folder:
            self.output_edit.setText(folder)

    def _build_config(self) -> ConverterConfig:
        paths = tuple(sort_input_paths(self.input_headers.keys()))
        if not paths:
            raise ValueError("Pilih minimal satu file OBS .bin.")

        return ConverterConfig(
            input_files=paths,
            output_base_folder=self.output_edit.text().strip(),
            network=self.network_edit.text().strip(),
            station=self.station_edit.text().strip(),
            location=self.location_edit.text().strip(),
            n_channel=self.n_channel_edit.text().strip(),
            e_channel=self.e_channel_edit.text().strip(),
            z_channel=self.z_channel_edit.text().strip(),
            write_sensor_csv=self.sensor_csv_check.isChecked(),
            write_metadata_json=self.metadata_check.isChecked(),
            verify_output=self.verify_check.isChecked(),
        )

    # ---------------------------------------------------------------- convert
    def _start_conversion(self):
        if self.worker is not None and self.worker.isRunning():
            return

        # Always ask where this conversion should be stored before starting.
        # The selected directory is the archive BASE; the existing UTC hierarchy
        # YYYY/YYYYMM/YYYYMMDD/YYYYMMDD_HH is created underneath it.
        current_output = self.output_edit.text().strip() or str(BASE_DIR)
        selected_output = QFileDialog.getExistingDirectory(
            self,
            "Select MiniSEED Output Base Folder",
            current_output,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected_output:
            self.status_label.setText("Ready")
            self.log_box.setText("Conversion cancelled before start.")
            return

        self.output_edit.setText(selected_output)

        if not NUMPY_AVAILABLE or not OBSPY_AVAILABLE:
            missing = []
            if not NUMPY_AVAILABLE:
                missing.append(f"numpy ({NUMPY_ERROR})")
            if not OBSPY_AVAILABLE:
                missing.append(f"obspy ({OBSPY_ERROR})")
            QMessageBox.critical(
                self,
                APP_TITLE,
                "Required package belum tersedia:\n\n"
                + "\n".join(missing)
                + "\n\nInstall dengan:\npip install numpy obspy",
            )
            return

        try:
            cfg = self._build_config()
            # Validate codes before launching thread.
            safe_code(cfg.network, max_len=2, field_name="Network")
            safe_code(cfg.station, max_len=5, field_name="Station")
            validate_channel(cfg.n_channel, "N Channel")
            validate_channel(cfg.e_channel, "E Channel")
            validate_channel(cfg.z_channel, "Z Channel")

            unavailable_rate_files = [
                Path(header.path).name
                for header in self.input_headers.values()
                if header.measured_sample_rate_hz is None
            ]
            if unavailable_rate_files:
                raise ValueError(
                    "Measured sampling rate BIN tidak tersedia untuk: "
                    + ", ".join(sorted(unavailable_rate_files))
                    + ". Conversion dihentikan."
                )
        except ValueError as config_error:
            QMessageBox.warning(self, APP_TITLE, str(config_error))
            return

        self.last_output_folder = None
        self.open_output_btn.setEnabled(False)
        self.convert_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.status_label.setText("Converting...")
        self.log_box.setText("Starting conversion...")

        self.worker = ConversionWorker(cfg, self)
        connect_signal(self.worker.progress_changed, self._on_progress)
        connect_signal(self.worker.log_message, self._on_log)
        connect_signal(self.worker.finished_ok, self._on_finished)
        connect_signal(self.worker.failed, self._on_failed)
        self.worker.start()

    def _cancel_conversion(self):
        if self.worker is not None and self.worker.isRunning():
            self.status_label.setText("Cancelling...")
            self.worker.cancel()

    def _on_progress(self, percent: int, records: int, text: str):
        self.progress.setValue(int(percent))
        self.status_label.setText(
            f"{percent}% • {records:,} records • {text}"
        )

    def _on_log(self, text: str):
        self.log_box.setText(text)
        self.log_box.setToolTip(text)

    def _finish_ui(self):
        self.convert_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_finished(self, folder: str, stats):
        self._finish_ui()
        self.progress.setValue(100)
        self.last_output_folder = folder
        self.open_output_btn.setEnabled(True)
        self.status_label.setText(
            f"Completed • {stats.records_written:,} records • "
            f"{stats.frames_written:,} frames • "
            f"{stats.gaps_detected} gap(s)"
        )
        self.log_box.setText(f"Output: {folder}")
        QMessageBox.information(
            self,
            APP_TITLE,
            "Conversion selesai.\n\n"
            f"Output folder:\n{folder}\n\n"
            f"Records: {stats.records_written:,}\n"
            f"ADC frames: {stats.frames_written:,}\n"
            f"Segments: {stats.segments_started:,}\n"
            f"Gaps: {stats.gaps_detected:,} "
            f"({stats.gap_frames:,} missing frames)\n"
            f"Counter resets: {stats.counter_resets:,}\n"
            f"RTC non-monotonic records: {stats.rtc_nonmonotonic_records:,}\n"
            f"ADC status ID mismatch: {stats.adc_status_channel_id_mismatches:,}\n"
            f"Resync events: {stats.resync_events:,}",
        )

    def _on_failed(self, message: str):
        self._finish_ui()
        self.status_label.setText("Conversion stopped / failed")
        short = message.strip().splitlines()[-1] if message.strip() else "Unknown error"
        self.log_box.setText(short)
        if "cancelled by user" in message.lower():
            QMessageBox.information(self, APP_TITLE, "Conversion dibatalkan.")
        else:
            QMessageBox.critical(
                self,
                APP_TITLE,
                "Conversion gagal:\n\n" + message[-5000:],
            )

    def _open_output(self):
        if not self.last_output_folder:
            return
        path = Path(self.last_output_folder)
        if not path.exists():
            return
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(path)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as open_error:
            QMessageBox.warning(self, APP_TITLE, f"Cannot open folder:\n{open_error}")

    def closeEvent(self, event: QCloseEvent):
        if self.worker is not None and self.worker.isRunning():
            answer = QMessageBox.question(
                self,
                APP_TITLE,
                "Conversion masih berjalan. Batalkan dan tutup aplikasi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.wait(3000)
        event.accept()


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)
    icon = application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    font = QFont("Segoe UI")
    font.setPointSize(9)
    app.setFont(font)

    missing = []
    if not NUMPY_AVAILABLE:
        missing.append(f"numpy: {NUMPY_ERROR}")
    if not OBSPY_AVAILABLE:
        missing.append(f"obspy: {OBSPY_ERROR}")

    window = ConverterWindow()
    window.show()

    self_test = "--self-test-gui" in sys.argv
    if self_test:
        QTimer.singleShot(350, window.close)
        QTimer.singleShot(1500, app.quit)
    elif missing:
        QMessageBox.warning(
            window,
            APP_TITLE,
            "Converter GUI dapat dibuka, tetapi conversion memerlukan:\n\n"
            + "\n".join(missing)
            + "\n\nInstall dengan:\npip install numpy obspy",
        )

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
