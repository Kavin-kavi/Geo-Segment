"""
Spectral Indices Dock Widget for Geo Segment Plugin

Computes a wide range of spectral indices (water, vegetation, snow/fire,
land-change) and band-combination composites from Sentinel-2 raster layers
loaded in QGIS.  All computation is pure-NumPy so no extra dependencies
beyond what QGIS ships with are needed.
"""

import os
import tempfile
import traceback

import numpy as np

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
    Qgis,
)


# ---------------------------------------------------------------------------
# Pure-NumPy spectral index functions
# ---------------------------------------------------------------------------

import numpy as np

# -------------------------------------------------     
# Utility
# -------------------------------------------------

def safe_divide(a, b):
    """Avoid division by zero."""
    return np.divide(a, b, out=np.zeros_like(a, dtype=float), where=b != 0)


# -------------------------------------------------
# Vegetation Indices
# -------------------------------------------------

def ndvi(B8A, B04):
    """Normalized Difference Vegetation Index"""
    return safe_divide((B8A - B04), (B8A + B04))


def savi(B8A, B04, L=0.5):
    """Soil Adjusted Vegetation Index"""
    return 1.5 * safe_divide((B8A - B04), (B8A + B04 + L))


def evi(B8A, B04, B02):
    """Enhanced Vegetation Index"""
    return 2.5 * safe_divide(
        (B8A - B04),
        (B8A + 6 * B04 - 7.5 * B02 + 1)
    )


def gci(B08, B03):
    """Green Chlorophyll Index"""
    return safe_divide(B08, B03) - 1


def sipi(B08, B02, B04):
    """Structure Insensitive Pigment Index"""
    return safe_divide((B08 - B02), (B08 - B04))


# -------------------------------------------------
# Water Index
# -------------------------------------------------

def ndwi(B03, B08):
    """Normalized Difference Water Index"""
    return safe_divide((B03 - B08), (B03 + B08))


# -------------------------------------------------
# Snow Detection
# -------------------------------------------------

def ndsi(B03, B11):
    """Normalized Difference Snow Index"""
    return safe_divide((B03 - B11), (B03 + B11))


# -------------------------------------------------
# Urban Detection
# -------------------------------------------------

def ndbi(B11, B08):
    """Normalized Difference Built-up Index"""
    return safe_divide((B11 - B08), (B11 + B08))


# -------------------------------------------------
# Fire / Burn Detection
# -------------------------------------------------

def nbr(B8A, B12):
    """Normalized Burn Ratio"""
    return safe_divide((B8A - B12), (B8A + B12))


def dnbr(nbr_pre, nbr_post):
    """Differenced Normalized Burn Ratio (change detection)"""
    return nbr_pre - nbr_post


# Band composites (RGB stacks) – returned as (3, H, W) float32
def composite_forestry_coverage(B04, B03, B02):
    return np.stack([B04, B03, B02]).astype(np.float32)


def composite_color_infrared(B08, B04, B03):
    return np.stack([B08, B04, B03]).astype(np.float32)


def composite_healthy_vegetation(B8A, B11, B02):
    return np.stack([B8A, B11, B02]).astype(np.float32)


def composite_land_water(B8A, B11, B04):
    return np.stack([B8A, B11, B04]).astype(np.float32)


def composite_agriculture(B11, B8A, B02):
    return np.stack([B11, B8A, B02]).astype(np.float32)


def composite_false_color_urban(B12, B11, B04):
    return np.stack([B12, B11, B04]).astype(np.float32)


def composite_snow_clouds(B02, B11, B12):
    return np.stack([B02, B11, B12]).astype(np.float32)


def composite_atmospheric_removal(B12, B8A, B03):
    return np.stack([B12, B8A, B03]).astype(np.float32)


def composite_atmospheric_penetration(B12, B11, B8A):
    return np.stack([B12, B11, B8A]).astype(np.float32)


# ---------------------------------------------------------------------------
# Index / composite registry
# ---------------------------------------------------------------------------

