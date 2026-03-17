"""
Geo Segment Workspace Dock – Modern UI (v2)

Unified QDockWidget with:
  · Large icon-card mode toggles  (Sandbox / AI Assistant)
  · 3 × 3 icon-tile module grid
  · Dynamic workspace (QStackedWidget)
  · Sandbox pipeline: Source → Filters → Segmentation → Notes
  · AI Assistant with keyword-routing and tool registry
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QSize, QDate
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsRasterLayer
from qgis.gui import QgsMapLayerComboBox

# Import AI Assistant module for unified management
from .ai_assistant import (
    AIAssistantPanel,
    route_prompt,
    MODULE_FRIENDLY,
    TOOLS,
    EXAMPLES,
)

# ── Theme ────────────────────────────────────────────────────────────────────
_C = {
    "card_off": "#363636",
    "card_on":  "#1565C0",
    "card_hov": "#454545",
    "bdr_off":  "#505050",
    "bdr_on":   "#42A5F5",
    "ok":       "#4CAF50",
    "err":      "#F44336",
    "warn":     "#FF9800",
    "muted":    "#888888",
    "header":   "#1976D2",
}

_CARD_CSS = (
    "QToolButton {{"
    "  background: {bg};"
    "  border: 2px solid {bdr};"
    "  border-radius: 8px;"
    "  color: {fg};"
    "  font-size: {fs}px;"
    "  font-weight: bold;"
    "  padding: 4px 2px;"
    "}}"
    "QToolButton:hover  {{ background: {hov}; border-color: #42A5F5; }}"
    "QToolButton:checked {{"
    "  background: {on};"
    "  border: 2px solid #42A5F5;"
    "  color: #ffffff;"
    "}}"
)

# ── Module registry ───────────────────────────────────────────────────────────
#  (key, display_label, icon_filename, accent_hex)
_MODULES = [
    ("sandbox",      "Sandbox",         "icon.png",                  "#1976D2"),
    ("ai_assistant", "AI\nAssistant",   "bot.png",                        "#7B1FA2"),
    ("spectral",     "Spectral\nIdx.",  "segment.svg",               "#388E3C"),
    ("samgeo",       "SAMGeo",          "samgeo.png",                "#E65100"),
    ("moondream",    "Moondream\nVLM",  "moondream.svg",             "#C2185B"),
    ("semantic_seg", "Semantic\nSeg.",  "segment.svg",               "#00796B"),
    ("instance_seg", "Instance\nSeg.",  "instance_segmentation.svg", "#5D4037"),
    ("deepforest",   "DeepForest",      "deepforest.svg",            "#558B2F"),
    ("water_seg",    "Water\nSeg.",     "water.svg",                 "#0277BD"),
]

_DEPS_REQUIRED = {
    "moondream", "semantic_seg", "instance_seg",
    "samgeo", "deepforest", "water_seg",
}

_AI_KEYWORDS: tuple = (
    (("moondream", "vlm", "caption", "describe", "vision"),     "moondream"),
    (("semantic", "landcover", "land cover", "classify"),        "semantic_seg"),
    (("instance", "mask rcnn", "mask r-cnn"),                    "instance_seg"),
    (("sam", "samgeo", "segment anything", "interactive"),       "samgeo"),
    (("forest", "tree", "crown", "canopy", "deepforest"),        "deepforest"),
    (("water", "wetland", "flood", "lake", "river"),             "water_seg"),
    (("spectral", "ndvi", "ndwi", "ndbi", "index", "indices"),  "spectral"),
)

_MODULE_IMPORT = {
    "moondream":    (".moondream",             "MoondreamDockWidget"),
    "semantic_seg": (".segmentation",          "SegmentationDockWidget"),
    "instance_seg": (".instance_segmentation", "InstanceSegmentationDockWidget"),
    "samgeo":       (".samgeo",                "SamGeoDockWidget"),
    "deepforest":   (".deepforest_panel",      "DeepForestDockWidget"),
    "water_seg":    (".water_segmentation",    "WaterSegmentationDockWidget"),
    "spectral":     (".spectral_indices",      "SpectralIndicesDockWidget"),
}

_MODULE_FRIENDLY = {
    "sandbox":      "Sandbox",
    "ai_assistant": "AI Assistant",
    "spectral":     "Spectral Indices",
    "samgeo":       "SAMGeo",
    "moondream":    "Moondream VLM",
    "semantic_seg": "Semantic Segmentation",
    "instance_seg": "Instance Segmentation",
    "deepforest":   "DeepForest",
    "water_seg":    "Water Segmentation",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _icon_path(plugin_dir: str, filename) -> str | None:
    if not filename:
        return None
    p = os.path.join(plugin_dir, "icons", filename)
    return p if os.path.exists(p) else None


def _colored_px(color: str, size: int = 22) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(QColor(color))
    return px


# ── Widget: large mode-toggle card ────────────────────────────────────────────
class _ModeCard(QToolButton):
    """Large, checkable icon-card for main mode selection."""

    def __init__(self, label: str, icon_path, accent: str, parent=None):
        super().__init__(parent)
        self.setText(label)
        self.setCheckable(True)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setIconSize(QSize(36, 36))
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setIcon(QIcon(_colored_px(accent, 32)))
        self._accent = accent
        self._refresh()

    def _refresh(self):
        self.setStyleSheet(
            _CARD_CSS.format(
                bg=_C["card_off"], bdr=_C["bdr_off"], fg="#cccccc",
                hov=_C["card_hov"], on=self._accent, fs=11,
            )
        )

    def nextCheckState(self):
        # Prevent unchecking by clicking an already-checked card
        if not self.isChecked():
            self.setChecked(True)


# ── Widget: small module tile ─────────────────────────────────────────────────
class _ModuleTile(QToolButton):
    """Compact icon tile for the 3 × 3 module grid."""

    def __init__(self, key: str, label: str, icon_path, accent: str, parent=None):
        super().__init__(parent)
        self.module_key = key
        self.setText(label)
        self.setCheckable(True)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setFixedSize(90, 72)
        self.setIconSize(QSize(24, 24))
        self.setToolTip(label.replace("\n", " "))
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setIcon(QIcon(_colored_px(accent, 22)))
        self._accent = accent
        self._refresh()

    def _refresh(self):
        self.setStyleSheet(
            _CARD_CSS.format(
                bg=_C["card_off"], bdr=_C["bdr_off"], fg="#cccccc",
                hov=_C["card_hov"], on=self._accent, fs=9,
            )
        )

# ── Dialog: File selection for layer import ────────────────────────────────────
class _FileSelectionDialog(QDialog):
    """Dialog to select which raster files to import."""

    def __init__(self, file_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Bands to Import")
        self.setMinimumWidth(550)
        self.setMinimumHeight(420)
        self._file_list = file_list
        self._selected = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Header
        header = QLabel("Select Bands to Import")
        header.setFont(QFont("", 11, QFont.Bold))
        layout.addWidget(header)
        
        # Resolution filter buttons
        res_box = QGroupBox("By Resolution")
        res_layout = QHBoxLayout(res_box)
        res_layout.setSpacing(4)
        res_layout.setContentsMargins(4, 6, 4, 6)
        
        res_10_btn = QPushButton("10m")
        res_10_btn.setStyleSheet("background:#1976D2;color:white;font-weight:bold;")
        res_10_btn.clicked.connect(self._select_10m)
        res_layout.addWidget(res_10_btn)
        
        res_20_btn = QPushButton("20m")
        res_20_btn.setStyleSheet("background:#FFA500;color:white;font-weight:bold;")
        res_20_btn.clicked.connect(self._select_20m)
        res_layout.addWidget(res_20_btn)
        
        res_60_btn = QPushButton("60m")
        res_60_btn.setStyleSheet("background:#FF6B6B;color:white;font-weight:bold;")
        res_60_btn.clicked.connect(self._select_60m)
        res_layout.addWidget(res_60_btn)
        
        res_layout.addStretch()
        layout.addWidget(res_box)
        
        # File list widget with checkboxes
        list_label = QLabel("Available Files")
        list_label.setStyleSheet("font-weight:bold;color:#333;")
        layout.addWidget(list_label)
        
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.ExtendedSelection)
        self._list.setMinimumHeight(200)
        
        for idx, item in enumerate(self._file_list):
            display = "{} - {}".format(
                item["name"][:45], item["res"]
            )
            list_item = QListWidgetItem(display)
            list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
            list_item.setCheckState(Qt.Unchecked)
            list_item.setData(Qt.UserRole, idx)
            # Auto-check R10m files (RGB resolution)
            if "10m" in item["res"]:
                list_item.setCheckState(Qt.Checked)
            self._list.addItem(list_item)
        
        layout.addWidget(self._list, 1)
        
        # Quick action buttons
        action_box = QHBoxLayout()
        action_box.setSpacing(4)
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.setMaximumWidth(100)
        select_all_btn.clicked.connect(self._select_all)
        action_box.addWidget(select_all_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(100)
        clear_btn.clicked.connect(self._clear_all)
        action_box.addWidget(clear_btn)
        
        action_box.addStretch()
        layout.addLayout(action_box)
        
        # Dialog buttons
        dlg_btn = QHBoxLayout()
        dlg_btn.setSpacing(6)
        
        ok_btn = QPushButton("Import")
        ok_btn.setStyleSheet("background:#4CAF50;color:white;font-weight:bold;padding:6px 16px;")
        ok_btn.setMinimumWidth(80)
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        
        dlg_btn.addStretch()
        dlg_btn.addWidget(ok_btn)
        dlg_btn.addWidget(cancel_btn)
        
        layout.addLayout(dlg_btn)

    def _select_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Checked)

    def _select_10m(self):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if "10m" in item.text():
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _select_20m(self):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if "20m" in item.text():
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _select_60m(self):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if "60m" in item.text():
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _clear_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Unchecked)

    def get_selected(self):
        selected = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.Checked:
                idx = item.data(Qt.UserRole)
                selected.append(self._file_list[idx])
        return selected


# ── Worker: Sentinel-2 download via eodag ────────────────────────────────────
class _SentinelWorker(QThread):
    progress = pyqtSignal(str)
    done = pyqtSignal(str)    # path to downloaded product
    failed = pyqtSignal(str)  # error message

    def __init__(self, cfg: dict):
        super().__init__()
        self._cfg = cfg
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            # Set credentials BEFORE importing eodag
            os.environ["EODAG__COP_DATASPACE__AUTH__CREDENTIALS__USERNAME"] = (
                self._cfg["username"]
            )
            os.environ["EODAG__COP_DATASPACE__AUTH__CREDENTIALS__PASSWORD"] = (
                self._cfg["password"]
            )
            # Clear any cached tokens to force fresh authentication
            os.environ["EODAG_CACHE_PATH"] = str(Path(tempfile.gettempdir()) / "eodag_cache")
            
            try:
                from eodag import EODataAccessGateway, setup_logging
            except ImportError:
                self.failed.emit(
                    "eodag is not installed.\n"
                    "Install it inside the plugin venv:\n\n"
                    "  pip install eodag"
                )
                return

            # Use verbose=0 to reduce token error spam (matches notebook pattern)
            setup_logging(verbose=0)
            self.progress.emit("Connecting to Copernicus Data Space…")
            dag = EODataAccessGateway()
            dag.set_preferred_provider("cop_dataspace")

            self.progress.emit("Searching for Sentinel-2 L2A products…")
            search_result = dag.search(
                productType="S2_MSI_L2A",
                cloudCover=self._cfg["cloud_cover"],
                start=self._cfg["start"],
                end=self._cfg["end"],
                geom=self._cfg["bbox"],
            )
            # Handle both old (results, metadata) and new eodag API formats
            results = search_result[0] if isinstance(search_result, tuple) else search_result

            if not results:
                self.failed.emit(
                    "No Sentinel-2 products found.\n"
                    "Try widening the date range or raising the cloud-cover limit."
                )
                return

            # Sort by cloud cover (matches notebook pattern exactly)
            results.sort(key=lambda p: p.properties.get("cloudCover", 100))
            best = results[0]
            cloud = best.properties.get("cloudCover", "?")
            title = best.properties.get("title", "unknown")

            self.progress.emit(
                "Found {} product(s).\nSelected: {:.1f}% cloud cover\n→ {}".format(
                    len(results), cloud, title
                )
            )

            if self._cancel:
                self.failed.emit("Download cancelled by user.")
                return

            # Download with extract=False to avoid extraction issues
            self.progress.emit("Downloading…  (may take several minutes)")
            out_dir = self._cfg["output_dir"]
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            
            # Download without automatic extraction
            downloaded = best.download(outputs_prefix=str(out_dir), extract=False)
            self.progress.emit("Download complete. Processing…")
            
            # Ensure file is in the correct output directory
            downloaded_path = Path(str(downloaded))
            target_path = Path(out_dir) / downloaded_path.name
            
            # If target already exists, use it; otherwise move file there
            if target_path.exists():
                self.progress.emit("Using existing download at {}".format(target_path))
                self.done.emit(str(target_path))
            elif downloaded_path != target_path:
                import shutil
                try:
                    shutil.move(str(downloaded_path), str(target_path))
                    self.done.emit(str(target_path))
                except Exception as move_err:
                    # If move fails, use the downloaded path as-is
                    self.progress.emit("Using download at {}".format(downloaded_path))
                    self.done.emit(str(downloaded_path))
            else:
                self.done.emit(str(downloaded))

        except Exception as exc:
            error_msg = str(exc)
            # Provide more helpful error messages
            if "401" in error_msg or "Unauthorized" in error_msg:
                error_msg = (
                    "Authentication failed (401 Unauthorized).\n\n"
                    "Please verify:\n"
                    "  • Copernicus username is correct\n"
                    "  • Copernicus password is correct\n"
                    "  • Account is active at dataspace.copernicus.eu\n\n"
                    f"Error: {error_msg}"
                )
            elif "iat" in error_msg or "token" in error_msg.lower():
                error_msg = (
                    "Token validation error.\n\n"
                    "This usually happens due to:\n"
                    "  • System clock not synchronized with server\n"
                    "  • Copernicus server temporary issue\n\n"
                    "Try:\n"
                    "  1. Check your system time is correct\n"
                    "  2. Wait a few minutes and try again\n"
                    "  3. Check Copernicus status at dataspace.copernicus.eu\n\n"
                    f"Error: {error_msg}"
                )
            elif "No such file or directory" in error_msg:
                error_msg = (
                    "Download completed but extraction failed.\n\n"
                    "This can happen if:\n"
                    "  • Disk space is full or write access is blocked\n"
                    "  • Copernicus server returned incomplete data\n"
                    "  • Temporary directory permissions issue\n\n"
                    "Try:\n"
                    "  1. Check available disk space\n"
                    "  2. Check folder permissions on download location\n"
                    "  3. Try again (may be temporary server issue)\n\n"
                    f"Error: {error_msg}"
                )
            self.failed.emit(error_msg)


# ── Sandbox pane: Source Data ─────────────────────────────────────────────────
class _SourcePane(QWidget):
    """Download Sentinel-2 imagery from Copernicus Data Space via eodag."""

    layer_downloaded = pyqtSignal(str)

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._worker = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 4)
        root.setSpacing(6)

        # Provider selector
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Provider:"))
        self._provider = QComboBox()
        self._provider.addItem("Copernicus Data Space  (Sentinel-2 L2A)")
        self._provider.addItem("Google Earth Engine  (coming soon)")
        self._provider.addItem("Local Raster  (coming soon)")
        self._provider.addItem("STAC API  (coming soon)")
        self._provider.model().item(1).setEnabled(False)
        self._provider.model().item(2).setEnabled(False)
        self._provider.model().item(3).setEnabled(False)
        prow.addWidget(self._provider, 1)
        root.addLayout(prow)

        # Credentials
        cred = QGroupBox("Copernicus Credentials")
        cf = QFormLayout(cred)
        cf.setContentsMargins(6, 8, 6, 6)
        self._user = QLineEdit()
        self._user.setPlaceholderText("your@email.com")
        self._pwd = QLineEdit()
        self._pwd.setEchoMode(QLineEdit.Password)
        self._pwd.setPlaceholderText("password")
        cf.addRow("Username:", self._user)
        cf.addRow("Password:", self._pwd)
        root.addWidget(cred)

        # Date range
        dt = QGroupBox("Date Range")
        df = QFormLayout(dt)
        df.setContentsMargins(6, 8, 6, 6)
        today = QDate.currentDate()
        self._dt_s = QDateEdit(today.addDays(-30))
        self._dt_e = QDateEdit(today)
        for w in (self._dt_s, self._dt_e):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
        df.addRow("From:", self._dt_s)
        df.addRow("To:",   self._dt_e)
        root.addWidget(dt)

        # AOI
        aoi = QGroupBox("Area of Interest  (WGS 84 decimal degrees)")
        af = QFormLayout(aoi)
        af.setContentsMargins(6, 8, 6, 6)

        def _dspin(val, lo=-180, hi=180):
            w = QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setDecimals(4)
            w.setValue(val)
            return w

        self._lonmin = _dspin(87.6550)
        self._latmin = _dspin(22.7868, -90, 90)
        self._lonmax = _dspin(88.0550)
        self._latmax = _dspin(23.1868, -90, 90)
        af.addRow("Lon min:", self._lonmin)
        af.addRow("Lat min:", self._latmin)
        af.addRow("Lon max:", self._lonmax)
        af.addRow("Lat max:", self._latmax)
        ext_btn = QPushButton("Use Current QGIS Extent")
        ext_btn.clicked.connect(self._use_qgis_extent)
        af.addRow("", ext_btn)
        root.addWidget(aoi)

        # Options
        opt = QGroupBox("Download Options")
        of = QFormLayout(opt)
        of.setContentsMargins(6, 8, 6, 6)
        self._cloud = QSpinBox()
        self._cloud.setRange(0, 100)
        self._cloud.setValue(20)
        self._cloud.setSuffix(" %")
        self._out = QLineEdit(str(Path.home() / "GeoSegment_Data"))
        brw = QPushButton("Browse…")
        brw.setFixedWidth(70)
        brw.clicked.connect(self._browse)
        orow = QHBoxLayout()
        orow.addWidget(self._out)
        orow.addWidget(brw)
        ow = QWidget()
        ow.setLayout(orow)
        of.addRow("Max cloud:", self._cloud)
        of.addRow("Save to:", ow)
        root.addWidget(opt)

        # Actions
        brow = QHBoxLayout()
        self._dl_btn = QPushButton("Download Best Image")
        self._dl_btn.setStyleSheet(
            "background:{};color:white;font-weight:bold;".format(_C["ok"])
        )
        self._stop_btn = QPushButton("Cancel")
        self._stop_btn.setEnabled(False)
        self._import_btn = QPushButton("Import as Layer")
        self._import_btn.setEnabled(False)
        self._import_btn.setStyleSheet(
            "background:{};color:white;font-weight:bold;".format(_C["header"])
        )
        self._dl_btn.clicked.connect(self._start)
        self._stop_btn.clicked.connect(self._cancel)
        self._import_btn.clicked.connect(self._import_layer)
        brow.addWidget(self._dl_btn)
        brow.addWidget(self._stop_btn)
        brow.addWidget(self._import_btn)
        root.addLayout(brow)
        
        # Store downloaded path for import
        self._downloaded_path = None

        self._pbar = QProgressBar()
        self._pbar.setRange(0, 0)
        self._pbar.setVisible(False)
        root.addWidget(self._pbar)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        self._log.setPlaceholderText("Download log…")
        root.addWidget(self._log)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder", self._out.text())
        if d:
            self._out.setText(d)

    def _use_qgis_extent(self):
        try:
            ext = self.iface.mapCanvas().extent()
            crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            if crs != wgs84:
                tr = QgsCoordinateTransform(crs, wgs84, QgsProject.instance())
                ext = tr.transformBoundingBox(ext)
            self._lonmin.setValue(round(ext.xMinimum(), 4))
            self._latmin.setValue(round(ext.yMinimum(), 4))
            self._lonmax.setValue(round(ext.xMaximum(), 4))
            self._latmax.setValue(round(ext.yMaximum(), 4))
        except Exception as exc:
            self._log.append("Could not read QGIS extent: {}".format(exc))

    def _start(self):
        u = self._user.text().strip()
        p = self._pwd.text().strip()
        if not u or not p:
            QMessageBox.warning(self, "Credentials required",
                                "Enter Copernicus username and password.")
            return
        cfg = {
            "username":    u,
            "password":    p,
            "start":       self._dt_s.date().toString("yyyy-MM-dd"),
            "end":         self._dt_e.date().toString("yyyy-MM-dd"),
            "bbox":        {
                "lonmin": self._lonmin.value(),
                "latmin": self._latmin.value(),
                "lonmax": self._lonmax.value(),
                "latmax": self._latmax.value(),
            },
            "cloud_cover": self._cloud.value(),
            "output_dir":  self._out.text().strip() or str(Path.home() / "GeoSegment_Data"),
        }
        self._log.clear()
        self._pbar.setVisible(True)
        self._pbar.setRange(0, 0)  # Indeterminate progress
        self._pbar.setStyleSheet(
            "QProgressBar { border: 1px solid #555; border-radius: 2px; background: #2a2a2a; }"
            "QProgressBar::chunk { background: linear-gradient(45deg, #1976D2, #1565C0); }"
        )
        self._dl_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        
        self._worker = _SentinelWorker(cfg)
        self._worker.progress.connect(self._log.append)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self._reset()

    def _on_done(self, path: str):
        self._reset()
        self._downloaded_path = path
        self._import_btn.setEnabled(True)
        self._log.append("\n\u2714 Download complete:\n{}".format(path))
        self._log.append("\nClick 'Import as Layer' to add it to your QGIS map.")
        self.layer_downloaded.emit(path)

    def _on_failed(self, msg: str):
        self._reset()
        self._log.append("\n\u2718 Error:\n{}".format(msg))

    def _reset(self):
        self._pbar.setVisible(False)
        self._dl_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _stop_progress_animation(self):
        """Stop the progress animation."""
        self._pbar.setVisible(False)
    
    def _import_layer(self):
        if not self._downloaded_path:
            self._log.append("\n\u2718 No downloaded file to import.")
            return
        try:
            path_str = str(self._downloaded_path)
            download_path = Path(path_str)
            
            # Handle .zip files (eodag downloads as .zip)
            if download_path.suffix == '.zip':
                import zipfile
                self._log.append("Extracting ZIP archive…")
                extract_dir = download_path.parent / download_path.stem
                if not extract_dir.exists():
                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    self._log.append("✓ Extraction complete")
                else:
                    self._log.append("✓ Already extracted")
                download_path = extract_dir
            elif download_path.is_file():
                # If it's a file but not zip, try to use it directly
                self._log.append("Attempting to load file directly: {}".format(download_path.name))
            elif download_path.is_dir():
                # If it's already a directory, use it as-is
                self._log.append("Using existing directory: {}".format(download_path.name))
            
            # Look for TIF files first (for processed data)
            tif_files = sorted(list(download_path.rglob("*.tif")) + list(download_path.rglob("*.TIF")))
            
            # Look for JP2 files (Sentinel-2 raw data)
            jp2_files = sorted(list(download_path.rglob("*.jp2")) + list(download_path.rglob("*.JP2")))
            
            # Combine all available raster files
            all_files = tif_files + jp2_files
            
            if not all_files:
                self._log.append(
                    "\n\u2718 No raster files found.\n"
                    "Expected TIF or JP2 files in: {}".format(download_path)
                )
                return
            
            # Build file list with resolutions
            file_list = []
            for f in all_files:
                res = "Unknown"
                if "R10m" in str(f):
                    res = "10m (RGB)"
                elif "R20m" in str(f):
                    res = "20m"
                elif "R60m" in str(f):
                    res = "60m"
                file_list.append({"path": f, "name": f.stem, "res": res})
            
            # Show dialog to select files
            dialog = _FileSelectionDialog(file_list, self)
            if dialog.exec() == QDialog.Accepted:
                selected = dialog.get_selected()
                if selected:
                    for file_info in selected:
                        data_file = str(file_info["path"])
                        basename = file_info["name"]
                        layer = QgsRasterLayer(data_file, basename)
                        if not layer.isValid():
                            self._log.append(
                                "\n\u2718 Failed to load: {}".format(basename)
                            )
                            continue
                        QgsProject.instance().addMapLayer(layer)
                        self._log.append("\n\u2714 Loaded: {} ({})".format(basename, file_info["res"]))
            else:
                self._log.append("\n  Import cancelled.")
        except Exception as exc:
            self._log.append("\n\u2718 Import failed: {}".format(exc))


# -- Sandbox filters tab: full SpectralIndicesDockWidget embed ----------------
class _SandboxFiltersTab(QWidget):
    """Filters tab that lazily embeds the full SpectralIndicesDockWidget."""

    dock_ready = pyqtSignal(object)

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._dock = None
        self._loaded = False
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)
        self._ph = QLabel(
            "Filters (Spectral Indices)\n\n"
            "Switch to this tab to load the full Spectral Indices interface."
        )
        self._ph.setAlignment(Qt.AlignCenter)
        self._ph.setWordWrap(True)
        self._ph.setStyleSheet(
            "color:{};font-size:12px;padding:20px;".format(_C["muted"])
        )
        self._root.addWidget(self._ph)

    def ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        self._ph.setText("Loading Spectral Indices\u2026")
        try:
            import importlib
            pkg = ".".join(__name__.split(".")[:-1])
            mod = importlib.import_module(".spectral_indices", package=pkg)
            self._dock = getattr(mod, "SpectralIndicesDockWidget")(self.iface, None)
            self._dock.hide()  # prevent it from appearing as a separate QGIS dock
            inner = self._dock.widget()  # QScrollArea wrapping the full tab widget
            while self._root.count():
                item = self._root.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            if inner:
                self._root.addWidget(inner)
                self.dock_ready.emit(self._dock)
            else:
                err = QLabel("Spectral Indices inner widget unavailable.")
                err.setAlignment(Qt.AlignCenter)
                self._root.addWidget(err)
        except Exception as exc:
            self._ph.setText("Error loading Spectral Indices:\n{}".format(exc))

    def get_dock(self):
        return self._dock


# -- Sandbox segmentation tab: full SamGeoDockWidget embed --------------------
class _SandboxSegTab(QWidget):
    """Segmentation tab that lazily embeds the full SamGeoDockWidget inner widget."""

    dock_ready = pyqtSignal(object)  # emits the SamGeoDockWidget when loaded

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._dock = None
        self._loaded = False
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)
        self._ph = QLabel(
            "Segmentation (SAMGeo)\n\n"
            "Switch to this tab to load the full SAMGeo interface."
        )
        self._ph.setAlignment(Qt.AlignCenter)
        self._ph.setWordWrap(True)
        self._ph.setStyleSheet(
            "color:{};font-size:12px;padding:20px;".format(_C["muted"])
        )
        self._root.addWidget(self._ph)

    def ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        self._ph.setText("Loading SAMGeo\u2026")
        try:
            import importlib
            pkg = ".".join(__name__.split(".")[:-1])
            mod = importlib.import_module(".samgeo", package=pkg)
            self._dock = getattr(mod, "SamGeoDockWidget")(self.iface, None)
            self._dock.hide()  # prevent it from appearing as a separate QGIS dock
            inner = self._dock.widget()
            # Clear layout
            while self._root.count():
                item = self._root.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            if inner:
                self._root.addWidget(inner)
                self.dock_ready.emit(self._dock)
            else:
                err = QLabel("SAMGeo inner widget unavailable.")
                err.setAlignment(Qt.AlignCenter)
                self._root.addWidget(err)
        except Exception as exc:
            self._ph.setText("Error loading SAMGeo:\n{}".format(exc))

    def get_dock(self):
        return self._dock


# ── Sandbox pane: Notes ───────────────────────────────────────────────────────
_DEFAULT_NOTES = (
    "Sandbox Workflow Notes\n"
    "\u2500" * 40 + "\n\n"
    "FILTER \u2192 SEGMENTATION GUIDE\n\n"
    "  NDVI  (B4 vs B8)   \u2192  Vegetation / crop mapping\n"
    "  NDWI  (B3 vs B8)   \u2192  Water body extraction\n"
    "  NDBI  (B11 vs B8)  \u2192  Built-up / urban detection\n"
    "  NBR   (B8 vs B12)  \u2192  Burn scar mapping\n"
    "  SAVI  (B4 vs B8)   \u2192  Vegetation in arid areas\n"
    "  EVI   (B4 vs B8)   \u2192  Enhanced vegetation\n\n"
    "RECOMMENDED SANDBOX WORKFLOW\n"
    "  1. Source      \u2192  Download Sentinel-2 from Copernicus\n"
    "  2. Filters     \u2192  Compute NDWI to isolate water pixels\n"
    "  3. Segmentation\u2192  Run SAMGeo on the NDWI output\n\n"
    "TIPS\n"
    "  \u2022  Use the Spectral Indices module for batch processing.\n"
    "  \u2022  Switch to AI Assistant mode to run workflows by prompt.\n"
    "  \u2022  Export layers via Layer \u2192 Save As in the QGIS menu.\n"
)


class _NotesPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._text = QTextEdit()
        self._text.setPlainText(_DEFAULT_NOTES)
        self._text.setFont(QFont("Monospace", 9))
        root.addWidget(self._text)


# ── Sandbox: QTabWidget with Source / Filters / Segmentation / Notes ──────────
class _SandboxPanel(QWidget):
    """Tab-based sandbox workflow panel."""

    # emitted when a module dock is created inside the sandbox (key, dock)
    module_dock_created = pyqtSignal(str, object)

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QTabWidget()

        # ── Tab 1: Source ──────────────────────────────────────────────────
        self.source_pane = _SourcePane(self.iface)
        src_scroll = QScrollArea()
        src_scroll.setWidget(self.source_pane)
        src_scroll.setWidgetResizable(True)
        src_scroll.setFrameShape(QFrame.NoFrame)
        self._tabs.addTab(src_scroll, "Source")

        # ── Tab 2: Filters (full SpectralIndicesDockWidget) ───────────────────────
        self._filters_tab = _SandboxFiltersTab(self.iface)
        self._filters_tab.dock_ready.connect(
            lambda d: self.module_dock_created.emit("spectral", d)
        )
        self._tabs.addTab(self._filters_tab, "Filters")

        # ── Tab 3: Segmentation (full SAMGeo) ──────────────────────────────
        self._seg_tab = _SandboxSegTab(self.iface)
        self._seg_tab.dock_ready.connect(
            lambda d: self.module_dock_created.emit("samgeo", d)
        )
        self._tabs.addTab(self._seg_tab, "Segmentation")

        # ── Tab 4: Notes ───────────────────────────────────────────────────
        self.notes_pane = _NotesPane()
        self._tabs.addTab(self.notes_pane, "Notes")

        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs)

    def _on_tab_changed(self, idx: int):
        if idx == 1:  # Filters tab
            self._filters_tab.ensure_loaded()
        elif idx == 2:  # Segmentation tab
            self._seg_tab.ensure_loaded()


# ── Main dock widget ──────────────────────────────────────────────────────────
class GeoSegmentDockWidget(QDockWidget):
    """
    Unified Geo Segment workspace panel.

    Layout (top to bottom):
      ① Large mode-toggle cards  (Sandbox / AI Assistant)
      ② 3 × 3 icon-tile module grid
      ③ Dynamic QStackedWidget workspace
    """

    def __init__(self, iface, parent=None):
        super().__init__("Geo Segment", parent)
        self.iface = iface
        # Locate plugin icons dir relative to this file:  dialogs/ → geo_segment/ → icons/
        self._plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.setObjectName("GeoSegmentMainDock")
        self.setMinimumWidth(380)

        self._active_key: str = "sandbox"
        self._module_docks: dict = {}
        self._module_widgets: dict = {}

        self._mode_group: QButtonGroup | None = None
        self._tile_group: QButtonGroup | None = None
        self._mode_cards: dict = {}
        self._tile_cards: dict = {}
        self._stack: QStackedWidget | None = None
        self._sandbox_panel: _SandboxPanel | None = None
        self._ai_panel: AIAssistantPanel | None = None

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Workspace: sidebar + main content
        root.addWidget(self._build_workspace(), stretch=1)

        self.setWidget(container)

        # Default: Sandbox mode
        self._activate("sandbox")

    def _build_module_grid(self) -> QWidget:
        wrapper = QWidget()
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(6)

        self._tile_group = QButtonGroup(self)
        self._tile_group.setExclusive(False)

        for key, label, icon_file, accent in _MODULES:
            ip = _icon_path(self._plugin_dir, icon_file)
            tile = _ModuleTile(key, label, ip, accent, wrapper)
            tile.setFixedHeight(60)
            tile.setFixedWidth(80)
            tile.clicked.connect(lambda _, k=key: self._on_tile_clicked(k))
            self._tile_group.addButton(tile)
            self._tile_cards[key] = tile
            vbox.addWidget(tile)
        
        vbox.addStretch()
        return wrapper

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#444;")
        return line
    
    def _make_divider_vertical(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet("color:#444;")
        return line

    def _build_workspace(self) -> QWidget:
        wrapper = QWidget()
        hbox = QHBoxLayout(wrapper)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # Left sidebar: module tiles
        sidebar = self._build_module_grid()
        sidebar.setStyleSheet("background:#2a2a2a;")
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidget(sidebar)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.NoFrame)
        sidebar_scroll.setMaximumWidth(100)
        hbox.addWidget(sidebar_scroll)
        
        # Vertical divider
        hbox.addWidget(self._make_divider_vertical())

        # Main stack: Sandbox / AI / Modules
        self._stack = QStackedWidget()

        # Index 0: placeholder
        ph = QLabel("Select a module to open its workspace.")
        ph.setAlignment(Qt.AlignCenter)
        ph.setWordWrap(True)
        ph.setStyleSheet(
            "color:{};font-size:12px;padding:20px;".format(_C["muted"])
        )
        self._stack.addWidget(ph)

        # Index 1: Sandbox workflow
        self._sandbox_panel = _SandboxPanel(self.iface)
        self._sandbox_panel.module_dock_created.connect(
            lambda k, d: self._module_docks.__setitem__(k, d)
        )
        self._stack.addWidget(self._sandbox_panel)

        # Index 2: AI Assistant
        self._ai_panel = AIAssistantPanel()
        self._ai_panel.module_requested.connect(self._on_tile_clicked)
        self._stack.addWidget(self._ai_panel)

        hbox.addWidget(self._stack, stretch=1)
        return wrapper

    # ── Interaction ──────────────────────────────────────────────────────────

    def _on_mode_toggled(self, key: str, checked: bool):
        # Mode toggle removed; kept for compatibility
        pass

    def _on_tile_clicked(self, key: str):
        # Sync mode cards
        for k, card in self._mode_cards.items():
            card.blockSignals(True)
            card.setChecked(k == key)
            card.blockSignals(False)
        # Sync all tiles
        for k, tile in self._tile_cards.items():
            tile.setChecked(k == key)
        self._load_workspace(key)

    def _activate(self, key: str):
        """Silently activate a module (used during init)."""
        card = self._mode_cards.get(key)
        if card:
            card.blockSignals(True)
            card.setChecked(True)
            card.blockSignals(False)
        tile = self._tile_cards.get(key)
        if tile:
            tile.setChecked(True)
        self._load_workspace(key)

    # ── Workspace loading ─────────────────────────────────────────────────────

    def _load_workspace(self, key: str):
        self._active_key = key

        if key == "sandbox":
            self._stack.setCurrentIndex(1)
            return

        if key == "ai_assistant":
            self._stack.setCurrentIndex(2)
            return

        # Specific module – already loaded?
        if key in self._module_widgets:
            self._stack.setCurrentWidget(self._module_widgets[key])
            return

        # Check dependencies
        if key in _DEPS_REQUIRED and not self._ensure_dependencies():
            self._stack.setCurrentIndex(0)
            return

        # Load module widget
        try:
            widget = self._create_module_widget(key)
        except Exception as exc:
            parent = self.iface.mainWindow() if self.iface else self
            QMessageBox.critical(
                parent,
                "Geo Segment – Module Error",
                "Failed to load module '{}':\n\n{}".format(
                    _MODULE_FRIENDLY.get(key, key), exc
                ),
            )
            self._stack.setCurrentIndex(0)
            return

        if widget is not None:
            self._module_widgets[key] = widget
            self._stack.addWidget(widget)
            self._stack.setCurrentWidget(widget)
        else:
            self._stack.setCurrentIndex(0)

    def _create_module_widget(self, key: str):
        spec = _MODULE_IMPORT.get(key)
        if spec is None:
            return None
        rel_module, class_name = spec
        import importlib
        # __name__ == "geo_segment.dialogs.geo_segment_dock"
        # package  == "geo_segment.dialogs"
        package = ".".join(__name__.split(".")[:-1])
        mod = importlib.import_module(rel_module, package=package)
        cls = getattr(mod, class_name)
        dock = cls(self.iface, None)
        dock.hide()  # prevent it from appearing as a separate QGIS dock
        self._module_docks[key] = dock   # keep alive for signals/model state
        inner = dock.widget()
        return inner if inner is not None else dock

    def _ensure_dependencies(self) -> bool:
        try:
            from ..core.venv_manager import (
                ensure_venv_packages_available,
                get_venv_status,
            )
            is_ready, _ = get_venv_status()
            if is_ready:
                ensure_venv_packages_available()
                return True
        except Exception:
            pass
        return False

    # ── Public API ────────────────────────────────────────────────────────────

    def select_module(self, key: str):
        """Programmatically activate a module by key."""
        self._on_tile_clicked(key)

    def current_module_key(self) -> str:
        return self._active_key
