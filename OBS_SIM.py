#!/usr/bin/env python3
"""
OBS TCP Simulator v10.7

TCP channels
------------
54300 : Command / Telemetry channel, max 2 clients
54301 : Bulk ADC Data channel, max 2 clients

Command/Telemetry:
    $ID,field1,field2,...*CC\r\n
Checksum:
    XOR of all bytes between '$' and '*', returned as 2-digit uppercase HEX.

Bulk ADC:
    12-byte little-endian header:
      0..3   = b"OBS:"
      4..7   = uint32 sequence
      8..11  = uint32 payload length (2048)
    Payload:
      512 x uint32 little-endian words
      128 ADC frames x 4 channels

Version 4 adds two selectable ADC sources:
    1. Generated / Control Panel (existing sine-wave simulator)
    2. OBS Binary Log Playback (.bin), replayed record-by-record at the
       automatically measured BIN sample rate and broadcast through the
       same TCP bulk socket server. Ancillary depth/temperature/AHRS fields
       from each log record are also mirrored into the simulator telemetry
       state while playback is active.
Version 5 aligns the command/telemetry wire format with obs_setting_v19.py:
    - $AHRS2 Roll/Pitch/Yaw are transmitted as E1 raw values (deg * 10).
    - $DEPT0 field0 is transmitted as E1 raw (physical value * 10), and
      temperature as E2 raw (degC * 100). Field1 remains unscaled.
    - $TIME1 uses fractional milliseconds, 2-digit year, Sunday=1..Saturday=7,
      and a counter field, matching OBS Setting's TIME1 sender/parser.
    - $XCHM1 controller telemetry is broadcast periodically.
    - Incoming $TIME1 updates the simulator device clock.
    - RMCMD 1/2/5/6 and 50..62 are accepted. RMCMD 61/62 emulate the
      onboard USB logger by emitting checksum-valid $STRG0 FILE_OPENED/CLOSED
      status messages and automatic 60-second filename rotation.

Version 6 aligns the geophone orientation terminology with the current OBS software:
    - CH0 = Geophone N (North)
    - CH1 = Geophone E (East)
    - CH2 = Geophone Z (Vertical)
    - CH3 remains auxiliary/non-geophone data.
    - The binary/TCP payload order remains CH0,CH1,CH2,CH3; no samples are
      reordered, remapped, scaled, filtered, or otherwise modified.
    - Emulated onboard logger filenames remain OBS_YYYYMMDD_HHMMSS.bin and use
      the simulator/OBS device local RTC. They are intentionally not renamed to UTC.
    - Protocol compatibility text is updated for obs_setting_v22.py.

Version 7 updates simulator controls only:
    - Telemetry Depth slider range is limited to 0..300 m.
    - Every Tk Scale control supports keyboard adjustment after focus/click.
    - Left/Down decreases one resolution step; Right/Up increases one step.
    - PageDown/PageUp changes ten steps; Home/End jumps to minimum/maximum.
    - TCP protocol, binary playback, ADC generation, channel order, scaling,
      sample rate and telemetry encoding are unchanged from Version 6.

Version 8 modular integration:
    - Intended to be launched from the OBS Tools modular main window.
    - Window/taskbar branding uses assets/icons/Prameya_rev.png.
    - Simulator TCP protocol, ADC generation/playback, telemetry encoding,
      slider behavior and all Version 7 functional behavior are unchanged.

Version 9 modernizes the simulator GUI only:
    - Dark navy visual language aligned with the OBS Runtime / Converter tools.
    - Modern header, server-status cards, stream-metric strip and styled tabs.
    - Refined buttons, entries, check/radio controls, sliders and server log.
    - OBS window branding is retained.
    - TCP protocol, ADC generation, BIN playback, telemetry encoding, slider
      ranges/keyboard behavior and all simulator data logic are unchanged.

Version 10 refines the simulator GUI and slider interaction only:
    - Replaces native Tk Scale controls with a custom modern flat slider.
    - Adds filled tracks, circular handles, hover/focus feedback and precise keyboard control.
    - Reworks Telemetry into compact grouped control cards plus live ADC value cards.
    - Refines spacing, typography, status cards, metric strip, buttons and notebook tabs.
    - TCP protocol, generated ADC, BIN playback, sample rate, telemetry encoding and
      all simulator data logic remain unchanged from Version 9.

Version 10.1 refines the ADC Simulation tab layout only:
    - Geophone control cards are displayed in physical-axis order CH2(Z), CH0(N), CH1(E).
    - CH3(AUX) remains available as a separate auxiliary channel below the geophone group.
    - Adds responsive vertical scrolling for smaller displays / reduced window heights.
    - TCP payload order remains CH0,CH1,CH2,CH3; this is a GUI display-order change only.

Version 10.2 hardening / self-test support:
    - Windows AppUserModelID setup uses dynamic ctypes lookup for IDE/type-checker clarity.
    - Expected exception paths are narrowed where practical.
    - OBSSimulatorGUI accepts start_servers=False for non-network GUI smoke tests.
    - --self-test-gui constructs the full Tk GUI, runs the event loop briefly, and exits.
    - TCP protocol, payload ordering, ADC generation/playback and telemetry behavior are unchanged.

Version 10.3 current-firmware alignment:
    - 30-byte OBS binary-log record header is now the primary/current firmware format.
    - 34-byte record header remains supported as a compatibility variant.
    - Ambiguous record-header detection now falls back to 30 bytes.
    - Binary playback, TCP bulk framing, generated ADC data and telemetry protocol are unchanged.

Version 10.4 land-test alignment:
    - OBS naming is retained; no product rename to Prameya.
    - GUI seismic semantics are CH0=X, CH1=Y, CH2=Z; CH3 remains AUX.
    - Adds optional effective sample-rate override for Binary Log Playback.
      Default playback pacing follows the BIN header; legacy logs can be replayed
      at a measured effective rate such as 976.580 Hz without modifying payload data.
    - TCP payload still carries CH0..CH3 exactly; no channel is removed from transport.

Version 10.5 NEZ label restoration:
    - Restores GUI seismic semantics to CH0=N, CH1=E, CH2=Z.
    - CH3 remains AUX and remains present in the raw/TCP transport.
    - Effective sample-rate override behavior is unchanged from v10.4.

Version 10.6 source-aware XCHM1 / VMON0 behavior:
    - Generated / Control Panel mode sends $XCHM1 controller-health telemetry.
    - Binary Log Playback mode does NOT send $XCHM1 because the USB BIN record
      does not contain VMON/controller-health fields.
    - Adds a configurable VMON0 control to the Telemetry tab for simulator mode.
    - VMON1, VMON2, VMON3, XCHM1 TEMP, PMON and HMON are transmitted as 0.
    - ADC BIN playback remains unchanged: exact CH0..CH3 raw payload is sent on
      TCP 54301, while depth/temperature/roll/pitch/yaw are mirrored from BIN.

Version 10.7 UTC + automatic measured-Fs synchronization:
    - HARD RULE: simulator/OBS device time, TIME1 and emulated USB filenames are UTC.
    - Binary Log Playback no longer uses BIN header Fs or a manual override for pacing.
    - Playback Fs is measured automatically from BIN data_cnt versus record UTC timestamps:
          measured Fs = delta(data_cnt) / delta(record timestamp)
    - BIN header Fs remains visible as nominal/reference information only.
    - Manual "Use BIN header rate" / effective-rate override controls are removed.
    - If a valid measured Fs cannot be derived, BIN playback is rejected rather than
      silently falling back to nominal/header Fs.
    - v10.6 source-aware XCHM1 behavior remains unchanged.

"""

import math
import os
import queue
import re
import socket
import struct
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from tkinter import filedialog, ttk
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APP_TITLE = "OBS TCP Simulator v10.7"
APP_USER_MODEL_ID = "GRC.UGM.PERTAMINA.OBS.TOOLS.SIMULATOR"

BASE_DIR = Path(__file__).resolve().parent
ICON_DIR = BASE_DIR / "assets" / "icons"
APP_ICON_PNG = ICON_DIR / "Prameya_rev.png"

def configure_windows_app_id(app_id: str) -> None:
    """Set Windows taskbar identity without static DLL-member assumptions."""
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
        setter(app_id)
    except (OSError, AttributeError, TypeError):
        return


configure_windows_app_id(APP_USER_MODEL_ID)

HOST = "0.0.0.0"

COMMAND_PORT = 54300
BULK_PORT = 54301

MAX_COMMAND_CLIENTS = 2
MAX_BULK_CLIENTS = 2

# IMPORTANT:
# This must match the RAW ADC source rate configured in the OBS software.
# Current OBS shared_data_v8 architecture uses 1000 raw frames/s/channel.
ADC_SAMPLE_RATE_HZ = 1000.0

ADC_FRAMES_PER_BLOCK = 128
ADC_CHANNELS = 4
ADC_ORIENTATION = ("N", "E", "Z", "AUX")
ADC_WORDS_PER_BLOCK = ADC_FRAMES_PER_BLOCK * ADC_CHANNELS
ADC_PAYLOAD_BYTES = ADC_WORDS_PER_BLOCK * 4

COMMAND_PERIOD_S = 1.0
BULK_PERIOD_S = ADC_FRAMES_PER_BLOCK / ADC_SAMPLE_RATE_HZ

# Keep accept polling substantially shorter than the 128-ms bulk period.
# A 0.2-s accept timeout would throttle a nominal 1000-Hz stream to roughly
# 5 blocks/s (about 640 ADC frames/s) whenever no second client is connecting.
BULK_ACCEPT_TIMEOUT_S = min(
    0.010,
    BULK_PERIOD_S / 8.0,
)

DEVICE_ID = 0x0001
UNIT_TITLE = "OBS Ocean Bottom Seismometer"
FIRMWARE_VERSION = "3.0.0"
FIRMWARE_DATE = "2026-08-21"

# Firmware command mappings used by obs_setting_v22.py and its local IPC clients.
RMCMD_PWR_MODE_HIGH = 1
RMCMD_LOCK_HIGH = 2
RMCMD_PWR_MODE_LOW = 5
RMCMD_LOCK_LOW = 6
RMCMD_CAMERA_MIN = 50
RMCMD_CAMERA_MAX = 60
RMCMD_USB_LOG_START = 61
RMCMD_USB_LOG_STOP = 62
RMCMD_SUPPORTED = frozenset(
    {RMCMD_PWR_MODE_HIGH, RMCMD_LOCK_HIGH, RMCMD_PWR_MODE_LOW, RMCMD_LOCK_LOW}
    | set(range(RMCMD_CAMERA_MIN, RMCMD_USB_LOG_STOP + 1))
)

USB_LOG_ROTATE_SECONDS = 60.0
STRG0_MAX_SENTENCE_BYTES = 192
TIME1_COUNTER = 0

OBS_MAGIC = b"OBS:"
BULK_HEADER = struct.Struct("<4sII")
assert BULK_HEADER.size == 12
assert ADC_PAYLOAD_BYTES == 2048

ADC24_MIN = -(1 << 23)
ADC24_MAX = (1 << 23) - 1


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def adc_rate_sanity() -> tuple[float, float, float]:
    """Return (sample_rate_hz, bulk_rate_hz, bulk_period_s)."""
    sample_rate = float(
        ADC_SAMPLE_RATE_HZ
    )
    bulk_rate = (
        sample_rate
        / ADC_FRAMES_PER_BLOCK
    )
    bulk_period = (
        ADC_FRAMES_PER_BLOCK
        / sample_rate
    )
    return (
        sample_rate,
        bulk_rate,
        bulk_period,
    )


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def nmea_checksum(body: str) -> int:
    """XOR all ASCII bytes between '$' and '*'."""
    checksum = 0
    for byte in body.encode("ascii", errors="replace"):
        checksum ^= byte
    return checksum


def make_sentence(message_id: str, *fields, max_bytes: int = 82) -> bytes:
    """Build one checksum-valid OBS NMEA-style sentence."""
    body = message_id
    if fields:
        body += "," + ",".join(str(x) for x in fields)

    checksum = nmea_checksum(body)
    sentence = f"${body}*{checksum:02X}\r\n"
    encoded = sentence.encode("ascii")
    if len(encoded) > int(max_bytes):
        raise ValueError(
            f"OBS sentence too long: {len(encoded)} bytes > {int(max_bytes)}: {sentence!r}"
        )
    return encoded


def make_strg0(message: str) -> bytes:
    """Build one firmware-style $STRG0 status sentence."""
    return make_sentence("STRG0", str(message), max_bytes=STRG0_MAX_SENTENCE_BYTES)


def time1_week_from_datetime(dt: datetime) -> int:
    """Firmware convention: Sunday=1, Monday=2, ... Saturday=7."""
    return ((int(dt.weekday()) + 1) % 7) + 1

def parse_sentence(line: bytes):
    """
    Validate an incoming NMEA-style sentence.

    Returns:
        (message_id, fields)
    or
        None if invalid.
    """
    try:
        text = line.decode("ascii").rstrip("\r\n")
    except UnicodeDecodeError:
        return None

    if not text.startswith("$"):
        return None

    star = text.rfind("*")
    if star < 2 or star + 3 != len(text):
        return None

    body = text[1:star]
    supplied = text[star + 1:star + 3]

    try:
        supplied_value = int(supplied, 16)
    except ValueError:
        return None

    if nmea_checksum(body) != supplied_value:
        return None

    parts = body.split(",")
    return parts[0], parts[1:]


def twos_complement_24(value: int) -> int:
    """Return a signed 24-bit value as a 24-bit two's-complement integer."""
    value = int(clamp(value, ADC24_MIN, ADC24_MAX))
    return value & 0xFFFFFF



# ---------------------------------------------------------------------------
# OBS binary log playback
# ---------------------------------------------------------------------------

BIN_FILE_MAGIC = 0x4F425342       # specification: "OBSB"
BIN_RECORD_MAGIC = 0x4F425352     # specification: "OBSR"
BIN_FORMAT_VERSION = 1