#  Each entry: (label, bands_needed, compute_fn)
#  bands_needed: list of Sentinel-2 band names used as widget labels
SINGLE_BAND_INDICES = [
    # Water
    ("NDWI – Normalized Difference Water Index",       ["B03", "B08"],             ndwi),
    # Vegetation
    ("NDVI – Normalized Difference Vegetation Index",  ["B8A", "B04"],             ndvi),
    ("SAVI – Soil Adjusted Vegetation Index",          ["B8A", "B04"],             savi),
    ("EVI – Enhanced Vegetation Index",                ["B8A", "B04", "B02"],      evi),
    ("GCI – Green Chlorophyll Index",                  ["B08", "B03"],             gci),
    ("SIPI – Structure Insensitive Pigment Index",     ["B08", "B02", "B04"],      sipi),
    # Snow
    ("NDSI – Normalized Difference Snow Index",        ["B03", "B11"],             ndsi),
    # Urban
    ("NDBI – Normalized Difference Built-up Index",    ["B11", "B08"],             ndbi),
    # Fire / Burn
    ("NBR – Normalized Burn Ratio",                    ["B8A", "B12"],             nbr),
    ("DNBR – Differenced Burn Ratio",                  ["DNBR_PRE", "DNBR_POST"],  dnbr),
]

