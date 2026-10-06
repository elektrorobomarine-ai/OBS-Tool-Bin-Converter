"""
OBS TOOLS
Modern modular launcher for the OBS Simulator and OBS BIN-to-MiniSEED Converter.

Version: 2.8

Architecture
------------
Each functional module runs as a separate GUI process:

    Source mode:
        main_tools_v2_7.py
            ├── OBS_SIM.py
            └── obs_bin_to_miniseed.py

    Frozen Windows mode:
        OBS_TOOLS.exe
            ├── OBS_TOOLS.exe --module simulator
            └── OBS_TOOLS.exe --module converter

The launcher intentionally does not import either module, keeping the Tkinter
simulator and PySide6 converter isolated in independent processes.

Version 2 UI refresh
--------------------
- Compact dark marine-instrument header with OBS branding.
- Modern module cards with READY / RUNNING / MISSING states.
- Smaller responsive footprint suitable for 1366x768 displays.
- Scrollable content for reduced display height.
- Partner attribution moved into a lightweight footer strip.
- Existing separate-process launch behavior is retained.

Version 2.1 lifecycle update
----------------------------
- Closing the main OBS Tools launcher now closes every child module started by it.
- Child processes are first terminated, then force-killed only if they do not exit
  within a short timeout.

Version 2.2 hardening / self-test support
-----------------------------------------
- Uses explicit PySide6 StandardPixmap enum members.
- Windows AppUserModelID setup is isolated behind dynamic ctypes lookup.
- Launcher lifecycle exception handling is narrowed.
- Adds --self-test-gui for automated GUI construction/event-loop smoke tests.

Version 2.3 module synchronization
----------------------------------
- Launcher now targets obs_bin_to_miniseed.py for current-firmware conversion.

Version 2.4 current-firmware synchronization
--------------------------------------------
- Launcher now targets OBS_SIM.py.
- Architecture documentation is synchronized with simulator v10.7 and converter v5.11.

Version 2.5 Windows executable support
--------------------------------------
- Supports one PyInstaller executable with child-process dispatch.
- Source mode still launches OBS_SIM.py and obs_bin_to_miniseed.py.
- Frozen mode launches the same OBS_TOOLS.exe with --module simulator
  or --module converter, preserving process isolation without requiring Python
  on the deployment PC.

Version 2.6 land-test synchronization
-------------------------------------
- OBS remains the application/product name.
- Launcher targets OBS Simulator v10.7 and BIN-to-MiniSEED Converter v5.11.
- MiniSEED export is limited to seismic CH0/CH1/CH2; CH3/AUX is source-only.

Version 2.8 build synchronization
---------------------------------
- Frozen Windows bundle uses generic module filenames OBS_SIM.py and
  obs_bin_to_miniseed.py while displaying their actual internal versions.
- Launcher cards synchronized to OBS Simulator v10.7 and Converter v5.11.
- Existing separate-process frozen dispatch remains unchanged.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

APP_USER_MODEL_ID = "GRC.UGM.PERTAMINA.OBS.TOOLS"


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
        # Branding is optional; launcher functionality must not depend on it.
        return


configure_windows_app_id(APP_USER_MODEL_ID)

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

APP_TITLE = "OBS Engineering Tools"
APP_VERSION = "2.8"

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_DIR = ASSETS_DIR / "logos"
ICON_DIR = ASSETS_DIR / "icons"

APP_HEADER_LOGO = LOGO_DIR / "Prameya_rev.png"
APP_ICON_PNG = ICON_DIR / "Prameya_rev.png"


def application_icon() -> QIcon:
    if APP_ICON_PNG.is_file():
        icon = QIcon(str(APP_ICON_PNG))
        if not icon.isNull():
            return icon
    return QIcon()


@dataclass(frozen=True)
class ModuleSpec:
    title: str
    version: str
    module_id: str
    script: str
    description: str
    detail: str
    fallback_icon: QStyle.StandardPixmap


MODULES = (
    ModuleSpec(
        title="OBS Simulator",
        version="v10.7",
        module_id="simulator",
        script="OBS_SIM.py",
        description="Command, telemetry and bulk ADC test instrument",
        detail="TCP 54300 / 54301  •  Generated ADC  •  BIN playback",
        fallback_icon=QStyle.StandardPixmap.SP_ComputerIcon,
    ),
    ModuleSpec(
        title="BIN → MiniSEED Converter",
        version="v5.11",
        module_id="converter",
        script="obs_bin_to_miniseed.py",
        description="Offline recovery and conversion of OBS binary logs",
        detail="NEZ (CH0-CH2)  •  CH3/AUX excluded  •  INT32 + STEIM2  •  ObsPy verify",
        fallback_icon=QStyle.StandardPixmap.SP_DialogSaveButton,
    ),
)


class LogoLabel(QLabel):
    """Compact logo label preserving source aspect ratio."""

    def __init__(self, image_path: Path, max_width: int, max_height: int):
        super().__init__()
        self.setObjectName("brandLogo")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(max_width, max_height)

        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            self.setPixmap(
                pixmap.scaled(
                    max_width - 18,
                    max_height - 12,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.setText("OBS")


class ModuleCard(QFrame):
    def __init__(self, spec: ModuleSpec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("moduleCard")
        self.setMinimumHeight(150)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(18)

        icon_box = QFrame()
        icon_box.setObjectName("moduleIconBox")
        icon_box.setFixedSize(74, 74)
        ib = QVBoxLayout(icon_box)
        ib.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setObjectName("moduleIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = self.style().standardIcon(spec.fallback_icon)
        icon_label.setPixmap(icon.pixmap(QSize(38, 38)))
        ib.addWidget(icon_label)
        root.addWidget(icon_box, 0, Qt.AlignmentFlag.AlignVCenter)

        content = QVBoxLayout()
        content.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title = QLabel(spec.title)
        title.setObjectName("moduleTitle")
        title_row.addWidget(title)

        version = QLabel(spec.version)
        version.setObjectName("versionBadge")
        version.setFixedHeight(24)
        title_row.addWidget(version)
        title_row.addStretch(1)

        self.status_label = QLabel("CHECKING")
        self.status_label.setObjectName("statusBadge")
        self.status_label.setProperty("state", "checking")
        self.status_label.setFixedHeight(24)
        title_row.addWidget(self.status_label)

        content.addLayout(title_row)

        desc = QLabel(spec.description)
        desc.setObjectName("moduleDescription")
        content.addWidget(desc)

        detail = QLabel(spec.detail)
        detail.setObjectName("moduleDetail")
        detail.setWordWrap(True)
        content.addWidget(detail)
        content.addStretch(1)

        root.addLayout(content, 1)

        action_col = QVBoxLayout()
        action_col.setContentsMargins(4, 0, 0, 0)
        action_col.addStretch(1)

        self.open_button = QPushButton("OPEN")
        self.open_button.setObjectName("openButton")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.setMinimumWidth(112)
        self.open_button.setFixedHeight(40)
        action_col.addWidget(self.open_button)

        action_col.addStretch(1)
        root.addLayout(action_col)

    def set_state(self, state: str):
        state = state.lower()
        labels = {
            "ready": "● READY",
            "running": "● RUNNING",
            "missing": "● MISSING",
            "checking": "CHECKING",
        }
        self.status_label.setText(labels.get(state, state.upper()))
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        if state == "missing":
            self.open_button.setEnabled(False)
            self.open_button.setText("MISSING")
        elif state == "running":
            self.open_button.setEnabled(True)
            self.open_button.setText("RUNNING")
        else:
            self.open_button.setEnabled(True)
            self.open_button.setText("OPEN")


def is_frozen() -> bool:
    """True when running from a PyInstaller-built executable."""
    return bool(getattr(sys, "frozen", False))


def dispatched_module() -> str | None:
    """Return --module value when this executable is acting as a child module."""
    try:
        index = sys.argv.index("--module")
    except ValueError:
        return None

    if index + 1 >= len(sys.argv):
        return ""
    return str(sys.argv[index + 1]).strip().lower()


def run_dispatched_module(module_id: str) -> int:
    """Run one bundled module in this child process."""
    if module_id == "simulator":
        import OBS_SIM

        result = OBS_SIM.main()
        return int(result) if isinstance(result, int) else 0

    if module_id == "converter":
        import obs_bin_to_miniseed

        return int(obs_bin_to_miniseed.main())

    raise ValueError(f"Unknown bundled module: {module_id!r}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._processes: dict[str, subprocess.Popen] = {}
        self._cards: dict[str, ModuleCard] = {}

        icon = application_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.setMinimumSize(900, 620)
        self.resize(1160, 760)

        self._build_ui()
        self._apply_style()
        self._refresh_module_states()

        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self._cleanup_processes)
        self.process_timer.start(1000)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("mainScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        page = QWidget()
        page.setObjectName("page")
        scroll.setWidget(page)

        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        # Header --------------------------------------------------------------
        header = QFrame()
        header.setObjectName("headerCard")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 14, 20, 14)
        hl.setSpacing(18)

        brand = LogoLabel(APP_HEADER_LOGO, 210, 72)
        hl.addWidget(brand, 0, Qt.AlignmentFlag.AlignVCenter)

        sep = QFrame()
        sep.setObjectName("verticalSeparator")
        sep.setFixedWidth(1)
        sep.setMinimumHeight(54)
        hl.addWidget(sep)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        eyebrow = QLabel("OCEAN BOTTOM SEISMOMETER")
        eyebrow.setObjectName("eyebrow")
        title_box.addWidget(eyebrow)

        title = QLabel("OBS Engineering Tools")
        title.setObjectName("appTitle")
        title_box.addWidget(title)

        subtitle = QLabel(
            "Simulation, protocol validation and offline acquisition-data conversion"
        )
        subtitle.setObjectName("appSubtitle")
        title_box.addWidget(subtitle)

        hl.addLayout(title_box, 1)

        state_box = QVBoxLayout()
        state_box.setSpacing(4)
        state_box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        version = QLabel(f"TOOLS  v{APP_VERSION}")
        version.setObjectName("headerVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignRight)
        state_box.addWidget(version)

        self.system_state = QLabel("● SYSTEM READY")
        self.system_state.setObjectName("systemReady")
        self.system_state.setAlignment(Qt.AlignmentFlag.AlignRight)
        state_box.addWidget(self.system_state)

        hl.addLayout(state_box)
        root.addWidget(header)

        # Section header ------------------------------------------------------
        section_row = QHBoxLayout()
        section_row.setContentsMargins(4, 4, 4, 0)

        section_text = QVBoxLayout()
        section_text.setSpacing(2)
        section_title = QLabel("SYSTEM MODULES")
        section_title.setObjectName("sectionTitle")
        section_text.addWidget(section_title)

        section_hint = QLabel(
            "Modules run in separate processes, but closing this launcher closes all modules started from it."
        )
        section_hint.setObjectName("sectionHint")
        section_text.addWidget(section_hint)

        section_row.addLayout(section_text)
        section_row.addStretch(1)

        architecture = QLabel("SEPARATE-PROCESS ARCHITECTURE")
        architecture.setObjectName("architectureBadge")
        section_row.addWidget(architecture, 0, Qt.AlignmentFlag.AlignBottom)

        root.addLayout(section_row)

        # Module cards --------------------------------------------------------
        module_grid = QGridLayout()
        module_grid.setContentsMargins(0, 0, 0, 0)
        module_grid.setHorizontalSpacing(14)
        module_grid.setVerticalSpacing(14)

        for index, spec in enumerate(MODULES):
            card = ModuleCard(spec)
            card.open_button.clicked.connect(
                lambda checked=False, module=spec: self.launch_module(module)
            )
            self._cards[spec.script] = card
            module_grid.addWidget(card, index, 0)

        root.addLayout(module_grid)

        # Information strip --------------------------------------------------
        info = QFrame()
        info.setObjectName("infoStrip")
        il = QHBoxLayout(info)
        il.setContentsMargins(16, 10, 16, 10)
        il.setSpacing(12)

        items = (
            ("CHANNEL MAP", "CH0 N  •  CH1 E  •  CH2 Z  •  CH3 AUX"),
            ("RAW ADC", "1000 Hz / channel"),
            ("MINISEED", "INT32  •  STEIM2  •  UTC archive"),
        )
        for idx, (label, value) in enumerate(items):
            cell = QVBoxLayout()
            cell.setSpacing(2)
            l = QLabel(label)
            l.setObjectName("infoLabel")
            v = QLabel(value)
            v.setObjectName("infoValue")
            cell.addWidget(l)
            cell.addWidget(v)
            il.addLayout(cell, 1)
            if idx < len(items) - 1:
                divider = QFrame()
                divider.setObjectName("infoDivider")
                divider.setFixedWidth(1)
                divider.setMinimumHeight(34)
                il.addWidget(divider)

        root.addWidget(info)
        root.addStretch(1)

        # Lightweight partner/footer strip -----------------------------------
        footer = QFrame()
        footer.setObjectName("footerStrip")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(14, 9, 14, 9)

        self.status_label = QLabel("System ready")
        self.status_label.setObjectName("footerStatus")
        fl.addWidget(self.status_label)

        fl.addStretch(1)

        partner = QLabel()
        partner.setObjectName("partnerText")
        fl.addWidget(partner)

        root.addWidget(footer)

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget#page {
                background-color: #06131D;
                color: #EAF4F8;
                font-family: "Segoe UI", "Arial";
            }

            QScrollArea#mainScroll {
                background: #06131D;
                border: none;
            }

            QFrame#headerCard {
                background-color: #091B27;
                border: 1px solid #123142;
                border-radius: 12px;
            }

            QLabel#brandLogo {
                background-color: #FFFFFF;
                border: 1px solid #D8E2E8;
                border-radius: 9px;
            }

            QFrame#verticalSeparator,
            QFrame#infoDivider {
                background-color: #17384A;
                border: none;
            }

            QLabel#eyebrow {
                color: #70C9F0;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 1.8px;
            }

            QLabel#appTitle {
                color: #F7FBFD;
                font-size: 24px;
                font-weight: 750;
            }

            QLabel#appSubtitle {
                color: #86A5B7;
                font-size: 11px;
            }

            QLabel#headerVersion {
                color: #86A5B7;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 10px;
                font-weight: 700;
            }

            QLabel#systemReady {
                color: #71D99A;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 10px;
                font-weight: 800;
            }

            QLabel#sectionTitle {
                color: #DDECF3;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1.2px;
            }

            QLabel#sectionHint {
                color: #7596A9;
                font-size: 10px;
            }

            QLabel#architectureBadge {
                color: #6C9DB6;
                background: #0A202D;
                border: 1px solid #14384B;
                border-radius: 10px;
                padding: 5px 10px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 9px;
                font-weight: 700;
            }

            QFrame#moduleCard {
                background-color: #0C2230;
                border: 1px solid #16384A;
                border-radius: 12px;
            }

            QFrame#moduleCard:hover {
                border: 1px solid #2B6683;
                background-color: #0E2736;
            }

            QFrame#moduleIconBox {
                background: #102D3E;
                border: 1px solid #1B455C;
                border-radius: 12px;
            }

            QLabel#moduleIcon {
                background: transparent;
            }

            QLabel#moduleTitle {
                color: #F3F8FA;
                font-size: 16px;
                font-weight: 750;
            }

            QLabel#moduleDescription {
                color: #B8CDD8;
                font-size: 11px;
                font-weight: 600;
            }

            QLabel#moduleDetail {
                color: #789BAC;
                font-size: 10px;
            }

            QLabel#versionBadge {
                color: #BFEAFF;
                background: #12354A;
                border: 1px solid #225C78;
                border-radius: 11px;
                padding: 2px 8px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 9px;
                font-weight: 800;
            }

            QLabel#statusBadge {
                border-radius: 11px;
                padding: 2px 9px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 9px;
                font-weight: 800;
            }

            QLabel#statusBadge[state="ready"] {
                color: #8CE3AA;
                background: #0C3225;
                border: 1px solid #1C5A3D;
            }

            QLabel#statusBadge[state="running"] {
                color: #84D9FA;
                background: #0B3044;
                border: 1px solid #245D77;
            }

            QLabel#statusBadge[state="missing"] {
                color: #F3A2AA;
                background: #3A1E27;
                border: 1px solid #6E3443;
            }

            QLabel#statusBadge[state="checking"] {
                color: #E6C66D;
                background: #352E19;
                border: 1px solid #62542B;
            }

            QPushButton#openButton {
                background: #2E94C4;
                color: #FFFFFF;
                border: 1px solid #46A4CD;
                border-radius: 8px;
                padding: 8px 15px;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 0.7px;
            }

            QPushButton#openButton:hover {
                background: #3EABD9;
                border-color: #68BCE0;
            }

            QPushButton#openButton:pressed {
                background: #257EA8;
            }

            QPushButton#openButton:disabled {
                color: #637D8C;
                background: #0A202D;
                border-color: #163345;
            }

            QFrame#infoStrip {
                background: #091B27;
                border: 1px solid #123142;
                border-radius: 10px;
            }

            QLabel#infoLabel {
                color: #6F91A4;
                font-size: 8px;
                font-weight: 800;
                letter-spacing: 1px;
            }

            QLabel#infoValue {
                color: #D9E9F0;
                font-size: 10px;
                font-weight: 650;
            }

            QFrame#footerStrip {
                background: #081A25;
                border: 1px solid #102D3D;
                border-radius: 9px;
            }

            QLabel#footerStatus {
                color: #7C9BAD;
                font-size: 9px;
            }

            QLabel#partnerText {
                color: #5E7F91;
                font-size: 9px;
                font-weight: 650;
            }

            QScrollBar:vertical {
                background: #06131D;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #1D4256;
                min-height: 28px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #2A5C74;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
                height: 0px;
            }
            """
        )

    @staticmethod
    def _gui_python_executable() -> str:
        executable = Path(sys.executable)

        if os.name == "nt" and executable.name.lower() == "python.exe":
            pythonw = executable.with_name("pythonw.exe")
            if pythonw.exists():
                return str(pythonw)

        return str(executable)

    def _module_process_running(self, script: str) -> bool:
        process = self._processes.get(script)
        return process is not None and process.poll() is None

    def _refresh_module_states(self):
        missing = 0
        running = 0

        for spec in MODULES:
            card = self._cards.get(spec.script)
            if card is None:
                continue

            available = is_frozen() or (BASE_DIR / spec.script).is_file()
            is_running = self._module_process_running(spec.script)

            if not available:
                card.set_state("missing")
                missing += 1
            elif is_running:
                card.set_state("running")
                running += 1
            else:
                card.set_state("ready")

        if missing:
            self.system_state.setText(f"● {missing} MODULE MISSING")
            self.system_state.setStyleSheet("color: #F08B95;")
        elif running:
            self.system_state.setText(f"● {running} MODULE RUNNING")
            self.system_state.setStyleSheet("color: #70C9F0;")
        else:
            self.system_state.setText("● SYSTEM READY")
            self.system_state.setStyleSheet("")

    def launch_module(self, spec: ModuleSpec):
        self._cleanup_processes()

        current = self._processes.get(spec.script)
        if current is not None and current.poll() is None:
            QMessageBox.information(
                self,
                APP_TITLE,
                f"{spec.title} is already running.",
            )
            self.status_label.setText(f"{spec.title}: already running")
            self._refresh_module_states()
            return

        if is_frozen():
            command = [sys.executable, "--module", spec.module_id]
            working_directory = str(Path(sys.executable).resolve().parent)
        else:
            script_path = BASE_DIR / spec.script
            if not script_path.is_file():
                QMessageBox.warning(
                    self,
                    APP_TITLE,
                    f"Module file tidak ditemukan:\n\n{script_path.name}",
                )
                self.status_label.setText(f"{spec.title}: file not found")
                self._refresh_module_states()
                return

            command = [self._gui_python_executable(), str(script_path)]
            working_directory = str(BASE_DIR)

        kwargs = {
            "cwd": working_directory,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            process = subprocess.Popen(command, **kwargs)
        except OSError as exc:
            QMessageBox.critical(
                self,
                APP_TITLE,
                f"Gagal membuka {spec.title}:\n\n{exc}",
            )
            self.status_label.setText(f"Failed to launch {spec.title}")
            return

        self._processes[spec.script] = process
        self.status_label.setText(f"{spec.title} launched")
        self._refresh_module_states()

    def _cleanup_processes(self):
        finished = [
            name
            for name, process in self._processes.items()
            if process.poll() is not None
        ]

        for name in finished:
            self._processes.pop(name, None)

        self._refresh_module_states()

    def _shutdown_child_processes(self):
        """Close every module process launched from this main window."""
        processes = [
            process
            for process in self._processes.values()
            if process.poll() is None
        ]

        # Request termination first.
        for process in processes:
            try:
                process.terminate()
            except OSError:
                continue

        # Give each child a short opportunity to exit, then force-kill if needed.
        for process in processes:
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except OSError:
                    continue
            except OSError:
                continue

        # Reap remaining process handles.
        for process in processes:
            try:
                process.wait(timeout=0.5)
            except (subprocess.TimeoutExpired, OSError):
                continue

        self._processes.clear()

    def closeEvent(self, event):
        self.process_timer.stop()
        self.status_label.setText("Closing OBS Tools modules...")
        self._shutdown_child_processes()
        event.accept()


def main() -> int:
    module_id = dispatched_module()
    if module_id is not None:
        if not module_id:
            raise SystemExit("--module requires simulator or converter")
        return run_dispatched_module(module_id)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)

    icon = application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    if "--self-test-gui" in sys.argv:
        QTimer.singleShot(350, window.close)
        QTimer.singleShot(1500, app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