BIN_FILE_HEADER = struct.Struct("<IIIII")
assert BIN_FILE_HEADER.size == 20

# Current firmware validation confirms that the record header is exactly the
# documented packed field set: 30 bytes. Keep 34-byte support as a compatibility
# variant because an earlier text specification declared that size.
BIN_RECORD_FIELDS = struct.Struct("<III4BHHHhhhh")
assert BIN_RECORD_FIELDS.size == 30
BIN_RECORD_HEADER_SIZE_CURRENT = 30
BIN_RECORD_HEADER_SIZE_COMPAT = 34


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
    measured_sample_rate_hz: float
    rate_deviation_percent: float
    first_record_utc: str
    last_record_utc: str

    @property
    def record_bytes(self) -> int:
        return self.record_header_size + self.payload_bytes

    @property
    def block_period_s(self) -> float:
        return self.frames_per_record / float(self.measured_sample_rate_hz)


@dataclass(frozen=True)
class BinaryLogRecord:
    index: int
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
    latest_adc_values: tuple
    gap_frames: int = 0

    @property
    def time_text(self) -> str:
        return (
            f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}."
            f"{self.milliseconds:03d}"
        )


class OBSBinaryLogReader:
    """Thread-safe sequential reader for the supplied OBS .bin log format."""

    def __init__(self):
        self._lock = threading.RLock()
        self._file = None
        self.header = None
        self.record_index = 0
        self.last_data_cnt = None
        self.last_error = ""

    @staticmethod
    def _filename_base_utc(path: str) -> datetime:
        """Parse OBS_YYYYMMDD_HHMMSS.bin as a UTC filename timestamp."""
        stem = Path(path).stem
        match = re.fullmatch(r"OBS_(\d{8})_(\d{6})", stem, flags=re.IGNORECASE)
        if match is None:
            raise ValueError(
                "Binary log filename must follow OBS_YYYYMMDD_HHMMSS.bin "
                "so record timestamps can be interpreted as UTC."
            )
        return datetime.strptime(
            match.group(1) + match.group(2),
            "%Y%m%d%H%M%S",
        ).replace(tzinfo=timezone.utc)

    def _measure_sample_rate(
        self,
        f,
        *,
        path: str,
        file_size: int,
        record_header_size: int,
        payload_bytes: int,
        nominal_sample_rate_hz: int,
    ):
        """Measure BIN Fs using delta(data_cnt) / delta(record UTC timestamp)."""
        base_dt = self._filename_base_utc(path)

        first_dt = None
        last_dt = None
        first_cnt = None
        last_cnt = None
        previous_dt = None
        valid_records = 0

        f.seek(BIN_FILE_HEADER.size)

        while True:
            record_offset = f.tell()
            raw_header = f.read(record_header_size)
            if not raw_header:
                break
            if len(raw_header) < record_header_size:
                break

            fields = BIN_RECORD_FIELDS.unpack(
                raw_header[:BIN_RECORD_FIELDS.size]
            )
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

            if magic != BIN_RECORD_MAGIC:
                # Measured-rate analysis is intentionally strict. Playback should
                # not silently derive timing from a damaged record stream.
                raise ValueError(
                    f"Record magic mismatch while measuring Fs at offset {record_offset}."
                )

            if f.tell() + payload_bytes > file_size:
                break
            f.seek(payload_bytes, os.SEEK_CUR)

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
                tzinfo=timezone.utc,
            )

            # Same rollover convention used by the converter/checker:
            # a >12 h backwards jump is interpreted as UTC midnight rollover.
            if previous_dt is not None and candidate < previous_dt - timedelta(hours=12):
                while candidate < previous_dt - timedelta(hours=12):
                    candidate += timedelta(days=1)

            if first_dt is None:
                first_dt = candidate
                first_cnt = int(data_cnt)

            last_dt = candidate
            last_cnt = int(data_cnt)
            previous_dt = candidate
            valid_records += 1

        if (
            first_dt is None
            or last_dt is None
            or first_cnt is None
            or last_cnt is None
            or valid_records < 2
        ):
            raise ValueError("Measured sampling rate cannot be derived from this BIN file.")

        duration_s = (last_dt - first_dt).total_seconds()
        frame_delta = int(last_cnt) - int(first_cnt)

        if duration_s <= 0.0 or frame_delta <= 0:
            raise ValueError(
                "Measured sampling rate is invalid: non-positive timestamp span "
                "or data_cnt span."
            )

        measured = float(frame_delta) / float(duration_s)
        if not math.isfinite(measured) or measured <= 0.0:
            raise ValueError("Measured sampling rate is not finite/positive.")

        deviation = (
            (measured - float(nominal_sample_rate_hz))
            / float(nominal_sample_rate_hz)
            * 100.0
        )

        fmt = lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"
        return measured, deviation, fmt(first_dt), fmt(last_dt)

    @staticmethod
    def _signed24_from_word(word: int) -> int:
        value = int(word) & 0xFFFFFF
        if value & 0x800000:
            value -= 1 << 24
        return value

    def close(self):
        with self._lock:
            if self._file is not None:
                try:
                    self._file.close()
                except OSError:
                    pass
            self._file = None

    def _detect_record_header_size(self, f, file_size, payload_bytes):
        data_bytes = max(0, file_size - BIN_FILE_HEADER.size)
        candidates = [BIN_RECORD_HEADER_SIZE_CURRENT, BIN_RECORD_HEADER_SIZE_COMPAT]
        record_magic_bytes = struct.pack("<I", BIN_RECORD_MAGIC)

        # Prefer an exact whole-record fit when only one candidate matches.
        exact = [
            size for size in candidates
            if data_bytes > 0 and data_bytes % (size + payload_bytes) == 0
        ]
        if len(exact) == 1:
            return exact[0]

        # Otherwise inspect the expected boundary of the second record.
        matched = []
        for size in candidates:
            second_offset = BIN_FILE_HEADER.size + size + payload_bytes
            if second_offset + 4 <= file_size:
                f.seek(second_offset)
                if f.read(4) == record_magic_bytes:
                    matched.append(size)
        if len(matched) == 1:
            return matched[0]

        # Current firmware uses the documented packed 30-byte record header.
        return BIN_RECORD_HEADER_SIZE_CURRENT

    def open(self, path: str) -> BinaryLogHeader:
        path = os.path.abspath(path)
        f = open(path, "rb")
        try:
            raw = f.read(BIN_FILE_HEADER.size)
            if len(raw) != BIN_FILE_HEADER.size:
                raise ValueError("Binary log is shorter than the 20-byte file header.")

            magic, version, sample_rate, channels, frames_per_record = (
                BIN_FILE_HEADER.unpack(raw)
            )

            if magic != BIN_FILE_MAGIC:
                raise ValueError(
                    f"Invalid OBS binary log magic 0x{magic:08X}; "
                    f"expected 0x{BIN_FILE_MAGIC:08X}."
                )
            if version != BIN_FORMAT_VERSION:
                raise ValueError(
                    f"Unsupported binary log version {version}; "
                    f"expected {BIN_FORMAT_VERSION}."
                )
            if sample_rate <= 0:
                raise ValueError("Binary log sample rate must be > 0.")
            if channels <= 0 or frames_per_record <= 0:
                raise ValueError("Binary log channel/frame count is invalid.")

            # The TCP bulk protocol implemented by this simulator is fixed at
            # 4 channels x 128 frames = 2048 bytes. Reject incompatible logs
            # rather than silently reshaping or fabricating samples.
            if channels != ADC_CHANNELS:
                raise ValueError(
                    f"Log has {channels} channels; TCP simulator requires "
                    f"{ADC_CHANNELS}."
                )
            if frames_per_record != ADC_FRAMES_PER_BLOCK:
                raise ValueError(
                    f"Log has {frames_per_record} frames/record; TCP simulator "
                    f"requires {ADC_FRAMES_PER_BLOCK}."
                )

            payload_bytes = channels * frames_per_record * 4
            file_size = os.path.getsize(path)
            header_size = self._detect_record_header_size(
                f, file_size, payload_bytes
            )
            record_bytes = header_size + payload_bytes
            estimated = max(0, (file_size - BIN_FILE_HEADER.size) // record_bytes)

            (
                measured_sample_rate_hz,
                rate_deviation_percent,
                first_record_utc,
                last_record_utc,
            ) = self._measure_sample_rate(
                f,
                path=path,
                file_size=file_size,
                record_header_size=header_size,
                payload_bytes=payload_bytes,
                nominal_sample_rate_hz=sample_rate,
            )

            header = BinaryLogHeader(
                path=path,
                version=version,
                sample_rate_hz=sample_rate,
                channels=channels,
                frames_per_record=frames_per_record,
                record_header_size=header_size,
                payload_bytes=payload_bytes,
                estimated_records=estimated,
                file_size=file_size,
                measured_sample_rate_hz=measured_sample_rate_hz,
                rate_deviation_percent=rate_deviation_percent,
                first_record_utc=first_record_utc,
                last_record_utc=last_record_utc,
            )

            with self._lock:
                self.close()
                self._file = f
                self.header = header
                self.record_index = 0
                self.last_data_cnt = None
                self.last_error = ""
                self._file.seek(BIN_FILE_HEADER.size)
            return header
        except (OSError, ValueError, struct.error):
            f.close()
            raise

    def rewind(self):
        with self._lock:
            if self._file is None:
                return
            self._file.seek(BIN_FILE_HEADER.size)
            self.record_index = 0
            self.last_data_cnt = None
            self.last_error = ""

    def _resync_unlocked(self, start_pos: int) -> bool:
        if self._file is None:
            return False
        marker = struct.pack("<I", BIN_RECORD_MAGIC)
        self._file.seek(start_pos)
        overlap = b""
        absolute = start_pos
        while True:
            chunk = self._file.read(64 * 1024)
            if not chunk:
                return False
            data = overlap + chunk
            pos = data.find(marker)
            if pos >= 0:
                found = absolute - len(overlap) + pos
                self._file.seek(found)
                return True
            overlap = data[-3:]
            absolute += len(chunk)

    def next_record(self, loop: bool = False):
        with self._lock:
            if self._file is None or self.header is None:
                return None

            for attempt in range(2):
                start_pos = self._file.tell()
                raw_header = self._file.read(self.header.record_header_size)

                if len(raw_header) == 0:
                    if loop:
                        self.rewind()
                        continue
                    return None

                if len(raw_header) < self.header.record_header_size:
                    self.last_error = (
                        f"Truncated record header at file offset {start_pos}."
                    )
                    if loop:
                        self.rewind()
                        continue
                    return None

                fields = BIN_RECORD_FIELDS.unpack(
                    raw_header[:BIN_RECORD_FIELDS.size]
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

                if magic != BIN_RECORD_MAGIC:
                    self.last_error = (
                        f"Record magic mismatch at offset {start_pos}; "
                        "attempting resync."
                    )
                    if self._resync_unlocked(start_pos + 1):
                        continue
                    if loop:
                        self.rewind()
                        continue
                    return None

                payload = self._file.read(self.header.payload_bytes)
                if len(payload) != self.header.payload_bytes:
                    self.last_error = (
                        f"Truncated ADC payload at record {self.record_index + 1}."
                    )
                    if loop:
                        self.rewind()
                        continue
                    return None

                gap_frames = 0
                if self.last_data_cnt is not None:
                    expected = (
                        self.last_data_cnt + self.header.frames_per_record
                    ) & 0xFFFFFFFF
                    if data_cnt != expected:
                        gap_frames = (data_cnt - expected) & 0xFFFFFFFF

                self.last_data_cnt = data_cnt
                self.record_index += 1

                last_frame_offset = (
                    (self.header.frames_per_record - 1)
                    * self.header.channels
                    * 4
                )
                words = struct.unpack_from(
                    "<" + "I" * self.header.channels,
                    payload,
                    last_frame_offset,
                )
                latest = tuple(
                    self._signed24_from_word(word)
                    for word in words[:ADC_CHANNELS]
                )

                return BinaryLogRecord(
                    index=self.record_index,
                    data_cnt=data_cnt,
                    frame_base_idx=frame_base_idx,
                    hours=hours,
                    minutes=minutes,
                    seconds=seconds,
                    milliseconds=milliseconds,
                    depth_m=depth_raw * 0.1,
                    temperature_c=temp_raw * 0.01,
                    roll_deg=roll_raw * 0.1,
                    pitch_deg=pitch_raw * 0.1,
                    yaw_deg=yaw_raw * 0.1,
                    payload=payload,
                    latest_adc_values=latest,
                    gap_frames=gap_frames,
                )

            return None


# ---------------------------------------------------------------------------
# Simulation state
# ---------------------------------------------------------------------------

@dataclass
class ADCChannel:
    enabled: bool = True
    frequency_hz: float = 10.0
    amplitude: int = 4_000_000
    offset: int = 0
    phase_deg: float = 0.0

    # Status byte:
    # bit7 ERROR
    # bit6 FILTER NOT SETTLED
    # bit5 REPEATED
    # bit4 FILTER TYPE
    # bit3 FILTER SATURATED
    # bit2..0 CHANNEL ID
    error: bool = False
    filter_not_settled: bool = False
    repeated: bool = False
    filter_type: bool = False
    filter_saturated: bool = False


@dataclass
class TelemetryState:
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    depth: float = 10.0
    depth_rate: float = 0.0
    temperature: float = 25.0

    angular_p: float = 0.0
    angular_q: float = 0.0
    angular_r: float = 0.0

    # Controller-health simulator value. This is NOT sourced from USB BIN.
    vmon0_v: float = 6.4

    unit_id: int = DEVICE_ID
    processor_status: int = 0

    adc: list = field(default_factory=lambda: [
        ADCChannel(True, 10.0, 4_000_000, 0, 0.0),
        ADCChannel(True, 20.0, 4_000_000, 0, 90.0),
        ADCChannel(True, 30.0, 4_000_000, 0, 180.0),
        ADCChannel(True, 40.0, 4_000_000, 0, 270.0),
    ])


class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = TelemetryState()
        self._device_clock_offset_s = 0.0
        self._adc_source_mode = "control"
        self.gimbal_locked = True
        self.power_mode = "NORMAL"
        self.last_camera_rmcmd = 0

    def update_navigation(
        self,
        roll,
        pitch,
        yaw,
        depth,
        depth_rate,
        temperature,
        angular_p,
        angular_q,
        angular_r,
    ):
        with self._lock:
            s = self._state
            s.roll = float(roll)
            s.pitch = float(pitch)
            s.yaw = float(yaw)
            s.depth = float(depth)
            s.depth_rate = float(depth_rate)
            s.temperature = float(temperature)
            s.angular_p = float(angular_p)
            s.angular_q = float(angular_q)
            s.angular_r = float(angular_r)

    def update_log_navigation(
        self,
        roll,
        pitch,
        yaw,
        depth,
        temperature,
    ):
        """Apply ancillary sensor values contained in one binary-log record."""
        with self._lock:
            s = self._state
            s.roll = float(roll)
            s.pitch = float(pitch)
            s.yaw = float(yaw)
            s.depth = float(depth)
            s.depth_rate = 0.0
            s.temperature = float(temperature)
            # P/Q/R are not present in TBinLogRecordHdr; do not synthesize them.
            s.angular_p = 0.0
            s.angular_q = 0.0
            s.angular_r = 0.0

    def update_adc(
        self,
        index,
        enabled,
        frequency_hz,
        amplitude,
        offset,
        phase_deg,
        error=False,
        filter_not_settled=False,
        repeated=False,
        filter_type=False,
        filter_saturated=False,
    ):
        with self._lock:
            ch = self._state.adc[index]
            ch.enabled = bool(enabled)
            ch.frequency_hz = max(0.0, float(frequency_hz))
            ch.amplitude = int(clamp(int(amplitude), 0, ADC24_MAX))
            ch.offset = int(clamp(int(offset), ADC24_MIN, ADC24_MAX))
            ch.phase_deg = float(phase_deg)
            ch.error = bool(error)
            ch.filter_not_settled = bool(filter_not_settled)
            ch.repeated = bool(repeated)
            ch.filter_type = bool(filter_type)
            ch.filter_saturated = bool(filter_saturated)

    def set_adc_source_mode(self, mode: str) -> None:
        mode = str(mode)
        if mode not in ("control", "log"):
            raise ValueError(f"Unknown ADC source mode: {mode}")
        with self._lock:
            self._adc_source_mode = mode

    def adc_source_mode(self) -> str:
        with self._lock:
            return str(self._adc_source_mode)

    def update_controller_simulation(self, vmon0_v: float) -> None:
        with self._lock:
            self._state.vmon0_v = max(0.0, float(vmon0_v))

    def device_datetime(self) -> datetime:
        """Return the simulator/OBS device clock as timezone-aware UTC."""
        with self._lock:
            offset_s = float(self._device_clock_offset_s)
        return datetime.now(timezone.utc) + timedelta(seconds=offset_s)

    def set_device_time_from_time1(self, fields) -> datetime:
        if len(fields) < 8:
            raise ValueError("TIME1 requires at least 8 fields")
        values = [int(str(value), 10) for value in fields[:9]]
        milliseconds, year, month = values[0], values[1], values[2]
        date, hours, minutes, seconds = values[4], values[5], values[6], values[7]
        if not (0 <= milliseconds <= 999):
            raise ValueError("TIME1 milliseconds must be 0..999")
        if 0 <= year <= 99:
            year += 2000
        target = datetime(
            year,
            month,
            date,
            hours,
            minutes,
            seconds,
            milliseconds * 1000,
            tzinfo=timezone.utc,
        )
        now = datetime.now(timezone.utc)
        with self._lock:
            self._device_clock_offset_s = (target - now).total_seconds()
        return target

    def apply_rmcmd(self, code: int) -> str:
        code = int(code)
        with self._lock:
            if code == RMCMD_PWR_MODE_HIGH:
                self.power_mode = "LOW"
                return "PWR_MODE HIGH / LOW POWER"
            if code == RMCMD_LOCK_HIGH:
                self.gimbal_locked = True
                return "GIMBAL LOCKED"
            if code == RMCMD_PWR_MODE_LOW:
                self.power_mode = "NORMAL"
                return "PWR_MODE LOW / NORMAL"
            if code == RMCMD_LOCK_LOW:
                self.gimbal_locked = False
                return "GIMBAL UNLOCKED"
            if RMCMD_CAMERA_MIN <= code <= RMCMD_CAMERA_MAX:
                self.last_camera_rmcmd = code
                return f"CAMERA RMCMD {code}"
        return f"RMCMD {code}"

    def snapshot(self):
        with self._lock:
            s = self._state
            return TelemetryState(
                roll=s.roll,
                pitch=s.pitch,
                yaw=s.yaw,
                depth=s.depth,
                depth_rate=s.depth_rate,
                temperature=s.temperature,
                angular_p=s.angular_p,
                angular_q=s.angular_q,
                angular_r=s.angular_r,
                vmon0_v=s.vmon0_v,
                unit_id=s.unit_id,
                processor_status=s.processor_status,
                adc=[
                    ADCChannel(
                        enabled=ch.enabled,
                        frequency_hz=ch.frequency_hz,
                        amplitude=ch.amplitude,
                        offset=ch.offset,
                        phase_deg=ch.phase_deg,
                        error=ch.error,
                        filter_not_settled=ch.filter_not_settled,
                        repeated=ch.repeated,
                        filter_type=ch.filter_type,
                        filter_saturated=ch.filter_saturated,
                    )
                    for ch in s.adc
                ],
            )


# ---------------------------------------------------------------------------
# Command / Telemetry TCP server
# ---------------------------------------------------------------------------

class CommandServer:
    def __init__(self, shared_state, event_queue):
        self.shared_state = shared_state
        self.events = event_queue

        self.stop_event = threading.Event()
        self.thread = None
        self.server_socket = None

        self.clients = []
        self.clients_lock = threading.Lock()

        self.sequence = 0
        self.sent_sentences = 0
        self.sent_bytes = 0
        self.usb_device_present = True
        self.usb_media_present = True
        self.usb_logger_active = False
        self.usb_current_filename = ""
        self.usb_open_monotonic = 0.0

    def log(self, message):
        self.events.put(("log", message))

    def status(self, message):
        self.events.put(("command_status", message))

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            name="CommandServer",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()

        with self.clients_lock:
            clients = list(self.clients)
            self.clients.clear()

        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass

        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

    def _remove_client(self, client):
        with self.clients_lock:
            if client in self.clients:
                self.clients.remove(client)

        try:
            client.close()
        except OSError:
            pass

    def _broadcast(self, data):
        dead = []

        with self.clients_lock:
            clients = list(self.clients)

        for client in clients:
            try:
                client.sendall(data)
                self.sent_sentences += 1
                self.sent_bytes += len(data)
            except OSError:
                dead.append(client)

        for client in dead:
            self._remove_client(client)

    def _send_to_client(self, client, data: bytes) -> None:
        client.sendall(data)
        self.sent_sentences += 1
        self.sent_bytes += len(data)

    def _broadcast_strg0(self, message: str) -> None:
        payload = make_strg0(message)
        self._broadcast(payload)
        self.log(f"STRG0 TX {message}")

    def _new_usb_filename(self) -> str:
        # Current OBS policy is UTC end-to-end: TIME1, device clock and BIN filename.
        now = self.shared_state.device_datetime().astimezone(timezone.utc)
        return f"OBS_{now:%Y%m%d_%H%M%S}.bin"

    def _start_usb_logger(self) -> None:
        if not self.usb_device_present or not self.usb_media_present:
            self._broadcast_strg0("USB_NO_DEVICE_CONNECTED")
            return
        if self.usb_logger_active:
            return
        self.usb_logger_active = True
        self.usb_current_filename = self._new_usb_filename()
        self.usb_open_monotonic = time.monotonic()
        self._broadcast_strg0(f"MSDV_FILE_OPENED:{self.usb_current_filename}")

    def _stop_usb_logger(self) -> None:
        if not self.usb_logger_active:
            return
        filename = self.usb_current_filename
        self.usb_logger_active = False
        self.usb_current_filename = ""
        self.usb_open_monotonic = 0.0
        self._broadcast_strg0(f"MSDV_FILE_CLOSED:{filename}")

    def _rotate_usb_logger_if_needed(self) -> None:
        if not self.usb_logger_active:
            return
        if time.monotonic() - self.usb_open_monotonic < USB_LOG_ROTATE_SECONDS:
            return
        old_name = self.usb_current_filename
        self._broadcast_strg0(f"MSDV_FILE_CLOSED:{old_name}")
        self.usb_current_filename = self._new_usb_filename()
        self.usb_open_monotonic = time.monotonic()
        self._broadcast_strg0(f"MSDV_FILE_OPENED:{self.usb_current_filename}")

    def _send_initial_usb_status(self, client) -> None:
        statuses = [
            "USB_DEVICE_CONNECTION" if self.usb_device_present else "USB_NO_DEVICE_CONNECTED",
        ]
        if self.usb_device_present and self.usb_media_present:
            statuses.append("USB_STORAGE_MEDIA_INSERTION")
        if self.usb_logger_active and self.usb_current_filename:
            statuses.append(f"MSDV_FILE_OPENED:{self.usb_current_filename}")
        for message in statuses:
            self._send_to_client(client, make_strg0(message))

    def _client_reader(self, client, address):
        buffer = bytearray()

        try:
            client.settimeout(0.5)

            while not self.stop_event.is_set():
                try:
                    data = client.recv(4096)
                except socket.timeout:
                    continue

                if not data:
                    break

                buffer.extend(data)

                while b"\n" in buffer:
                    pos = buffer.index(b"\n") + 1
                    line = bytes(buffer[:pos])
                    del buffer[:pos]

                    if len(line) > 82:
                        self.log(
                            f"COMMAND RX too long from {address[0]}:{address[1]}"
                        )
                        continue

                    parsed = parse_sentence(line)
                    if parsed is None:
                        self.log(
                            f"COMMAND RX invalid checksum/frame "
                            f"from {address[0]}:{address[1]}"
                        )
                        continue

                    message_id, fields = parsed
                    self.log(
                        f"COMMAND RX {message_id}"
                        + (f" fields={fields}" if fields else "")
                    )
                    self._handle_command(client, message_id, fields)

        except OSError:
            pass
        finally:
            self._remove_client(client)
            self.log(f"Command client disconnected: {address[0]}:{address[1]}")

    def _handle_command(self, client, message_id, fields):
        """Handle requests/commands used by obs_setting_v22.py."""
        try:
            if message_id == "XFWVR":
                self._send_to_client(client, make_sentence(
                    "XFWVR", FIRMWARE_VERSION, FIRMWARE_DATE, UNIT_TITLE
                ))
            elif message_id == "XCHM0":
                state = self.shared_state.snapshot()
                self._send_to_client(client, make_sentence(
                    "XCHM0", f"{state.unit_id:04X}", f"{state.processor_status:02X}"
                ))
            elif message_id == "TIME1":
                target = self.shared_state.set_device_time_from_time1(fields)
                self.log(
                    f"TIME1 applied -> {target:%Y-%m-%d %H:%M:%S}."
                    f"{target.microsecond // 1000:03d}"
                )
                self._send_to_client(client, self._make_time1())
            elif message_id == "RMCMD":
                if not fields:
                    raise ValueError("RMCMD requires command code")
                code = int(str(fields[0]), 10)
                if code not in RMCMD_SUPPORTED:
                    self.log(f"RMCMD {code} unsupported by simulator")
                    return
                description = self.shared_state.apply_rmcmd(code)
                self.log(f"RMCMD {code} -> {description}")
                if code == RMCMD_USB_LOG_START:
                    self._start_usb_logger()
                elif code == RMCMD_USB_LOG_STOP:
                    self._stop_usb_logger()
        except (OSError, ValueError) as exc:
            self.log(f"COMMAND handling error for {message_id}: {exc}")
            if isinstance(exc, OSError):
                self._remove_client(client)

    def _make_gdat2(self, sequence):
        """
        GDAT2:
          10 hexadecimal diagnostic fields + sequence/counter.

        Fields are intentionally compact so the sentence stays below 82 bytes.
        """
        state = self.shared_state.snapshot()

        # Example diagnostic bytes:
        # ADC channel health + system flags.
        diag = []
        for i, ch in enumerate(state.adc):
            status = (
                (0x80 if ch.error else 0)
                | (0x40 if ch.filter_not_settled else 0)
                | (0x20 if ch.repeated else 0)
                | (0x10 if ch.filter_type else 0)
                | (0x08 if ch.filter_saturated else 0)
                | (i & 0x07)
            )
            diag.append(status)

        diag.extend([
            0x00,  # reserved
            0x00,  # reserved
            0x00,  # reserved
            state.processor_status & 0xFF,
            0x00,  # reserved
            0x00,  # reserved
        ])

        return make_sentence(
            "GDAT2",
            *(f"{x:02X}" for x in diag[:10]),
            f"{sequence & 0xFFFFFFFF:08X}",
        )

    def _make_time1(self):
        now = self.shared_state.device_datetime()
        return make_sentence(
            "TIME1",
            now.microsecond // 1000,
            now.year % 100,
            now.month,
            time1_week_from_datetime(now),
            now.day,
            now.hour,
            now.minute,
            now.second,
            TIME1_COUNTER,
        )

    def _make_dept0(self):
        state = self.shared_state.snapshot()
        pressure_raw_e1 = int(round(float(state.depth) * 10.0))
        temperature_raw_e2 = int(round(float(state.temperature) * 100.0))
        return make_sentence(
            "DEPT0", pressure_raw_e1, f"{state.depth_rate:.3f}", temperature_raw_e2
        )

    def _make_ahrs2(self):
        state = self.shared_state.snapshot()
        return make_sentence(
            "AHRS2",
            int(round(float(state.roll) * 10.0)),
            int(round(float(state.pitch) * 10.0)),
            int(round(float(state.yaw) * 10.0)),
            f"{state.angular_p:.3f}",
            f"{state.angular_q:.3f}",
            f"{state.angular_r:.3f}",
            f"{state.unit_id:04X}",
        )

    def _make_xchm1(self):
        state = self.shared_state.snapshot()
        vmon0_raw_e1 = int(round(float(state.vmon0_v) * 10.0))

        # Current OBS runtime only uses VMON0 as the simulated battery/rail value.
        # VMON1/2/3, TEMP, PMON and HMON are not populated by this simulator.
        return make_sentence(
            "XCHM1",
            vmon0_raw_e1,                    # VMON0, E1 raw (V * 10)
            0,                               # VMON1
            0,                               # VMON2
            0,                               # VMON3
            0,                               # TEMP (reserved here)
            0,                               # PMON
            0,                               # HMON
            0,                               # LMON
            int(state.processor_status) & 0xFF,
            int(state.unit_id) & 0xFF,
            self.sequence & 0xFF,
        )

    def _telemetry_loop(self):
        next_tx = time.perf_counter()

        while not self.stop_event.is_set():
            now = time.perf_counter()
            remaining = next_tx - now

            if remaining > 0:
                time.sleep(min(remaining, 0.02))
                continue

            self.sequence = (self.sequence + 1) & 0xFFFFFFFF

            try:
                self._rotate_usb_logger_if_needed()
                messages = [
                    self._make_gdat2(self.sequence),
                    self._make_time1(),
                    self._make_dept0(),
                    self._make_ahrs2(),
                ]

                # USB BIN records do not contain VMON/controller-health data.
                # Therefore XCHM1 is emitted only in Generated / Control mode.
                if self.shared_state.adc_source_mode() == "control":
                    messages.append(self._make_xchm1())

                for message in messages:
                    self._broadcast(message)

            except ValueError as exc:
                self.log(f"Telemetry build error: {exc}")

            next_tx += COMMAND_PERIOD_S

            # Resync after a long stall.
            if time.perf_counter() - next_tx > 1.0:
                next_tx = time.perf_counter() + COMMAND_PERIOD_S

    def _run(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket = srv
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((HOST, COMMAND_PORT))
            srv.listen(MAX_COMMAND_CLIENTS)
            srv.settimeout(0.5)

            self.log(
                f"Command server aktif di {HOST}:{COMMAND_PORT} "
                f"(max {MAX_COMMAND_CLIENTS} clients)"
            )

            threading.Thread(
                target=self._telemetry_loop,
                name="TelemetryLoop",
                daemon=True,
            ).start()

            self.status("LISTENING")

            while not self.stop_event.is_set():
                try:
                    client, address = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                with self.clients_lock:
                    if len(self.clients) >= MAX_COMMAND_CLIENTS:
                        try:
                            client.sendall(
                                make_sentence("XCHM0", "FFFF", "01")
                            )
                        except OSError:
                            pass
                        client.close()
                        self.log(
                            f"Command connection rejected: max "
                            f"{MAX_COMMAND_CLIENTS} clients"
                        )
                        continue

                    self.clients.append(client)

                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                self.log(
                    f"Command client connected: "
                    f"{address[0]}:{address[1]}"
                )
                self.status(
                    f"CONNECTED ({len(self.clients)}/{MAX_COMMAND_CLIENTS})"
                )
                try:
                    self._send_initial_usb_status(client)
                except OSError:
                    self._remove_client(client)
                    continue

                threading.Thread(
                    target=self._client_reader,
                    args=(client, address),
                    name=f"CommandClient-{address[1]}",
                    daemon=True,
                ).start()

        except OSError as exc:
            if not self.stop_event.is_set():
                self.log(f"Command server ERROR: {exc}")
                self.status("ERROR")
        finally:
            self.stop()
            self.status("STOPPED")
            self.log("Command server stopped.")


# ---------------------------------------------------------------------------
# Bulk ADC server
# ---------------------------------------------------------------------------

class BulkServer:
    def __init__(self, shared_state, event_queue):
        self.shared_state = shared_state
        self.events = event_queue

        self.stop_event = threading.Event()
        self.thread = None
        self.server_socket = None

        self.clients = []
        self.clients_lock = threading.Lock()

        self.sequence = 0
        self.frame_count = 0
        self.byte_count = 0

        # Continuous ADC sample counter so waveform phase never resets
        # at the boundary of each 128-sample bulk block.
        self.sample_index = 0

        self.start_time = time.perf_counter()

        # ADC source selection. Generated/control mode is the legacy source;
        # binary-log mode replays raw uint32 ADC words without re-encoding them.
        self.source_lock = threading.RLock()
        self.source_mode = "control"
        self.log_reader = OBSBinaryLogReader()
        self.log_playing = False
        self.log_loop = False
        self.log_eof = False
        self.log_status = "NO FILE"
        self.latest_log_record = None
        self.latest_adc_values = [0] * ADC_CHANNELS
        self.stats_lock = threading.Lock()

    def log(self, message):
        self.events.put(("log", message))

    def status(self, message):
        self.events.put(("bulk_status", message))

    def _reset_stats(self):
        with self.stats_lock:
            self.frame_count = 0
            self.byte_count = 0
            self.start_time = time.perf_counter()

    def load_log_file(self, path):
        header = self.log_reader.open(path)
        with self.source_lock:
            self.source_mode = "log"
            self.log_playing = False
            self.log_eof = False
            self.log_status = "READY"
            self.latest_log_record = None
            self.sample_index = 0
        self.shared_state.set_adc_source_mode("log")
        self._reset_stats()
        self.log(
            f"Binary log loaded: {os.path.basename(header.path)} | "
            f"Header Fs={header.sample_rate_hz} Hz | "
            f"Measured Fs={header.measured_sample_rate_hz:.6f} Hz | "
            f"Deviation={header.rate_deviation_percent:+.6f}% | "
            f"CH={header.channels} | frames/record={header.frames_per_record} | "
            f"record header={header.record_header_size} bytes | "
            f"records~{header.estimated_records}"
        )
        self.log(
            f"Binary playback rate AUTO -> {header.measured_sample_rate_hz:.6f} Hz "
            "(measured from data_cnt / record UTC timestamp span)"
        )
        return header

    def set_source_mode(self, mode):
        if mode not in ("control", "log"):
            raise ValueError(f"Unknown ADC source mode: {mode}")
        with self.source_lock:
            if mode == "log" and self.log_reader.header is None:
                raise ValueError("Load an OBS binary log before selecting log mode.")
            self.source_mode = mode
            if mode == "control":
                self.log_playing = False
                self.log_status = "CONTROL PANEL"
            else:
                self.log_status = "PLAYING" if self.log_playing else "READY"
        self.shared_state.set_adc_source_mode(mode)
        self._reset_stats()
        self.log(
            "ADC source -> "
            + ("Generated / Control Panel" if mode == "control" else "Binary Log")
        )

    def play_log(self):
        with self.source_lock:
            if self.log_reader.header is None:
                raise ValueError("No OBS binary log loaded.")
            if self.log_eof:
                self.log_reader.rewind()
                self.log_eof = False
            self.source_mode = "log"
            self.log_playing = True
            self.log_status = "PLAYING"
        self.shared_state.set_adc_source_mode("log")
        self._reset_stats()
        self.log("Binary log playback started.")

    def pause_log(self):
        with self.source_lock:
            if self.source_mode == "log":
                self.log_playing = False
                self.log_status = "PAUSED"
        self.log("Binary log playback paused.")

    def stop_log(self):
        with self.source_lock:
            self.log_playing = False
            self.log_eof = False
            self.log_reader.rewind()
            self.latest_log_record = None
            if self.log_reader.header is not None:
                self.log_status = "READY / REWOUND"
            else:
                self.log_status = "NO FILE"
        self._reset_stats()
        self.log("Binary log playback stopped and rewound.")

    def set_log_loop(self, enabled):
        with self.source_lock:
            self.log_loop = bool(enabled)

    def source_snapshot(self):
        with self.source_lock:
            header = self.log_reader.header
            record = self.latest_log_record
            mode = self.source_mode
            playing = self.log_playing
            status = self.log_status
            loop = self.log_loop
            eof = self.log_eof
            latest = tuple(self.latest_adc_values)
        return {
            "mode": mode,
            "playing": playing,
            "status": status,
            "loop": loop,
            "eof": eof,
            "header": header,
            "record": record,
            "latest_adc_values": latest,
            "target_sample_rate_hz": (
                float(header.measured_sample_rate_hz)
                if mode == "log" and header is not None
                else float(ADC_SAMPLE_RATE_HZ)
            ),
        }

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self._reset_stats()

        self.thread = threading.Thread(
            target=self._run,
            name="BulkServer",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()

        with self.clients_lock:
            clients = list(self.clients)
            self.clients.clear()

        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass

        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

    def _remove_client(self, client):
        with self.clients_lock:
            if client in self.clients:
                self.clients.remove(client)

        try:
            client.close()
        except OSError:
            pass

    @staticmethod
    def _adc_value(ch: ADCChannel, elapsed_s: float) -> int:
        if not ch.enabled:
            return int(clamp(ch.offset, ADC24_MIN, ADC24_MAX))

        phase_rad = math.radians(ch.phase_deg)

        value = ch.offset + ch.amplitude * math.sin(
            2.0 * math.pi * ch.frequency_hz * elapsed_s + phase_rad
        )

        return int(clamp(round(value), ADC24_MIN, ADC24_MAX))

    @staticmethod
    def _status_byte(ch: ADCChannel, channel_index: int) -> int:
        return (
            (0x80 if ch.error else 0)
            | (0x40 if ch.filter_not_settled else 0)
            | (0x20 if ch.repeated else 0)
            | (0x10 if ch.filter_type else 0)
            | (0x08 if ch.filter_saturated else 0)
            | (channel_index & 0x07)
        )

    def _build_block(self, state):
        words = []

        # Generate samples from a global sample index instead of the
        # scheduler's current time. This keeps the waveform phase continuous
        # across consecutive 128-sample bulk blocks.
        block_start_index = self.sample_index

        # 128 ADC frames, each with CH0(N) CH1(E) CH2(Z) CH3(AUX).
        last_values = [0] * ADC_CHANNELS
        for frame in range(ADC_FRAMES_PER_BLOCK):
            sample_number = block_start_index + frame
            elapsed_s = sample_number / ADC_SAMPLE_RATE_HZ

            for channel_index, ch in enumerate(state.adc):
                value = self._adc_value(ch, elapsed_s)
                status = self._status_byte(ch, channel_index)

                # Low 24 bits = signed ADC result in two's complement.
                # High 8 bits = channel status.
                word = (status << 24) | twos_complement_24(value)
                words.append(word)
                if frame == ADC_FRAMES_PER_BLOCK - 1:
                    last_values[channel_index] = value

        self.sample_index += ADC_FRAMES_PER_BLOCK
        with self.source_lock:
            self.latest_adc_values = last_values

        payload = struct.pack(
            "<" + ("I" * len(words)),
            *words,
        )

        assert len(payload) == ADC_PAYLOAD_BYTES

        header = BULK_HEADER.pack(
            OBS_MAGIC,
            self.sequence,
            len(payload),
        )

        self.sequence = (self.sequence + 1) & 0xFFFFFFFF

        return header + payload

    def _build_log_block(self):
        with self.source_lock:
            loop = self.log_loop

        record = self.log_reader.next_record(loop=loop)
        if record is None:
            with self.source_lock:
                self.log_playing = False
                self.log_eof = True
                self.log_status = (
                    "EOF" if not self.log_reader.last_error
                    else "EOF / PARTIAL OR CORRUPT RECORD"
                )
            if self.log_reader.last_error:
                self.log(f"Binary log: {self.log_reader.last_error}")
            self.log("Binary log reached EOF; bulk transmission paused.")
            return None

        # Preserve the exact 2048-byte raw ADC payload from the file.
        # Only the simulator's 12-byte TCP transport header is regenerated.
        payload = record.payload
        header = BULK_HEADER.pack(
            OBS_MAGIC,
            self.sequence,
            len(payload),
        )
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        self.sample_index += ADC_FRAMES_PER_BLOCK

        self.shared_state.update_log_navigation(
            record.roll_deg,
            record.pitch_deg,
            record.yaw_deg,
            record.depth_m,
            record.temperature_c,
        )

        with self.source_lock:
            self.latest_log_record = record
            self.latest_adc_values = list(record.latest_adc_values)
            self.log_status = "PLAYING"

        if record.gap_frames:
            self.log(
                f"Binary log data counter gap before record {record.index}: "
                f"{record.gap_frames} frame(s)."
            )

        return header + payload

    def _broadcast_block(self, frame):
        dead = []

        with self.clients_lock:
            clients = list(self.clients)

        for client in clients:
            try:
                client.sendall(frame)
            except OSError:
                dead.append(client)

        for client in dead:
            self._remove_client(client)

        with self.stats_lock:
            self.frame_count += 1
            self.byte_count += len(frame)

    def _run(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket = srv
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((HOST, BULK_PORT))
            srv.listen(MAX_BULK_CLIENTS)
            srv.settimeout(BULK_ACCEPT_TIMEOUT_S)

            self.log(
                f"Bulk server aktif di {HOST}:{BULK_PORT} "
                f"(max {MAX_BULK_CLIENTS} clients)"
            )
            self.log(
                f"Bulk frame = 12 + {ADC_PAYLOAD_BYTES} = "
                f"{12 + ADC_PAYLOAD_BYTES} bytes, "
                f"{ADC_FRAMES_PER_BLOCK} ADC frames/frame"
            )
            self.log(
                f"ADC target = {ADC_SAMPLE_RATE_HZ:.1f} frames/s/channel | "
                f"bulk target = {ADC_SAMPLE_RATE_HZ / ADC_FRAMES_PER_BLOCK:.4f} blocks/s | "
                f"period = {BULK_PERIOD_S * 1000.0:.3f} ms"
            )
            self.status("LISTENING")

            next_tx = time.perf_counter()

            while not self.stop_event.is_set():
                # Accept clients without blocking the data scheduler.
                try:
                    client, address = srv.accept()

                    with self.clients_lock:
                        if len(self.clients) >= MAX_BULK_CLIENTS:
                            client.close()
                            self.log(
                                f"Bulk connection rejected: max "
                                f"{MAX_BULK_CLIENTS} clients"
                            )
                        else:
                            client.setsockopt(
                                socket.IPPROTO_TCP,
                                socket.TCP_NODELAY,
                                1,
                            )
                            self.clients.append(client)
                            self.log(
                                f"Bulk client connected: "
                                f"{address[0]}:{address[1]}"
                            )
                            self.status(
                                f"CONNECTED "
                                f"({len(self.clients)}/{MAX_BULK_CLIENTS})"
                            )
                except socket.timeout:
                    pass
                except OSError:
                    break

                now = time.perf_counter()

                if now < next_tx:
                    time.sleep(min(next_tx - now, 0.002))
                    continue

                source = self.source_snapshot()

                if source["mode"] == "log":
                    if not source["playing"]:
                        next_tx = time.perf_counter() + 0.02
                        time.sleep(0.005)
                        continue
                    header_info = source["header"]
                    if header_info is not None:
                        playback_rate = max(
                            float(source["target_sample_rate_hz"]),
                            1.0,
                        )
                        period_s = (
                            float(header_info.frames_per_record)
                            / playback_rate
                        )
                    else:
                        period_s = BULK_PERIOD_S
                else:
                    period_s = BULK_PERIOD_S

                try:
                    if source["mode"] == "log":
                        frame = self._build_log_block()
                        if frame is None:
                            next_tx = time.perf_counter() + 0.02
                            continue
                    else:
                        state = self.shared_state.snapshot()
                        frame = self._build_block(state)

                    self._broadcast_block(frame)
                except (OSError, ValueError, struct.error) as exc:
                    self.log(f"Bulk TX error: {exc}")

                next_tx += period_s

                if time.perf_counter() - next_tx > 0.5:
                    next_tx = time.perf_counter() + period_s

        except OSError as exc:
            if not self.stop_event.is_set():
                self.log(f"Bulk server ERROR: {exc}")
                self.status("ERROR")
        finally:
            self.stop()
            self.status("STOPPED")
            self.log("Bulk server stopped.")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class ModernSlider(tk.Canvas):
    """Flat, responsive slider with precise mouse and keyboard interaction."""

    def __init__(
        self,
        master,
        variable,
        from_,
        to,
        resolution=0.1,
        *,
        bg="#07151F",
        track="#17384A",
        fill="#41A9D8",
        thumb="#DDF4FF",
        thumb_border="#52B9E8",
        focus="#79CFF2",
        width=360,
        height=30,
        **kwargs,
    ):
        super().__init__(
            master,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=1,
            highlightbackground=bg,
            highlightcolor=focus,
            bd=0,
            relief="flat",
            takefocus=1,
            cursor="hand2",
            **kwargs,
        )
        self.variable = variable
        self.minimum = float(from_)
        self.maximum = float(to)
        self.resolution = abs(float(resolution)) or 1.0
        self.track_color = track
        self.fill_color = fill
        self.thumb_color = thumb
        self.thumb_border = thumb_border
        self.focus_color = focus
        self._hover = False
        self._dragging = False
        self._pad_x = 13
        self._track_y = height // 2
        self._trace_id = self.variable.trace_add("write", self._on_variable_changed)

        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<FocusIn>", self._redraw)
        self.bind("<FocusOut>", self._redraw)
        self.bind("<Left>", lambda _e: self._move_steps(-1))
        self.bind("<Down>", lambda _e: self._move_steps(-1))
        self.bind("<Right>", lambda _e: self._move_steps(+1))
        self.bind("<Up>", lambda _e: self._move_steps(+1))
        self.bind("<Prior>", lambda _e: self._move_steps(+10))
        self.bind("<Next>", lambda _e: self._move_steps(-10))
        self.bind("<Home>", lambda _e: self._set_value(self.minimum))
        self.bind("<End>", lambda _e: self._set_value(self.maximum))
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.after_idle(self._redraw)

    def _on_destroy(self, _event=None):
        try:
            if self._trace_id:
                self.variable.trace_remove("write", self._trace_id)
                self._trace_id = None
        except (tk.TclError, AttributeError):
            pass

    def _quantize(self, value):
        value = clamp(float(value), min(self.minimum, self.maximum), max(self.minimum, self.maximum))
        base = self.minimum
        if self.resolution > 0:
            value = base + round((value - base) / self.resolution) * self.resolution
        value = clamp(value, min(self.minimum, self.maximum), max(self.minimum, self.maximum))
        return value

    def _set_value(self, value):
        value = self._quantize(value)
        try:
            if isinstance(self.variable, tk.IntVar):
                self.variable.set(int(round(value)))
            else:
                self.variable.set(float(value))
        except tk.TclError:
            pass
        return "break"

    def _move_steps(self, steps):
        try:
            current = float(self.variable.get())
        except (tk.TclError, TypeError, ValueError):
            current = self.minimum
        return self._set_value(current + float(steps) * self.resolution)

    def _value_from_x(self, x):
        width = max(self.winfo_width(), 2 * self._pad_x + 1)
        left = self._pad_x
        right = width - self._pad_x
        ratio = clamp((float(x) - left) / max(1.0, right - left), 0.0, 1.0)
        return self.minimum + ratio * (self.maximum - self.minimum)

    def _x_from_value(self, value):
        width = max(self.winfo_width(), 2 * self._pad_x + 1)
        left = self._pad_x
        right = width - self._pad_x
        span = self.maximum - self.minimum
        ratio = 0.0 if span == 0 else (float(value) - self.minimum) / span
        ratio = clamp(ratio, 0.0, 1.0)
        return left + ratio * (right - left)

    def _on_press(self, event):
        self.focus_set()
        self._dragging = True
        self._set_value(self._value_from_x(event.x))
        self._redraw()

    def _on_drag(self, event):
        if self._dragging:
            self._set_value(self._value_from_x(event.x))

    def _on_release(self, _event):
        self._dragging = False
        self._redraw()

    def _on_enter(self, _event):
        self._hover = True
        self._redraw()

    def _on_leave(self, _event):
        self._hover = False
        self._redraw()

    def _on_variable_changed(self, *_):
        self.after_idle(self._redraw)

    def _redraw(self, _event=None):
        if not self.winfo_exists():
            return
        self.delete("all")
        width = max(self.winfo_width(), 2 * self._pad_x + 1)
        height = max(self.winfo_height(), 24)
        y = height / 2.0
        left = self._pad_x
        right = width - self._pad_x
        try:
            value = float(self.variable.get())
        except (tk.TclError, TypeError, ValueError):
            value = self.minimum
        x = self._x_from_value(value)

        # Subtle inactive rail + luminous active rail.
        self.create_line(left, y, right, y, fill=self.track_color, width=5, capstyle="round")
        self.create_line(left, y, x, y, fill=self.fill_color, width=5, capstyle="round")

        # Thumb halo is only shown on hover/focus/drag to keep the resting UI clean.
        active = self._hover or self._dragging or self.focus_get() is self
        if active:
            self.create_oval(x - 9, y - 9, x + 9, y + 9, fill=self.focus_color, outline="")
        self.create_oval(
            x - 6.5,
            y - 6.5,
            x + 6.5,
            y + 6.5,
            fill=self.thumb_color,
            outline=self.thumb_border,
            width=2,
        )


class OBSSimulatorGUI(tk.Tk):
    def __init__(self, *, start_servers: bool = True):
        super().__init__()

        self.title(APP_TITLE)

        # Use the same OBS branding as the modular OBS runtime.
        self._app_icon_image = None
        try:
            if APP_ICON_PNG.is_file():
                self._app_icon_image = tk.PhotoImage(file=str(APP_ICON_PNG))
                self.iconphoto(True, self._app_icon_image)
        except tk.TclError:
            self._app_icon_image = None

        self.geometry("1360x900")
        self.minsize(1120, 760)

        self.shared_state = SharedState()
        self.events = queue.Queue()

        self.command_server = CommandServer(self.shared_state, self.events)
        self.bulk_server = BulkServer(self.shared_state, self.events)

        self._make_style()
        self._create_variables()
        self._build_ui()
        self._bind_variable_updates()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._sync_state()
        self._sync_controller_health()

        if start_servers:
            self.command_server.start()
            self.bulk_server.start()

        self.after(100, self._process_events)
        self.after(250, self._refresh_gui)

    def _make_style(self):
        """Modern dark instrument-console visual language for OBS tools."""
        bg = "#06131D"
        panel = "#091B27"
        card = "#0C2230"
        card_alt = "#102A3A"
        border = "#193B4E"
        border_soft = "#123142"
        input_bg = "#071923"
        text = "#EAF4F8"
        muted = "#86A5B7"
        accent = "#2E94C4"
        accent_hover = "#3EABD9"
        cyan = "#70C9F0"
        green = "#71D99A"
        amber = "#E6C66D"
        red = "#F08B95"

        self.configure(bg=bg)
        self.option_add("*Font", ("Segoe UI", 9))

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=bg, foreground=text)
        style.configure("TFrame", background=bg)
        style.configure("Content.TFrame", background=bg)
        style.configure("Header.TFrame", background=bg)
        style.configure("Surface.TFrame", background=panel)
        style.configure("Card.TFrame", background=card, borderwidth=1, relief="solid", bordercolor=border_soft)
        style.configure("Metric.TFrame", background=panel)

        style.configure(
            "Title.TLabel",
            background=bg,
            foreground="#F7FBFD",
            font=("Segoe UI", 20, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=bg,
            foreground=muted,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Heading.TLabel",
            background=bg,
            foreground="#DDECF3",
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "SectionTitle.TLabel",
            background=card,
            foreground="#DDECF3",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "SectionHint.TLabel",
            background=card,
            foreground=muted,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Muted.TLabel",
            background=bg,
            foreground=muted,
            font=("Segoe UI", 9),
        )
        style.configure(
            "CardTitle.TLabel",
            background=card,
            foreground=muted,
            font=("Segoe UI", 8, "bold"),
        )
        style.configure(
            "CardValue.TLabel",
            background=card,
            foreground="#F7FBFD",
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "MetricLabel.TLabel",
            background=panel,
            foreground=muted,
            font=("Segoe UI", 8, "bold"),
        )
        style.configure(
            "MetricValue.TLabel",
            background=panel,
            foreground="#F3F8FA",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "ValuePill.TLabel",
            background=card_alt,
            foreground="#EAF7FC",
            padding=(10, 5),
            anchor="e",
            font=("Cascadia Mono", 9, "bold"),
        )
        style.configure(
            "ADCName.TLabel",
            background=card,
            foreground=muted,
            font=("Segoe UI", 8, "bold"),
        )
        style.configure(
            "ADCValue.TLabel",
            background=card,
            foreground="#F5FAFC",
            font=("Cascadia Mono", 12, "bold"),
        )

        for name, color in (
            ("Status.TLabel", cyan),
            ("StatusConnected.TLabel", green),
            ("StatusWarning.TLabel", amber),
            ("StatusError.TLabel", red),
        ):
            style.configure(
                name,
                background=card,
                foreground=color,
                font=("Cascadia Mono", 9, "bold"),
            )

        style.configure(
            "TLabelframe",
            background=card,
            foreground="#DDECF3",
            bordercolor=border_soft,
            lightcolor=border_soft,
            darkcolor=border_soft,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "TLabelframe.Label",
            background=card,
            foreground="#DDECF3",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("Card.TLabel", background=card, foreground=text)

        style.configure(
            "TButton",
            background="#143549",
            foreground="#EAF4F8",
            bordercolor="#24536A",
            lightcolor="#143549",
            darkcolor="#143549",
            padding=(12, 7),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "TButton",
            background=[("active", "#1D4960"), ("pressed", "#0F2A39"), ("disabled", "#0A202D")],
            foreground=[("disabled", "#617D8D")],
            bordercolor=[("active", "#3E7C99")],
        )
        style.configure(
            "Primary.TButton",
            background=accent,
            foreground="#FFFFFF",
            bordercolor="#46A4CD",
            padding=(14, 8),
        )
        style.map(
            "Primary.TButton",
            background=[("active", accent_hover), ("pressed", "#257EA8")],
        )
        style.configure(
            "Danger.TButton",
            background="#4D2C37",
            foreground="#FFEFF1",
            bordercolor="#71414D",
            padding=(14, 8),
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#653743"), ("pressed", "#3B222B")],
        )

        style.configure(
            "TEntry",
            fieldbackground=input_bg,
            foreground=text,
            insertcolor=text,
            bordercolor="#21485E",
            lightcolor="#21485E",
            darkcolor="#21485E",
            padding=7,
        )
        style.map(
            "TEntry",
            fieldbackground=[("readonly", "#091E2A")],
            foreground=[("readonly", "#B9CED9")],
        )

        for control_style in ("TCheckbutton", "TRadiobutton"):
            style.configure(
                control_style,
                background=card,
                foreground=text,
                focuscolor=card,
                font=("Segoe UI", 9),
            )
            style.map(
                control_style,
                background=[("active", card)],
                foreground=[("active", "#FFFFFF")],
            )

        style.configure(
            "TNotebook",
            background=bg,
            borderwidth=0,
            tabmargins=(0, 10, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#091D2A",
            foreground="#86A7B9",
            padding=(18, 10),
            borderwidth=0,
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#12354A"), ("active", "#0D293A")],
            foreground=[("selected", "#F7FBFD"), ("active", "#DDECF3")],
        )

        style.configure("TSeparator", background=border_soft)
        style.configure(
            "Vertical.TScrollbar",
            background="#1D4256",
            troughcolor=bg,
            bordercolor=bg,
            arrowcolor="#B9CDD7",
        )

        self._theme_colors = {
            "bg": bg,
            "panel": panel,
            "card": card,
            "card_alt": card_alt,
            "border": border,
            "border_soft": border_soft,
            "input_bg": input_bg,
            "text": text,
            "muted": muted,
            "accent": accent,
            "accent_hover": accent_hover,
            "cyan": cyan,
            "green": green,
            "amber": amber,
            "red": red,
            "slider_track": "#16384A",
            "slider_fill": "#3AA4D3",
            "slider_thumb": "#E6F7FF",
            "slider_thumb_border": "#54BCE8",
            "slider_focus": "#2D718F",
        }

    def _create_variables(self):
        # Navigation / environment
        self.roll_var = tk.DoubleVar(value=0.0)
        self.pitch_var = tk.DoubleVar(value=0.0)
        self.yaw_var = tk.DoubleVar(value=0.0)

        self.depth_var = tk.DoubleVar(value=10.0)
        self.depth_rate_var = tk.DoubleVar(value=0.0)
        self.temperature_var = tk.DoubleVar(value=25.0)

        self.angular_p_var = tk.DoubleVar(value=0.0)
        self.angular_q_var = tk.DoubleVar(value=0.0)
        self.angular_r_var = tk.DoubleVar(value=0.0)

        # XCHM1 simulator-only value. USB BIN playback does not provide VMON0.
        self.vmon0_var = tk.DoubleVar(value=6.4)

        defaults = [
            (True, 10.0, 4_000_000, 0, 0.0),
            (True, 20.0, 4_000_000, 0, 90.0),
            (True, 30.0, 4_000_000, 0, 180.0),
            (True, 40.0, 4_000_000, 0, 270.0),
        ]

        self.adc_vars = []

        for enabled, freq, amp, offset, phase in defaults:
            self.adc_vars.append({
                "enabled": tk.BooleanVar(value=enabled),
                "frequency": tk.DoubleVar(value=freq),
                "amplitude": tk.IntVar(value=amp),
                "offset": tk.IntVar(value=offset),
                "phase": tk.DoubleVar(value=phase),

                "error": tk.BooleanVar(value=False),
                "filter_not_settled": tk.BooleanVar(value=False),
                "repeated": tk.BooleanVar(value=False),
                "filter_type": tk.BooleanVar(value=False),
                "filter_saturated": tk.BooleanVar(value=False),
            })

        # ADC source / binary-log playback
        self.source_mode_var = tk.StringVar(value="control")
        self.log_file_var = tk.StringVar(value="No binary log loaded")
        self.log_state_var = tk.StringVar(value="NO FILE")
        self.log_header_var = tk.StringVar(value="-")
        self.log_progress_var = tk.StringVar(value="-")
        self.log_sensor_var = tk.StringVar(value="-")
        self.log_loop_var = tk.BooleanVar(value=False)

        self.command_status_var = tk.StringVar(value="STARTING")
        self.bulk_status_var = tk.StringVar(value="STARTING")

        self.command_clients_var = tk.StringVar(value="0 / 2")
        self.bulk_clients_var = tk.StringVar(value="0 / 2")

        self.bulk_rate_var = tk.StringVar(value="0.0 blocks/s | 0.0 ADC frames/s")
        self.bulk_mbps_var = tk.StringVar(value="0.0 Mbit/s")

        self.bulk_sequence_var = tk.StringVar(value="0")
        self.bulk_frame_size_var = tk.StringVar(
            value=f"{12 + ADC_PAYLOAD_BYTES} bytes"
        )

        self.last_adc_vars = [
            tk.StringVar(value="0") for _ in range(ADC_CHANNELS)
        ]

    def _build_ui(self):
        root = ttk.Frame(self, style="Content.TFrame", padding=(22, 16, 22, 20))
        root.pack(fill="both", expand=True)

        # Header --------------------------------------------------------------
        header = ttk.Frame(root, style="Header.TFrame")
        header.pack(fill="x", pady=(0, 14))

        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.pack(side="left", fill="x", expand=True)

        ttk.Label(
            title_box,
            text="OBS TCP SIMULATOR",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            text=(
                "Command / telemetry + bulk ADC test instrument   •   "
                "CH0 N   CH1 E   CH2 Z   CH3 AUX"
            ),
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        version_box = ttk.Frame(header, style="Header.TFrame")
        version_box.pack(side="right", padx=(18, 0))
        ttk.Label(version_box, text="v10.7", style="Heading.TLabel").pack(anchor="e")
        ttk.Label(
            version_box,
            text=f"RAW ADC  {ADC_SAMPLE_RATE_HZ:.0f} Hz",
            style="Subtitle.TLabel",
        ).pack(anchor="e", pady=(3, 0))

        # Compact server cards ------------------------------------------------
        status_row = ttk.Frame(root, style="Content.TFrame")
        status_row.pack(fill="x", pady=(0, 10))
        status_row.columnconfigure(0, weight=1)
        status_row.columnconfigure(1, weight=1)
        status_row.columnconfigure(2, weight=0)

        command_card = ttk.Frame(status_row, style="Card.TFrame", padding=(16, 12))
        command_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        command_card.columnconfigure(0, weight=1)
        ttk.Label(command_card, text="COMMAND / TELEMETRY", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(command_card, text=f"TCP {COMMAND_PORT}", style="CardTitle.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        self.command_status_label = ttk.Label(
            command_card, textvariable=self.command_status_var, style="Status.TLabel"
        )
        self.command_status_label.grid(row=1, column=0, sticky="w", pady=(7, 0))
        ttk.Label(
            command_card,
            textvariable=self.command_clients_var,
            style="CardValue.TLabel",
        ).grid(row=1, column=1, sticky="e", padx=(20, 0), pady=(4, 0))

        bulk_card = ttk.Frame(status_row, style="Card.TFrame", padding=(16, 12))
        bulk_card.grid(row=0, column=1, sticky="nsew", padx=6)
        bulk_card.columnconfigure(0, weight=1)
        ttk.Label(bulk_card, text="BULK ADC DATA", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(bulk_card, text=f"TCP {BULK_PORT}", style="CardTitle.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        self.bulk_status_label = ttk.Label(
            bulk_card, textvariable=self.bulk_status_var, style="Status.TLabel"
        )
        self.bulk_status_label.grid(row=1, column=0, sticky="w", pady=(7, 0))
        ttk.Label(
            bulk_card,
            textvariable=self.bulk_clients_var,
            style="CardValue.TLabel",
        ).grid(row=1, column=1, sticky="e", padx=(20, 0), pady=(4, 0))

        action_card = ttk.Frame(status_row, style="Card.TFrame", padding=(12, 10))
        action_card.grid(row=0, column=2, sticky="ns", padx=(6, 0))
        ttk.Label(action_card, text="SERVER CONTROL", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 7)
        )
        button_row = ttk.Frame(action_card, style="Card.TFrame")
        button_row.pack(fill="x")
        ttk.Button(
            button_row,
            text="Start",
            command=self._start_servers,
            style="Primary.TButton",
            width=10,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            button_row,
            text="Stop",
            command=self._stop_servers,
            style="Danger.TButton",
            width=10,
        ).pack(side="left")

        # Stream metrics ------------------------------------------------------
        metrics = ttk.Frame(root, style="Surface.TFrame", padding=(16, 10))
        metrics.pack(fill="x", pady=(0, 10))
        for col in range(4):
            metrics.columnconfigure(col, weight=1)

        metric_items = (
            ("STREAM RATE", self.bulk_rate_var),
            ("THROUGHPUT", self.bulk_mbps_var),
            ("SEQUENCE", self.bulk_sequence_var),
            ("FRAME SIZE", self.bulk_frame_size_var),
        )
        for col, (label, variable) in enumerate(metric_items):
            cell = ttk.Frame(metrics, style="Metric.TFrame", padding=(8, 1))
            cell.grid(row=0, column=col, sticky="nsew")
            if col:
                ttk.Separator(metrics, orient="vertical").grid(
                    row=0, column=col, sticky="nsw", padx=(0, 4)
                )
            ttk.Label(cell, text=label, style="MetricLabel.TLabel").pack(anchor="w")
            ttk.Label(cell, textvariable=variable, style="MetricValue.TLabel").pack(
                anchor="w", pady=(3, 0)
            )

        # Main functional notebook -------------------------------------------
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        main_tab = ttk.Frame(notebook, style="Content.TFrame", padding=(4, 14, 4, 4))
        adc_tab = ttk.Frame(notebook, style="Content.TFrame", padding=(4, 14, 4, 4))
        binary_tab = ttk.Frame(notebook, style="Content.TFrame", padding=(4, 14, 4, 4))
        protocol_tab = ttk.Frame(notebook, style="Content.TFrame", padding=(4, 14, 4, 4))
        log_tab = ttk.Frame(notebook, style="Content.TFrame", padding=(4, 14, 4, 4))

        notebook.add(main_tab, text="Telemetry")
        notebook.add(adc_tab, text="ADC Simulation")
        notebook.add(binary_tab, text="Binary Log Playback")
        notebook.add(protocol_tab, text="Protocol")
        notebook.add(log_tab, text="Server Log")

        self._build_main_tab(main_tab)
        self._build_adc_tab(adc_tab)
        self._build_binary_log_tab(binary_tab)
        self._build_protocol_tab(protocol_tab)
        self._build_log_tab(log_tab)

        self._update_server_status_styles()

    @staticmethod
    def _status_label_style(value: str) -> str:
        text = str(value).upper()
        if "CONNECTED" in text or "LISTENING" in text:
            return "StatusConnected.TLabel"
        if "ERROR" in text or "STOPPED" in text:
            return "StatusError.TLabel"
        if "START" in text:
            return "StatusWarning.TLabel"
        return "Status.TLabel"

    def _update_server_status_styles(self):
        try:
            self.command_status_label.configure(
                style=self._status_label_style(self.command_status_var.get())
            )
            self.bulk_status_label.configure(
                style=self._status_label_style(self.bulk_status_var.get())
            )
        except (tk.TclError, AttributeError):
            pass

    @staticmethod
    def _enable_scale_keyboard(
        scale,
        variable,
        from_,
        to_,
        resolution,
    ):
        """
        Give every horizontal Scale deterministic keyboard control.

        Click the scale or reach it with Tab to focus it.
        Arrow keys move by one configured resolution step.
        PageUp/PageDown move by ten steps; Home/End jump to endpoints.
        """
        minimum = min(float(from_), float(to_))
        maximum = max(float(from_), float(to_))
        step = abs(float(resolution))
        if step <= 0.0:
            step = 1.0

        def set_value(value):
            value = clamp(float(value), minimum, maximum)

            if isinstance(variable, tk.IntVar):
                variable.set(int(round(value)))
            else:
                variable.set(float(value))

            return "break"

        def move(delta_steps):
            try:
                current = float(variable.get())
            except (tk.TclError, TypeError, ValueError):
                current = minimum
            return set_value(current + float(delta_steps) * step)

        scale.configure(takefocus=True)

        # Preserve normal mouse dragging, but ensure a click also gives
        # keyboard focus to that slider.
        scale.bind(
            "<Button-1>",
            lambda _event: scale.after_idle(scale.focus_set),
            add="+",
        )

        scale.bind("<Left>", lambda _event: move(-1))
        scale.bind("<Down>", lambda _event: move(-1))
        scale.bind("<Right>", lambda _event: move(+1))
        scale.bind("<Up>", lambda _event: move(+1))

        scale.bind("<Prior>", lambda _event: move(+10))  # PageUp
        scale.bind("<Next>", lambda _event: move(-10))   # PageDown
        scale.bind("<Home>", lambda _event: set_value(minimum))
        scale.bind("<End>", lambda _event: set_value(maximum))

    def _add_slider(
        self,
        parent,
        row,
        label,
        variable,
        from_,
        to_,
        resolution=0.1,
        unit="",
    ):
        ttk.Label(
            parent,
            text=label,
            style="Card.TLabel",
            width=14,
        ).grid(row=row, column=0, sticky="w", pady=5)

        slider = ModernSlider(
            parent,
            variable,
            from_,
            to_,
            resolution,
            bg=self._theme_colors["card"],
            track=self._theme_colors["slider_track"],
            fill=self._theme_colors["slider_fill"],
            thumb=self._theme_colors["slider_thumb"],
            thumb_border=self._theme_colors["slider_thumb_border"],
            focus=self._theme_colors["slider_focus"],
            height=30,
        )
        slider.grid(row=row, column=1, sticky="ew", padx=(8, 12), pady=2)

        value_label = ttk.Label(
            parent,
            width=16,
            style="ValuePill.TLabel",
            anchor="e",
        )
        value_label.grid(row=row, column=2, sticky="e", pady=3)

        def update_label(*_):
            try:
                value = float(variable.get())
                # Keep telemetry readable without sacrificing exact slider resolution.
                decimals = 2 if abs(float(resolution)) < 0.1 else 1
                value_label.config(text=f"{value:.{decimals}f} {unit}".strip())
            except (tk.TclError, ValueError):
                pass

        variable.trace_add("write", update_label)
        update_label()

    def _build_telemetry_group(self, parent, title, hint, controls):
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 14))
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text=title, style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(card, text=hint, style="SectionHint.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 8)
        )
        for row, item in enumerate(controls, start=2):
            self._add_slider(card, row, *item)
        return card

    def _build_main_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(
            parent,
            text="Navigation / Environment / AHRS",
            style="Heading.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        attitude_controls = [
            ("Roll", self.roll_var, -180, 180, 0.1, "deg"),
            ("Pitch", self.pitch_var, -90, 90, 0.1, "deg"),
            ("Yaw", self.yaw_var, 0, 360, 0.1, "deg"),
            ("Depth", self.depth_var, 0, 300, 0.01, "m"),
        ]
        motion_controls = [
            ("Depth rate", self.depth_rate_var, -100, 100, 0.01, "m/s"),
            ("Temperature", self.temperature_var, -10, 80, 0.1, "°C"),
            ("Angular P", self.angular_p_var, -500, 500, 0.01, "deg/s"),
            ("Angular Q", self.angular_q_var, -500, 500, 0.01, "deg/s"),
            ("Angular R", self.angular_r_var, -500, 500, 0.01, "deg/s"),
        ]

        attitude = self._build_telemetry_group(
            parent,
            "ATTITUDE & DEPTH",
            "Physical values transmitted through AHRS2 / DEPT0 telemetry.",
            attitude_controls,
        )
        attitude.grid(row=1, column=0, sticky="nsew", padx=(0, 6))

        motion = self._build_telemetry_group(
            parent,
            "ENVIRONMENT & RATES",
            "Environmental and angular-rate simulator controls.",
            motion_controls,
        )
        motion.grid(row=1, column=1, sticky="nsew", padx=(6, 0))

        # Controller health / XCHM1 ------------------------------------------
        controller = ttk.Frame(parent, style="Card.TFrame", padding=(16, 14))
        controller.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )
        controller.columnconfigure(1, weight=1)

        ttk.Label(
            controller,
            text="CONTROLLER HEALTH / XCHM1",
            style="SectionTitle.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(
            controller,
            text=(
                "VMON0 is simulator-generated and sent only in Generated / Control mode. "
                "During Binary Log Playback, XCHM1 is not transmitted because USB BIN "
                "does not contain VMON/controller-health data."
            ),
            style="SectionHint.TLabel",
            wraplength=1080,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 8))

        self._add_slider(
            controller,
            2,
            "VMON0 / Battery",
            self.vmon0_var,
            0.0,
            20.0,
            0.01,
            "V",
        )

        # Live ADC readout ----------------------------------------------------
        readout = ttk.Frame(parent, style="Content.TFrame")
        readout.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for col in range(ADC_CHANNELS):
            readout.columnconfigure(col, weight=1)

        ttk.Label(
            readout,
            text="LIVE ADC OUTPUT",
            style="Heading.TLabel",
        ).grid(row=0, column=0, columnspan=ADC_CHANNELS, sticky="w", pady=(0, 8))

        for i in range(ADC_CHANNELS):
            card = ttk.Frame(readout, style="Card.TFrame", padding=(14, 10))
            card.grid(
                row=1,
                column=i,
                sticky="ew",
                padx=(0 if i == 0 else 5, 0 if i == ADC_CHANNELS - 1 else 5),
            )
            ttk.Label(
                card,
                text=f"CH{i}  •  {ADC_ORIENTATION[i]}",
                style="ADCName.TLabel",
            ).pack(anchor="w")
            ttk.Label(
                card,
                textvariable=self.last_adc_vars[i],
                style="ADCValue.TLabel",
            ).pack(anchor="w", pady=(4, 0))

    def _build_adc_channel_card(self, parent, i, pady=(5, 5)):
        """Build one ADC control card without changing the underlying channel index."""
        frame = ttk.LabelFrame(
            parent,
            text=f"ADC Channel {i} ({ADC_ORIENTATION[i]})",
            padding=(12, 9),
        )
        frame.pack(fill="x", pady=pady)
        frame.columnconfigure(1, weight=1)

        v = self.adc_vars[i]

        ttk.Checkbutton(
            frame,
            text="Enable sine output",
            variable=v["enabled"],
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            frame,
            text="Current:",
        ).grid(row=0, column=1, sticky="e")

        ttk.Label(
            frame,
            textvariable=self.last_adc_vars[i],
            width=16,
        ).grid(row=0, column=2, sticky="w", padx=5)

        self._add_adc_control(
            frame, 1, "Frequency", v["frequency"],
            0.0, ADC_SAMPLE_RATE_HZ * 0.49, 0.1, "Hz"
        )

        self._add_adc_control(
            frame, 2, "Amplitude", v["amplitude"],
            0, ADC24_MAX, 1000, "count"
        )

        self._add_adc_control(
            frame, 3, "DC Offset", v["offset"],
            ADC24_MIN, ADC24_MAX, 1000, "count"
        )

        self._add_adc_control(
            frame, 4, "Phase", v["phase"],
            0.0, 360.0, 1.0, "deg"
        )

        flags = ttk.Frame(frame)
        flags.grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(5, 0),
        )

        ttk.Checkbutton(
            flags, text="ERROR", variable=v["error"]
        ).pack(side="left", padx=(0, 12))

        ttk.Checkbutton(
            flags, text="Not settled",
            variable=v["filter_not_settled"]
        ).pack(side="left", padx=(0, 12))

        ttk.Checkbutton(
            flags, text="Repeated",
            variable=v["repeated"]
        ).pack(side="left", padx=(0, 12))

        ttk.Checkbutton(
            flags, text="Filter type",
            variable=v["filter_type"]
        ).pack(side="left", padx=(0, 12))

        ttk.Checkbutton(
            flags, text="Saturated",
            variable=v["filter_saturated"]
        ).pack(side="left")

        return frame

    def _build_adc_tab(self, parent):
        """Build a responsive, vertically scrollable ADC Simulation tab."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        shell = ttk.Frame(parent, style="Content.TFrame")
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        canvas = tk.Canvas(
            shell,
            bg=self._theme_colors["bg"],
            highlightthickness=0,
            bd=0,
            relief="flat",
            yscrollincrement=32,
            takefocus=0,
        )
        scroll = ttk.Scrollbar(
            shell,
            orient="vertical",
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns", padx=(8, 0))

        content = ttk.Frame(
            canvas,
            style="Content.TFrame",
            padding=(2, 0, 8, 14),
        )
        content_window = canvas.create_window(
            (0, 0),
            window=content,
            anchor="nw",
        )

        def sync_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Keep the scrollbar visually out of the way when all content fits.
            try:
                needs_scroll = content.winfo_reqheight() > canvas.winfo_height() + 2
                if needs_scroll:
                    scroll.grid()
                else:
                    scroll.grid_remove()
                    canvas.yview_moveto(0.0)
            except tk.TclError:
                pass

        def fit_content_width(event):
            canvas.itemconfigure(content_window, width=max(1, event.width))
            canvas.after_idle(sync_scroll_region)

        def pointer_is_over_canvas():
            try:
                px, py = self.winfo_pointerxy()
                left = canvas.winfo_rootx()
                top = canvas.winfo_rooty()
                return (
                    left <= px < left + canvas.winfo_width()
                    and top <= py < top + canvas.winfo_height()
                )
            except tk.TclError:
                return False

        def on_mousewheel(event):
            if not pointer_is_over_canvas():
                return None
            delta = int(-event.delta / 120) if event.delta else 0
            if delta:
                canvas.yview_scroll(delta, "units")
                return "break"
            return None

        def on_linux_wheel(event):
            if not pointer_is_over_canvas():
                return None
            canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
            return "break"

        content.bind("<Configure>", sync_scroll_region)
        canvas.bind("<Configure>", fit_content_width)
        canvas.bind_all("<MouseWheel>", on_mousewheel, add="+")
        canvas.bind_all("<Button-4>", on_linux_wheel, add="+")
        canvas.bind_all("<Button-5>", on_linux_wheel, add="+")

        ttk.Label(
            content,
            text="Generated ADC waveform controls",
            style="Heading.TLabel",
        ).pack(fill="x", pady=(0, 3))
        ttk.Label(
            content,
            text=(
                f"{ADC_SAMPLE_RATE_HZ:.0f} samples/s  •  {ADC_FRAMES_PER_BLOCK} frames/block  •  "
                f"{ADC_WORDS_PER_BLOCK} words  •  {ADC_PAYLOAD_BYTES} payload bytes"
            ),
            style="Muted.TLabel",
            wraplength=1050,
        ).pack(fill="x", pady=(0, 7))

        ttk.Label(
            content,
            text="GEOPHONE CHANNELS  •  Z → N → E",
            style="SectionHint.TLabel",
        ).pack(fill="x", pady=(3, 0))

        # Display order follows physical orientation requested by the operator.
        # IMPORTANT: this does not alter adc_vars indices or TCP payload order.
        for position, i in enumerate((2, 0, 1)):
            self._build_adc_channel_card(
                content,
                i,
                pady=((5 if position == 0 else 4), 4),
            )

        ttk.Separator(content).pack(fill="x", pady=(8, 8))
        ttk.Label(
            content,
            text="AUXILIARY CHANNEL",
            style="SectionHint.TLabel",
        ).pack(fill="x", pady=(0, 0))
        self._build_adc_channel_card(content, 3, pady=(5, 4))

        ttk.Label(
            content,
            text=(
                "Display order only: TCP bulk payload remains "
                "CH0(N), CH1(E), CH2(Z), CH3(AUX)."
            ),
            style="Muted.TLabel",
        ).pack(fill="x", pady=(7, 0))

        canvas.after_idle(sync_scroll_region)

    def _build_binary_log_tab(self, parent):
        parent.columnconfigure(0, weight=1)

        source_box = ttk.LabelFrame(parent, text="ADC Data Source", padding=10)
        source_box.pack(fill="x", pady=(0, 10))

        ttk.Radiobutton(
            source_box,
            text="Generated / Control Panel",
            variable=self.source_mode_var,
            value="control",
            command=self._on_source_mode_changed,
        ).pack(side="left", padx=(0, 25))

        ttk.Radiobutton(
            source_box,
            text="OBS Binary Log (.bin)",
            variable=self.source_mode_var,
            value="log",
            command=self._on_source_mode_changed,
        ).pack(side="left")

        file_box = ttk.LabelFrame(parent, text="Binary Log File", padding=10)
        file_box.pack(fill="x", pady=(0, 10))
        file_box.columnconfigure(1, weight=1)

        ttk.Label(file_box, text="File:").grid(row=0, column=0, sticky="w")
        ttk.Entry(
            file_box,
            textvariable=self.log_file_var,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(
            file_box,
            text="Browse...",
            command=self._browse_binary_log,
            style="Primary.TButton",
        ).grid(row=0, column=2)

        ttk.Label(file_box, text="Header:").grid(
            row=1, column=0, sticky="nw", pady=(8, 0)
        )
        ttk.Label(
            file_box,
            textvariable=self.log_header_var,
            justify="left",
            font=("Consolas", 10),
        ).grid(row=1, column=1, columnspan=2, sticky="w", padx=8, pady=(8, 0))

        playback_box = ttk.LabelFrame(parent, text="Playback", padding=10)
        playback_box.pack(fill="x", pady=(0, 10))

        ttk.Label(playback_box, text="State:").grid(row=0, column=0, sticky="e")
        ttk.Label(
            playback_box,
            textvariable=self.log_state_var,
            style="Status.TLabel",
            width=30,
        ).grid(row=0, column=1, sticky="w", padx=(6, 20))

        ttk.Button(
            playback_box,
            text="Play",
            command=self._play_binary_log,
            style="Primary.TButton",
        ).grid(row=0, column=2, padx=4)
        ttk.Button(
            playback_box, text="Pause", command=self._pause_binary_log
        ).grid(row=0, column=3, padx=4)
        ttk.Button(
            playback_box, text="Stop / Rewind", command=self._stop_binary_log
        ).grid(row=0, column=4, padx=4)
        ttk.Checkbutton(
            playback_box,
            text="Loop at EOF",
            variable=self.log_loop_var,
            command=self._on_log_loop_changed,
        ).grid(row=0, column=5, padx=(20, 0))

        ttk.Label(playback_box, text="Rate:").grid(
            row=1, column=0, sticky="e", pady=(10, 0)
        )
        ttk.Label(
            playback_box,
            text="AUTO • Measured from BIN",
            style="StatusConnected.TLabel",
        ).grid(row=1, column=1, sticky="w", padx=6, pady=(10, 0))

        ttk.Label(playback_box, text="Progress:").grid(
            row=2, column=0, sticky="ne", pady=(10, 0)
        )
        ttk.Label(
            playback_box,
            textvariable=self.log_progress_var,
            justify="left",
            font=("Consolas", 10),
        ).grid(row=2, column=1, columnspan=5, sticky="w", padx=6, pady=(10, 0))

        ttk.Label(playback_box, text="Sensors:").grid(
            row=3, column=0, sticky="ne", pady=(6, 0)
        )
        ttk.Label(
            playback_box,
            textvariable=self.log_sensor_var,
            justify="left",
            font=("Consolas", 10),
        ).grid(row=3, column=1, columnspan=5, sticky="w", padx=6, pady=(6, 0))

        note = (
            "Playback reads records consecutively and broadcasts the exact raw ADC "
            "payload through TCP bulk port 54301 without channel remapping "
            "(CH0=N, CH1=E, CH2=Z, CH3=AUX). By default pacing follows "
            "frames_per_record / sample_rate from the BIN header; an effective-rate "
            "override is available for legacy timing tests. Depth, "
            "temperature, roll, pitch and yaw from each record are mirrored into "
            "the simulator telemetry state and then encoded to the current v22-compatible "
            "E1/E2 wire format. XCHM1 is intentionally NOT sent while Binary Log mode "
            "is active because VMON/controller-health fields are not stored in the BIN. "
            "Current firmware uses a 30-byte packed record header; "
            "the reader keeps 34-byte auto-detection only for compatibility."
        )
        ttk.Label(
            parent, text=note, wraplength=1050, justify="left"
        ).pack(fill="x", pady=(4, 0))

    def _browse_binary_log(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Open OBS Binary Log",
            filetypes=[
                ("OBS Binary Log", "*.bin"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            header = self.bulk_server.load_log_file(path)
        except (OSError, ValueError, struct.error) as exc:
            self._append_log(f"Binary log open ERROR: {exc}")
            from tkinter import messagebox
            messagebox.showerror("Binary Log", str(exc), parent=self)
            return

        self.log_file_var.set(header.path)
        self.log_header_var.set(
            f"v{header.version} | Header Fs {header.sample_rate_hz} Hz | "
            f"Measured Fs {header.measured_sample_rate_hz:.6f} Hz | "
            f"Dev {header.rate_deviation_percent:+.6f}% | "
            f"CH {header.channels} | frames/record {header.frames_per_record} | "
            f"record header {header.record_header_size} B | payload {header.payload_bytes} B | "
            f"records ~{header.estimated_records}"
        )
        self.source_mode_var.set("log")
        self._on_source_mode_changed()

    def _on_source_mode_changed(self):
        mode = self.source_mode_var.get()
        try:
            self.bulk_server.set_source_mode(mode)
        except ValueError as exc:
            self._append_log(f"ADC source change ERROR: {exc}")
            self.source_mode_var.set("control")
            self.bulk_server.set_source_mode("control")
            return

        if mode == "control":
            self._sync_state()
            for i in range(ADC_CHANNELS):
                self._sync_adc_state(i)

    def _play_binary_log(self):
        try:
            self.bulk_server.set_log_loop(self.log_loop_var.get())
            self.bulk_server.play_log()
            self.source_mode_var.set("log")
        except ValueError as exc:
            self._append_log(f"Binary log PLAY ERROR: {exc}")

    def _pause_binary_log(self):
        self.bulk_server.pause_log()

    def _stop_binary_log(self):
        self.bulk_server.stop_log()

    def _on_log_loop_changed(self):
        self.bulk_server.set_log_loop(self.log_loop_var.get())

    def _add_adc_control(
        self,
        parent,
        row,
        label,
        variable,
        from_,
        to_,
        resolution,
        unit,
    ):
        ttk.Label(
            parent,
            text=label,
            style="Card.TLabel",
            width=16,
        ).grid(row=row, column=0, sticky="w", pady=4)

        slider = ModernSlider(
            parent,
            variable,
            from_,
            to_,
            resolution,
            bg=self._theme_colors["card"],
            track=self._theme_colors["slider_track"],
            fill=self._theme_colors["slider_fill"],
            thumb=self._theme_colors["slider_thumb"],
            thumb_border=self._theme_colors["slider_thumb_border"],
            focus=self._theme_colors["slider_focus"],
            height=28,
        )
        slider.grid(row=row, column=1, sticky="ew", padx=(8, 10), pady=1)

        entry = ttk.Entry(
            parent,
            textvariable=variable,
            width=14,
            justify="right",
            font=("Cascadia Mono", 9),
        )
        entry.grid(row=row, column=2, padx=(0, 7), pady=2)

        ttk.Label(
            parent,
            text=unit,
            style="Card.TLabel",
            width=8,
        ).grid(row=row, column=3, sticky="w")

    def _build_protocol_tab(self, parent):
        parent.columnconfigure(1, weight=1)

        rows = [
            ("Command port", str(COMMAND_PORT)),
            ("Bulk port", str(BULK_PORT)),
            ("Max command clients", str(MAX_COMMAND_CLIENTS)),
            ("Max bulk clients", str(MAX_BULK_CLIENTS)),
            ("ADC sample rate", f"{ADC_SAMPLE_RATE_HZ:.0f} Hz"),
            ("ADC Nyquist", f"{ADC_SAMPLE_RATE_HZ / 2.0:.1f} Hz"),
            ("ADC frames/block", str(ADC_FRAMES_PER_BLOCK)),
            ("Bulk target rate", f"{ADC_SAMPLE_RATE_HZ / ADC_FRAMES_PER_BLOCK:.4f} blocks/s"),
            ("Bulk period", f"{BULK_PERIOD_S * 1000.0:.3f} ms"),
            ("ADC payload", f"{ADC_PAYLOAD_BYTES} bytes"),
            ("Bulk frame", f"{12 + ADC_PAYLOAD_BYTES} bytes"),
            ("Magic", "OBS:"),
            ("Byte order", "Little-endian"),
            ("Telemetry compatibility", "obs_setting_v22.py / shared_data_v8"),
            ("OBS/device time basis", "UTC (TIME1 + emulated BIN filename)"),
            ("USB logger emulation", "RMCMD 61/62 + STRG0; 60 s rotation (status only)"),
        ]

        ttk.Label(
            parent,
            text="Protocol Summary",
            style="Heading.TLabel",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 10),
        )

        for row, (name, value) in enumerate(rows, start=1):
            ttk.Label(
                parent,
                text=name,
                width=25,
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=3,
            )
            ttk.Label(
                parent,
                text=value,
            ).grid(
                row=row,
                column=1,
                sticky="w",
            )

        ttk.Separator(parent).grid(
            row=len(rows) + 1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=15,
        )

        ttk.Label(
            parent,
            text="Command telemetry",
            style="Heading.TLabel",
        ).grid(
            row=len(rows) + 2,
            column=0,
            columnspan=2,
            sticky="w",
        )

        telemetry_text = (
            "$GDAT2  ->  10 HEX diagnostic fields + counter\n"
            "$TIME1  ->  ms(0..999), yy, month, weekday, date, hh, mm, ss, cnt\n"
            "$DEPT0  ->  field0 E1 raw, field1 unscaled, temperature E2 raw\n"
            "$AHRS2  ->  roll/pitch/yaw E1 raw, angular P/Q/R, unit ID\n"
            "$XCHM1  ->  VMON0/controller health; suppressed during Binary Log Playback\n"
            "$STRG0  ->  USB/logger status, including FILE_OPENED/CLOSED\n"
            "$XFWVR  ->  firmware version/date/title (request)\n"
            "$XCHM0  ->  unit ID + processor status (request)\n"
            "$RMCMD  ->  1/2/5/6, camera 50..60, USB logger 61/62\n"
            "\n"
            "Checksum = XOR of ASCII bytes between '$' and '*'."
        )

        ttk.Label(
            parent,
            text=telemetry_text,
            justify="left",
            font=("Consolas", 10),
        ).grid(
            row=len(rows) + 3,
            column=0,
            columnspan=2,
            sticky="w",
            pady=5,
        )

        ttk.Label(
            parent,
            text="Bulk binary frame",
            style="Heading.TLabel",
        ).grid(
            row=len(rows) + 4,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(12, 5),
        )

        bulk_text = (
            "Header 12 bytes: OBS: | uint32 sequence | uint32 payload length\n"
            "Payload: 512 x uint32 words = CH0(N),CH1(E),CH2(Z),CH3(AUX) repeated for 128 frames.\n"
            "Word bits 23..0 = signed 24-bit ADC result.\n"
            "Word bits 31..24 = channel status byte."
        )

        ttk.Label(
            parent,
            text=bulk_text,
            justify="left",
            font=("Consolas", 10),
        ).grid(
            row=len(rows) + 5,
            column=0,
            columnspan=2,
            sticky="w",
        )

    def _build_log_tab(self, parent):
        self.log_text = tk.Text(
            parent,
            height=30,
            wrap="word",
            font=("Cascadia Mono", 9),
            bg=self._theme_colors["input_bg"],
            fg="#CFE1EA",
            insertbackground=self._theme_colors["text"],
            selectbackground="#285B73",
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
        )

        scroll = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=self.log_text.yview,
        )

        self.log_text.configure(
            yscrollcommand=scroll.set
        )

        self.log_text.pack(
            side="left",
            fill="both",
            expand=True,
        )
        scroll.pack(
            side="right",
            fill="y",
        )

    def _bind_variable_updates(self):
        for var in [
            self.roll_var,
            self.pitch_var,
            self.yaw_var,
            self.depth_var,
            self.depth_rate_var,
            self.temperature_var,
            self.angular_p_var,
            self.angular_q_var,
            self.angular_r_var,
        ]:
            var.trace_add(
                "write",
                lambda *_: self._sync_state()
            )

        self.vmon0_var.trace_add(
            "write",
            lambda *_: self._sync_controller_health()
        )

        for i, values in enumerate(self.adc_vars):
            for var in values.values():
                var.trace_add(
                    "write",
                    lambda *_args, idx=i: self._sync_adc_state(idx)
                )

    def _sync_state(self):
        try:
            if self.bulk_server.source_snapshot()["mode"] != "control":
                return
            self.shared_state.update_navigation(
                self.roll_var.get(),
                self.pitch_var.get(),
                self.yaw_var.get(),
                self.depth_var.get(),
                self.depth_rate_var.get(),
                self.temperature_var.get(),
                self.angular_p_var.get(),
                self.angular_q_var.get(),
                self.angular_r_var.get(),
            )
        except (tk.TclError, ValueError):
            pass

    def _sync_controller_health(self):
        try:
            self.shared_state.update_controller_simulation(
                self.vmon0_var.get()
            )
        except (tk.TclError, ValueError):
            pass

    def _sync_adc_state(self, index):
        try:
            if self.bulk_server.source_snapshot()["mode"] != "control":
                return
            v = self.adc_vars[index]

            self.shared_state.update_adc(
                index,
                v["enabled"].get(),
                v["frequency"].get(),
                v["amplitude"].get(),
                v["offset"].get(),
                v["phase"].get(),
                v["error"].get(),
                v["filter_not_settled"].get(),
                v["repeated"].get(),
                v["filter_type"].get(),
                v["filter_saturated"].get(),
            )
        except (tk.TclError, ValueError):
            pass

    def _append_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(
            "end",
            f"[{timestamp}] {message}\n"
        )
        self.log_text.see("end")

    def _process_events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()

                if kind == "log":
                    self._append_log(data)

                elif kind == "command_status":
                    self.command_status_var.set(data)
                    self._update_server_status_styles()

                elif kind == "bulk_status":
                    self.bulk_status_var.set(data)
                    self._update_server_status_styles()

        except queue.Empty:
            pass

        if self.winfo_exists():
            self.after(100, self._process_events)

    def _refresh_gui(self):
        # Client counts
        with self.command_server.clients_lock:
            cmd_count = len(self.command_server.clients)

        with self.bulk_server.clients_lock:
            bulk_count = len(self.bulk_server.clients)

        self.command_clients_var.set(
            f"{cmd_count} / {MAX_COMMAND_CLIENTS}"
        )

        self.bulk_clients_var.set(
            f"{bulk_count} / {MAX_BULK_CLIENTS}"
        )

        # Bulk rate / active source
        source = self.bulk_server.source_snapshot()
        with self.bulk_server.stats_lock:
            start_time = self.bulk_server.start_time
            frame_count = self.bulk_server.frame_count
            byte_count = self.bulk_server.byte_count

        elapsed = max(time.perf_counter() - start_time, 0.001)
        blocks_per_sec = frame_count / elapsed
        bits_per_sec = byte_count * 8 / elapsed
        actual_adc_rate = blocks_per_sec * ADC_FRAMES_PER_BLOCK
        target_rate = max(float(source["target_sample_rate_hz"]), 1.0)
        rate_error_percent = 100.0 * (actual_adc_rate - target_rate) / target_rate

        source_name = "LOG" if source["mode"] == "log" else "CONTROL"
        self.bulk_rate_var.set(
            f"{blocks_per_sec:.2f} blocks/s | {actual_adc_rate:.1f} ADC frames/s "
            f"({rate_error_percent:+.1f}% vs {target_rate:.0f} Hz) | {source_name}"
        )
        self.bulk_mbps_var.set(f"{bits_per_sec / 1_000_000:.3f} Mbit/s")
        self.bulk_sequence_var.set(str(self.bulk_server.sequence))

        # Current ADC values are captured from the exact last transmitted block.
        for i, value in enumerate(source["latest_adc_values"]):
            self.last_adc_vars[i].set(f"{int(value):,}")

        # Binary playback panel
        self.log_state_var.set(source["status"])
        header = source["header"]
        record = source["record"]
        if header is not None:
            self.log_header_var.set(
                f"v{header.version} | Header Fs {header.sample_rate_hz} Hz | "
                f"Measured/Play Fs {float(source['target_sample_rate_hz']):.6f} Hz | "
                f"Dev {header.rate_deviation_percent:+.6f}% | "
                f"CH {header.channels} | frames/record {header.frames_per_record} | "
                f"record header {header.record_header_size} B | payload {header.payload_bytes} B | "
                f"records ~{header.estimated_records}"
            )
        if record is not None:
            total = header.estimated_records if header is not None else 0
            self.log_progress_var.set(
                f"record {record.index}/{total or '?'} | data_cnt {record.data_cnt} | "
                f"frame_base {record.frame_base_idx} | time {record.time_text}"
                + (f" | GAP {record.gap_frames} frames" if record.gap_frames else "")
            )
            self.log_sensor_var.set(
                f"depth {record.depth_m:.1f} m | temp {record.temperature_c:.2f} C | "
                f"roll {record.roll_deg:.1f} deg | pitch {record.pitch_deg:.1f} deg | "
                f"yaw {record.yaw_deg:.1f} deg"
            )
        elif header is not None:
            self.log_progress_var.set("ready at first record")
            self.log_sensor_var.set("-")

        if self.winfo_exists():
            self.after(250, self._refresh_gui)

    def _start_servers(self):
        self.command_server.start()
        self.bulk_server.start()

    def _stop_servers(self):
        self.command_server.stop()
        self.bulk_server.stop()

    def _on_close(self):
        self.command_server.stop()
        self.bulk_server.stop()
        self.bulk_server.log_reader.close()
        self.destroy()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(APP_TITLE)
    print(f"Command TCP : {HOST}:{COMMAND_PORT}")
    print(f"Bulk TCP    : {HOST}:{BULK_PORT}")
    sample_rate, bulk_rate, bulk_period = (
        adc_rate_sanity()
    )

    print(f"ADC rate    : {sample_rate:.0f} Hz")
    print(f"Bulk rate   : {bulk_rate:.4f} blocks/s")
    print(f"Bulk period : {bulk_period * 1000.0:.3f} ms")
    print(f"Nyquist     : {sample_rate / 2.0:.1f} Hz")
    print(f"Block       : {ADC_FRAMES_PER_BLOCK} frames")
    print(f"Payload     : {ADC_PAYLOAD_BYTES} bytes")
    print(f"Frame       : {12 + ADC_PAYLOAD_BYTES} bytes")

    self_test = "--self-test-gui" in sys.argv
    app = OBSSimulatorGUI(start_servers=not self_test)
    if self_test:
        app.after(350, app._on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