COMPOSITES = [
    ("Forestry Coverage (R=B04, G=B03, B=B02)",       ["B04", "B03", "B02"],      composite_forestry_coverage),
    ("Color Infrared (R=B08, G=B04, B=B03)",           ["B08", "B04", "B03"],      composite_color_infrared),
    ("Healthy Vegetation (R=B8A, G=B11, B=B02)",       ["B8A", "B11", "B02"],      composite_healthy_vegetation),
    ("Land / Water (R=B8A, G=B11, B=B04)",             ["B8A", "B11", "B04"],      composite_land_water),
    ("Agriculture (R=B11, G=B8A, B=B02)",              ["B11", "B8A", "B02"],      composite_agriculture),
    ("False Color Urban (R=B12, G=B11, B=B04)",        ["B12", "B11", "B04"],      composite_false_color_urban),
    ("Snow & Clouds (R=B02, G=B11, B=B12)",            ["B02", "B11", "B12"],      composite_snow_clouds),
    ("Atmospheric Removal (R=B12, G=B8A, B=B03)",      ["B12", "B8A", "B03"],      composite_atmospheric_removal),
    ("Atmospheric Penetration (R=B12, G=B11, B=B8A)",  ["B12", "B11", "B8A"],      composite_atmospheric_penetration),
]


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class SpectralWorker(QThread):
    """Run spectral index or composite computation in a background thread."""

    finished = pyqtSignal(str)   # output raster path
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self.params = params

    # QGIS DataType int code  →  numpy dtype
    _QGIS_TO_NUMPY = {
        1: np.uint8,    # Byte
        2: np.uint16,   # UInt16  (Sentinel-2 native, most common)
        3: np.int16,    # Int16
        4: np.uint32,   # UInt32
        5: np.int32,    # Int32
        6: np.float32,  # Float32
        7: np.float64,  # Float64
    }

    # ------------------------------------------------------------------
    def _read_band(self, layer, band_no: int) -> np.ndarray:
        """Read a single band from a QgsRasterLayer as float32 array.

        The raw block bytes are decoded using the layer's *native* data type
        (e.g. UInt16 for Sentinel-2) before being cast to float32.  Fixing
        this avoids the reshape error that occurs when the caller assumes
        float32 (4 bytes/pixel) but the data is actually UInt16 (2 bytes/pixel).
        """
        provider = layer.dataProvider()
        extent   = layer.extent()
        width    = layer.width()
        height   = layer.height()

        block = provider.block(band_no, extent, width, height)
        if not block.isValid():
            raise RuntimeError(
                f"Could not read band {band_no} from layer '{layer.name()}'."
            )

        dt_int   = int(provider.dataType(band_no))
        np_dtype = self._QGIS_TO_NUMPY.get(dt_int, np.float32)

        raw  = bytes(block.data())
        data = np.frombuffer(raw, dtype=np_dtype).reshape(height, width)
        return data.astype(np.float32)

    # ------------------------------------------------------------------
    def _save_single_band(self, arr: np.ndarray, crs_wkt: str,
                           geotransform, output_path: str):
        """Save a 2-D float32 array to a GeoTIFF via gdal (bundled in QGIS)."""
        try:
            from osgeo import gdal, osr
        except ImportError:
            raise RuntimeError(
                "GDAL Python bindings are not available. "
                "Please use QGIS with GDAL support."
            )

        driver = gdal.GetDriverByName("GTiff")
        rows, cols = arr.shape
        ds = driver.Create(output_path, cols, rows, 1, gdal.GDT_Float32,
                           options=["COMPRESS=LZW", "TILED=YES"])
        if ds is None:
            raise RuntimeError(f"Could not create output file: {output_path}")

        ds.SetGeoTransform(geotransform)
        srs = osr.SpatialReference()
        srs.ImportFromWkt(crs_wkt)
        ds.SetProjection(srs.ExportToWkt())

        band = ds.GetRasterBand(1)
        band.WriteArray(arr.astype(np.float32))
        band.SetNoDataValue(-9999.0)
        band.FlushCache()
        ds.FlushCache()
        ds = None

    # ------------------------------------------------------------------
    def _save_multi_band(self, arr: np.ndarray, crs_wkt: str,
                          geotransform, output_path: str):
        """Save a (3, H, W) float32 array as a 3-band GeoTIFF."""
        try:
            from osgeo import gdal, osr
        except ImportError:
            raise RuntimeError(
                "GDAL Python bindings are not available."
            )

        bands, rows, cols = arr.shape
        driver = gdal.GetDriverByName("GTiff")
        ds = driver.Create(output_path, cols, rows, bands, gdal.GDT_Float32,
                           options=["COMPRESS=LZW", "TILED=YES"])
        if ds is None:
            raise RuntimeError(f"Could not create output file: {output_path}")

        ds.SetGeoTransform(geotransform)
        srs = osr.SpatialReference()
        srs.ImportFromWkt(crs_wkt)
        ds.SetProjection(srs.ExportToWkt())

        for b in range(bands):
            band_obj = ds.GetRasterBand(b + 1)
            band_obj.WriteArray(arr[b].astype(np.float32))
            band_obj.SetNoDataValue(-9999.0)
            band_obj.FlushCache()

        ds.FlushCache()
        ds = None

    # ------------------------------------------------------------------
    def _get_geotransform(self, layer):
        """Return a GDAL-style geotransform tuple from a QgsRasterLayer."""
        ext = layer.extent()
        xres = ext.width()  / layer.width()
        yres = ext.height() / layer.height()
        return (
            ext.xMinimum(),   # top-left X
            xres,             # pixel width
            0.0,
            ext.yMaximum(),   # top-left Y
            0.0,
            -yres,            # pixel height (negative)
        )

    # ------------------------------------------------------------------
    def run(self):
        try:
            p          = self.params
            is_composite = p["is_composite"]
            compute_fn   = p["compute_fn"]
            band_layers  = p["band_layers"]   # list of (QgsRasterLayer, band_no)
            output_path  = p["output_path"]

            self.progress.emit("Reading raster bands …")

            arrays = []
            crs_wkt      = None
            geotransform = None
            ref_layer    = None

            for layer, band_no in band_layers:
                if crs_wkt is None:
                    crs_wkt      = layer.crs().toWkt()
                    geotransform = self._get_geotransform(layer)
                    ref_layer    = layer
                arr = self._read_band(layer, band_no)
                arrays.append(arr.astype(np.float64))

            self.progress.emit("Computing index / composite …")
            result = compute_fn(*arrays)

            self.progress.emit("Saving output raster …")
            if is_composite:
                self._save_multi_band(result.astype(np.float32), crs_wkt,
                                      geotransform, output_path)
            else:
                self._save_single_band(result.astype(np.float32), crs_wkt,
                                       geotransform, output_path)

            self.finished.emit(output_path)

        except Exception:
            self.error.emit(traceback.format_exc())


# ---------------------------------------------------------------------------
# Dock widget UI
# ---------------------------------------------------------------------------

class SpectralIndicesDockWidget(QDockWidget):
    """Dockable panel for computing spectral indices and band composites."""

    _PANEL_STYLE = """
        QGroupBox {
            font-weight: bold;
            border: 1px solid palette(mid);
            border-radius: 4px;
            margin-top: 10px;
            padding: 6px 4px 4px 4px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
        }
        QTextEdit {
            font-family: Consolas, "Courier New", monospace;
            font-size: 9pt;
        }
        QPushButton#runBtn {
            font-weight: bold;
            padding: 6px 12px;
            border-radius: 4px;
        }
    """

    def __init__(self, iface, parent=None):
        super().__init__("Spectral Indices", parent)
        self.iface   = iface
        self.worker  = None

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setMinimumWidth(340)

        # ---- outer scroll so the panel does not get clipped ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer = QWidget()
        outer.setStyleSheet(self._PANEL_STYLE)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        outer_layout.setSpacing(8)
        scroll.setWidget(outer)
        self.setWidget(scroll)

        # ---- tab widget ----
        self.tabs = QTabWidget()
        outer_layout.addWidget(self.tabs)

        self._build_index_tab()
        self._build_composite_tab()

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_index_tab(self):
        """Build the single-band spectral index tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Index selector ────────────────────────────────────────────
        sel_group = QGroupBox("Index")
        sel_layout = QVBoxLayout(sel_group)
        sel_layout.setContentsMargins(6, 8, 6, 6)
        self.index_combo = QComboBox()
        self.index_combo.setToolTip("Select the spectral index to compute")
        for label, _, _ in SINGLE_BAND_INDICES:
            self.index_combo.addItem(label)
        self.index_combo.currentIndexChanged.connect(self._on_index_changed)
        sel_layout.addWidget(self.index_combo)
        layout.addWidget(sel_group)

        # ── Band assignment header with refresh button ─────────────────
        band_header = QHBoxLayout()
        band_header_label = QLabel("Band Assignment")
        band_header_label.setStyleSheet("font-weight: bold;")
        band_header.addWidget(band_header_label, 1)
        refresh_btn_index = QPushButton("🔄 Refresh Layers")
        refresh_btn_index.setFixedWidth(140)
        refresh_btn_index.setToolTip("Reload available raster layers")
        refresh_btn_index.clicked.connect(self._refresh_index_layers)
        band_header.addWidget(refresh_btn_index)
        layout.addLayout(band_header)

        # ── Band assignment (dynamically rebuilt) ─────────────────────
        self.index_bands_group = QGroupBox()
        self.index_bands_group.setLayout(QVBoxLayout())
        self.index_bands_group.layout().setContentsMargins(6, 8, 6, 6)
        self.index_bands_group.layout().setSpacing(4)
        layout.addWidget(self.index_bands_group)

        # ── Output ────────────────────────────────────────────────────
        out_group = QGroupBox("Output")
        out_layout = QVBoxLayout(out_group)
        out_layout.setContentsMargins(6, 8, 6, 6)
        out_layout.setSpacing(4)

        row_out = QHBoxLayout()
        self.index_output_edit = QLineEdit()
        self.index_output_edit.setPlaceholderText("Auto temp file (leave blank) …")
        row_out.addWidget(self.index_output_edit, 1)
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(28)
        btn_browse.setToolTip("Choose output GeoTIFF path")
        btn_browse.clicked.connect(lambda: self._browse_output(self.index_output_edit))
        row_out.addWidget(btn_browse)
        out_layout.addLayout(row_out)

        self.index_load_cb = QCheckBox("Load result into QGIS")
        self.index_load_cb.setChecked(True)
        out_layout.addWidget(self.index_load_cb)
        layout.addWidget(out_group)

        # ── Log ───────────────────────────────────────────────────────
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(6, 8, 6, 6)
        self.index_log = QTextEdit()
        self.index_log.setReadOnly(True)
        self.index_log.setMinimumHeight(80)
        self.index_log.setMaximumHeight(130)
        log_layout.addWidget(self.index_log)
        layout.addWidget(log_group)

        # ── Compute button ────────────────────────────────────────────
        self.index_run_btn = QPushButton("▶  Compute Index")
        self.index_run_btn.setObjectName("runBtn")
        self.index_run_btn.setMinimumHeight(34)
        self.index_run_btn.clicked.connect(self._run_index)
        layout.addWidget(self.index_run_btn)

        layout.addStretch()
        self.tabs.addTab(widget, "Spectral Index")

        # Populate initial band fields
        self._rebuild_band_fields(SINGLE_BAND_INDICES[0][1], self.index_bands_group, "index")

    # ------------------------------------------------------------------
    def _build_composite_tab(self):
        """Build the RGB band-composite tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Composite selector ────────────────────────────────────────
        sel_group = QGroupBox("Composite")
        sel_layout = QVBoxLayout(sel_group)
        sel_layout.setContentsMargins(6, 8, 6, 6)
        self.composite_combo = QComboBox()
        self.composite_combo.setToolTip("Select the band composite to generate")
        for label, _, _ in COMPOSITES:
            self.composite_combo.addItem(label)
        self.composite_combo.currentIndexChanged.connect(self._on_composite_changed)
        sel_layout.addWidget(self.composite_combo)
        layout.addWidget(sel_group)

        # ── Band assignment header with refresh button ─────────────────
        band_header2 = QHBoxLayout()
        band_header_label2 = QLabel("Band Assignment")
        band_header_label2.setStyleSheet("font-weight: bold;")
        band_header2.addWidget(band_header_label2, 1)
        refresh_btn_composite = QPushButton("🔄 Refresh Layers")
        refresh_btn_composite.setFixedWidth(140)
        refresh_btn_composite.setToolTip("Reload available raster layers")
        refresh_btn_composite.clicked.connect(self._refresh_composite_layers)
        band_header2.addWidget(refresh_btn_composite)
        layout.addLayout(band_header2)

        # ── Band assignment (dynamically rebuilt) ─────────────────────
        self.composite_bands_group = QGroupBox()
        self.composite_bands_group.setLayout(QVBoxLayout())
        self.composite_bands_group.layout().setContentsMargins(6, 8, 6, 6)
        self.composite_bands_group.layout().setSpacing(4)
        layout.addWidget(self.composite_bands_group)

        # ── Output ────────────────────────────────────────────────────
        out_group = QGroupBox("Output")
        out_layout = QVBoxLayout(out_group)
        out_layout.setContentsMargins(6, 8, 6, 6)
        out_layout.setSpacing(4)

        row_out = QHBoxLayout()
        self.composite_output_edit = QLineEdit()
        self.composite_output_edit.setPlaceholderText("Auto temp file (leave blank) …")
        row_out.addWidget(self.composite_output_edit, 1)
        btn_browse2 = QPushButton("…")
        btn_browse2.setFixedWidth(28)
        btn_browse2.setToolTip("Choose output GeoTIFF path")
        btn_browse2.clicked.connect(lambda: self._browse_output(self.composite_output_edit))
        row_out.addWidget(btn_browse2)
        out_layout.addLayout(row_out)

        self.composite_load_cb = QCheckBox("Load result into QGIS")
        self.composite_load_cb.setChecked(True)
        out_layout.addWidget(self.composite_load_cb)
        layout.addWidget(out_group)

        # ── Log ───────────────────────────────────────────────────────
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(6, 8, 6, 6)
        self.composite_log = QTextEdit()
        self.composite_log.setReadOnly(True)
        self.composite_log.setMinimumHeight(80)
        self.composite_log.setMaximumHeight(130)
        log_layout.addWidget(self.composite_log)
        layout.addWidget(log_group)

        # ── Generate button ───────────────────────────────────────────
        self.composite_run_btn = QPushButton("▶  Generate Composite")
        self.composite_run_btn.setObjectName("runBtn")
        self.composite_run_btn.setMinimumHeight(34)
        self.composite_run_btn.clicked.connect(self._run_composite)
        layout.addWidget(self.composite_run_btn)

        layout.addStretch()
        self.tabs.addTab(widget, "Band Composite")

        self._rebuild_band_fields(COMPOSITES[0][1], self.composite_bands_group, "composite")

    # ------------------------------------------------------------------
    # Dynamic band-field helpers
    # ------------------------------------------------------------------

    def _clear_layout(self, layout):
        """Recursively remove all items from *layout*, immediately hiding widgets."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    self._clear_layout(sub)

    def _rebuild_band_fields(self, band_names: list, group_box, prefix: str):
        """Replace the dynamic band-assignment rows inside *group_box*.

        A fresh QWidget container is created each time and swapped in, so
        the previous rows are immediately removed from the display (no overlap).
        """
        grp_layout = group_box.layout()

        # Remove and destroy the previous container widget (if any)
        if grp_layout.count() > 0:
            old_item = grp_layout.takeAt(0)
            old_w = old_item.widget()
            if old_w is not None:
                old_w.setParent(None)
                old_w.deleteLater()

        raster_layers = {
            layer.name(): layer
            for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsRasterLayer) and layer.isValid()
        }

        # Build a completely fresh container widget
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(4)

        combos = {}
        for bname in band_names:
            row = QHBoxLayout()
            row.setSpacing(4)

            lbl = QLabel(f"{bname}:")
            lbl.setFixedWidth(36)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl)

            layer_combo = QComboBox()
            layer_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layer_combo.setToolTip(f"Raster layer that contains {bname}")
            layer_combo.addItem("— select layer —", None)
            for name in sorted(raster_layers):
                layer_combo.addItem(name, raster_layers[name])
            row.addWidget(layer_combo, 3)

            band_spin = QSpinBox()
            band_spin.setMinimum(1)
            band_spin.setMaximum(200)
            band_spin.setValue(1)
            band_spin.setFixedWidth(55)
            band_spin.setToolTip("Band number within the selected layer")
            row.addWidget(band_spin)

            c_layout.addLayout(row)
            combos[bname] = (layer_combo, band_spin)

        grp_layout.addWidget(container)

        if prefix == "index":
            self._index_band_combos = combos
        else:
            self._composite_band_combos = combos

    # ------------------------------------------------------------------
    # Slot: index selection changed
    # ------------------------------------------------------------------

    def _on_index_changed(self, idx):
        _, band_names, _ = SINGLE_BAND_INDICES[idx]
        self._rebuild_band_fields(band_names, self.index_bands_group, "index")

    def _on_composite_changed(self, idx):
        _, band_names, _ = COMPOSITES[idx]
        self._rebuild_band_fields(band_names, self.composite_bands_group, "composite")

    # ------------------------------------------------------------------
    # Refresh layers
    # ------------------------------------------------------------------

    def _refresh_index_layers(self):
        """Refresh available layers in the Spectral Index tab."""
        idx = self.index_combo.currentIndex()
        _, band_names, _ = SINGLE_BAND_INDICES[idx]
        self._rebuild_band_fields(band_names, self.index_bands_group, "index")
        self.index_log.append("✓ Layer list refreshed.")

    def _refresh_composite_layers(self):
        """Refresh available layers in the Band Composite tab."""
        idx = self.composite_combo.currentIndex()
        _, band_names, _ = COMPOSITES[idx]
        self._rebuild_band_fields(band_names, self.composite_bands_group, "composite")
        self.composite_log.append("✓ Layer list refreshed.")

    # ------------------------------------------------------------------
    # Browse output
    # ------------------------------------------------------------------

    def _browse_output(self, line_edit: QLineEdit):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Output Raster",
            "",
            "GeoTIFF (*.tif *.tiff)",
        )
        if path:
            if not path.lower().endswith((".tif", ".tiff")):
                path += ".tif"
            line_edit.setText(path)

    # ------------------------------------------------------------------
    # Collect band assignments
    # ------------------------------------------------------------------

    def _collect_band_layers(self, combos: dict) -> list:
        """Return [(QgsRasterLayer, band_no), …] in dict-insertion order."""
        result = []
        for bname, (layer_combo, band_spin) in combos.items():
            layer = layer_combo.currentData()
            if layer is None:
                raise ValueError(
                    f"No layer selected for band {bname}. "
                    "Please choose a raster layer."
                )
            result.append((layer, band_spin.value()))
        return result

    # ------------------------------------------------------------------
    # Run helpers
    # ------------------------------------------------------------------

    def _get_output_path(self, line_edit: QLineEdit) -> str:
        path = line_edit.text().strip()
        if not path:
            fd, path = tempfile.mkstemp(suffix=".tif", prefix="geo_segment_")
            os.close(fd)
        return path

    def _run_index(self):
        if self.worker and self.worker.isRunning():
            self.index_log.append("Previous computation is still running …")
            return

        idx = self.index_combo.currentIndex()
        _, band_names, fn = SINGLE_BAND_INDICES[idx]

        try:
            band_layers = self._collect_band_layers(self._index_band_combos)
        except ValueError as e:
            QMessageBox.warning(self, "Geo Segment", str(e))
            return

        output_path       = self._get_output_path(self.index_output_edit)
        load_result       = self.index_load_cb.isChecked()
        index_label       = self.index_combo.currentText()

        params = {
            "is_composite": False,
            "compute_fn":   fn,
            "band_layers":  band_layers,
            "output_path":  output_path,
        }

        self.index_run_btn.setEnabled(False)
        self.index_log.clear()
        self.index_log.append(f"Starting: {index_label} …")

        self.worker = SpectralWorker(params)
        self.worker.progress.connect(lambda m: self.index_log.append(m))
        self.worker.finished.connect(
            lambda p: self._on_finished(p, load_result, index_label, self.index_run_btn, self.index_log)
        )
        self.worker.error.connect(
            lambda e: self._on_error(e, self.index_run_btn, self.index_log)
        )
        self.worker.start()

    def _run_composite(self):
        if self.worker and self.worker.isRunning():
            self.composite_log.append("Previous computation is still running …")
            return

        idx = self.composite_combo.currentIndex()
        _, band_names, fn = COMPOSITES[idx]

        try:
            band_layers = self._collect_band_layers(self._composite_band_combos)
        except ValueError as e:
            QMessageBox.warning(self, "Geo Segment", str(e))
            return

        output_path       = self._get_output_path(self.composite_output_edit)
        load_result       = self.composite_load_cb.isChecked()
        composite_label   = self.composite_combo.currentText()

        params = {
            "is_composite": True,
            "compute_fn":   fn,
            "band_layers":  band_layers,
            "output_path":  output_path,
        }

        self.composite_run_btn.setEnabled(False)
        self.composite_log.clear()
        self.composite_log.append(f"Starting: {composite_label} …")

        self.worker = SpectralWorker(params)
        self.worker.progress.connect(lambda m: self.composite_log.append(m))
        self.worker.finished.connect(
            lambda p: self._on_finished(p, load_result, composite_label, self.composite_run_btn, self.composite_log)
        )
        self.worker.error.connect(
            lambda e: self._on_error(e, self.composite_run_btn, self.composite_log)
        )
        self.worker.start()

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------

    def _on_finished(self, output_path, load_result, label, btn, log_widget):
        btn.setEnabled(True)
        log_widget.append(f"Done! Output saved to:\n  {output_path}")
        QgsMessageLog.logMessage(
            f"Spectral index saved: {output_path}", "Geo Segment", Qgis.Info
        )

        if load_result:
            layer_name = os.path.splitext(os.path.basename(output_path))[0]
            rlayer = QgsRasterLayer(output_path, layer_name)
            if rlayer.isValid():
                QgsProject.instance().addMapLayer(rlayer)
                log_widget.append(f"Layer '{layer_name}' added to the map.")
            else:
                log_widget.append("Warning: The output layer could not be loaded.")

    def _on_error(self, error_msg, btn, log_widget):
        btn.setEnabled(True)
        log_widget.append("ERROR:")
        log_widget.append(error_msg)
        QgsMessageLog.logMessage(error_msg, "Geo Segment", Qgis.Critical)
        QMessageBox.critical(
            self,
            "Geo Segment – Computation Error",
            "An error occurred during computation.\n"
            "See the log panel for details.",
        )
