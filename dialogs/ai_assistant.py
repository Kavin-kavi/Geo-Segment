"""
AI Assistant Panel – Autonomous geospatial assistant

Public API (imported by geo_segment_dock):
    AIAssistantPanel, route_prompt, MODULE_FRIENDLY, TOOLS, EXAMPLES
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import traceback
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from qgis.PyQt.QtCore import pyqtSignal, QThread, QTimer, QDateTime, Qt, QDate
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
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
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFillSymbol,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsMessageLog,
    Qgis,
)

# -------------------------------------------------
# Theme colours
# -------------------------------------------------

_C = {
    "user":        "#42A5F5",
    "assistant":   "#4CAF50",
    "error":       "#F44336",
    "muted":       "#888888",
    "status_ok":   "#4CAF50",
    "status_busy": "#FF9800",
}

# -------------------------------------------------
# Module registry
# -------------------------------------------------

MODULE_FRIENDLY: dict[str, str] = {
    "spectral":     "Spectral Indices",
    "samgeo":       "SAM Geo Segmentation",
    "deepforest":   "DeepForest Tree Detection",
    "water_seg":    "Water Segmentation",
    "semantic_seg": "Semantic Segmentation",
    "instance_seg": "Instance Segmentation",
    "moondream":    "Moondream Vision",
}

# Placeholder callable registry — dock may populate at runtime
TOOLS: dict[str, object] = {key: None for key in MODULE_FRIENDLY}

EXAMPLES: list[tuple[str, str]] = [
    ("Detect water bodies",       "water_seg"),
    ("Detect trees",              "deepforest"),
    ("Segment buildings",         "instance_seg"),
    ("Compute NDVI",              "spectral"),
    ("Describe the image",        "moondream"),
]

# Supported spectral indices: keyword → display label
SPECTRAL_INDICES: dict[str, str] = {
    "ndvi":  "NDVI",
    "ndwi":  "NDWI",
    "savi":  "SAVI",
    "evi":   "EVI",
    "ndsi":  "NDSI",
    "ndbi":  "NDBI",
    "nbr":   "NBR",
    "gci":   "GCI",
    "sipi":  "SIPI",
    "dnbr":  "dNBR",
}

# -------------------------------------------------
# Keyword routing (fallback when LLM is unavailable)
# -------------------------------------------------

KEYWORD_ROUTES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("moondream", "vlm", "caption", "describe", "vision", "what is in"),    "moondream"),
    (("water", "flood", "wetland", "river", "lake", "ocean"),                "water_seg"),
    (("tree", "forest", "canopy", "deepforest", "vegetation cover"),         "deepforest"),
    (("spectral", "ndvi", "ndwi", "savi", "evi", "ndsi",
      "ndbi", "nbr", "gci", "sipi", "dnbr", "index", "band"),               "spectral"),
    (("segment", "samgeo", "sam", "geosam", "mask"),                         "samgeo"),
    (("building", "urban", "structure", "instance"),                         "instance_seg"),
    (("semantic", "landcover", "land cover", "land use"),                    "semantic_seg"),
)


def route_prompt(prompt: str) -> str | None:
    """Return a module key via keyword matching, or ``None`` if no match."""
    lower = prompt.lower()
    for keywords, key in KEYWORD_ROUTES:
        if any(k in lower for k in keywords):
            return key
    return None

# -------------------------------------------------
# OpenRouter configuration
# -------------------------------------------------

OPENROUTER_KEYS: list[str] = [
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    "",
    "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",
    " ",
]


OPENROUTER_MODEL = "openai/gpt-4o-mini"

_SYSTEM_PROMPT = """You are a fully autonomous geospatial AI assistant embedded in QGIS (GeoSegment Plugin).
You have end-to-end automation capabilities.

CURRENT QGIS PROJECT STATE:
{qgis_context}

AVAILABLE TOOLS:
{tools_list}

SUPPORTED SPECTRAL INDICES:
{indices_list}

CITY COORDINATE BBOXES (WGS-84: lonmin, latmin, lonmax, latmax):
new delhi: [76.85, 28.40, 77.35, 28.90]
mumbai: [72.77, 18.89, 73.00, 19.27]
chennai: [80.18, 12.95, 80.28, 13.12]
kolkata: [88.25, 22.45, 88.45, 22.65]
bangalore: [77.49, 12.90, 77.65, 13.04]
hyderabad: [78.35, 17.30, 78.60, 17.50]
london: [-0.30, 51.40, 0.10, 51.60]
new york: [-74.10, 40.60, -73.85, 40.85]
paris: [2.25, 48.80, 2.42, 48.92]
beijing: [116.25, 39.85, 116.55, 40.05]
sydney: [150.95, -33.90, 151.30, -33.70]
tokyo: [139.65, 35.60, 139.85, 35.75]
dubai: [55.10, 25.05, 55.40, 25.30]

HOW TO RESPOND:
1. When the user asks to EXECUTE a task → respond with ONLY a JSON action (no explanation).
2. When the user asks a QUESTION or needs discussion → respond with plain text.
3. Maintain context across the conversation — remember what was discussed.

JSON ACTION FORMAT (respond with EXACTLY this, no extra text):
For satellite download:  {{"action":"download_satellite","bbox":[lonmin,latmin,lonmax,latmax],"days_back":30,"cloud_max":20}}
For water segmentation:  {{"action":"run_water_seg"}}
For tree detection:      {{"action":"run_deepforest"}}
For spectral index:      {{"action":"run_spectral","index":"NDVI"}}
For image description:   {{"action":"run_moondream","question":"What do you see?"}}
For SAM Go segment:      {{"action":"run_samgeo"}}
For instance segment:    {{"action":"run_instance_seg"}}
For semantic segment:    {{"action":"run_semantic_seg"}}

IMPORTANT RULES:
- If user gives coordinates or a city name → use download_satellite action.
- Extract bbox from city names using the table above.
- If user says "detect water", "find floods" → use run_water_seg.
- If user says "detect trees", "find canopy" → use run_deepforest.
- If user says "compute NDVI" or any spectral index → use run_spectral with the correct index.
- If user says "describe", "caption", "what is in this image" → use run_moondream.
- For questions about layers, data, CRS, extents → answer in plain text.
- Never ask for credentials — the system handles that automatically.
"""


# -------------------------------------------------
# Background Workers
# -------------------------------------------------


class WaterSegmentationWorker(QThread):
    """Background worker for water segmentation - non-blocking execution."""
    
    progress = pyqtSignal(str)  # Step description
    log_msg = pyqtSignal(str)   # Detailed log
    finished = pyqtSignal(str)  # Success: output path
    error = pyqtSignal(str)     # Error message

    def __init__(self, input_path: str, logger=None):
        super().__init__()
        self.input_path = input_path
        self.logger = logger
        self.output_vector = None
        self.output_raster = None

    def _log(self, msg: str, level: str = "INFO") -> None:
        """Log with timestamp and level."""
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss.zzz")
        log_entry = f"[{timestamp}] {level}: {msg}"
        self.log_msg.emit(log_entry)
        
        if self.logger:
            try:
                QgsMessageLog.logMessage(msg, "Geo Segment AI", Qgis.Info)
            except:
                pass

    def run(self) -> None:
        """Execute water segmentation in background."""
        try:
            self._log("═" * 60, "START")
            self._log(f"Water Segmentation Workflow Started", "START")
            self._log(f"Input: {self.input_path}", "INFO")
            
            # Step 1: Validate input
            self._log("▶ Step 1/5: Validating input file...", "STEP")
            self.progress.emit("▶ Step 1/5: Validating input...")
            
            if not os.path.exists(self.input_path):
                raise FileNotFoundError(f"Input file not found: {self.input_path}")
            
            file_size_mb = os.path.getsize(self.input_path) / (1024 * 1024)
            self._log(f"File size: {file_size_mb:.2f} MB", "DEBUG")
            
            if file_size_mb > 2000:
                self._log(f"WARNING: Large file ({file_size_mb:.2f} MB) may take longer", "WARN")
            
            self._log("✓ Input validation passed", "OK")
            
            # Step 2: Create output paths
            self._log("▶ Step 2/5: Creating output paths...", "STEP")
            self.progress.emit("▶ Step 2/5: Setting up output paths...")
            
            self.output_raster = tempfile.mktemp(suffix="_water_mask.tif")
            self.output_vector = tempfile.mktemp(suffix="_water_bodies.gpkg")
            
            self._log(f"Output raster: {self.output_raster}", "DEBUG")
            self._log(f"Output vector: {self.output_vector}", "DEBUG")
            self._log("✓ Output paths created", "OK")
            
            # Step 3: Run water segmentation (with parallel setup)
            self._log("▶ Step 3/5: Running water segmentation (OmniWaterMask)...", "STEP")
            self.progress.emit("▶ Step 3/5: Water segmentation (ML model)...")
            
            try:
                import geoai
                
                self._log("Importing geoai library...", "DEBUG")
                self._log("Calling geoai.segment_water()...", "DEBUG")
                
                # Call water segmentation
                geoai.segment_water(
                    self.input_path,
                    output_raster=self.output_raster,
                    output_vector=self.output_vector,
                    band_order="sentinel2",
                )
                
                self._log("✓ Water segmentation completed", "OK")
                
            except Exception as e:
                self._log(f"Water segmentation error: {str(e)}", "ERROR")
                self._log(traceback.format_exc(), "ERROR")
                raise
            
            # Step 4: Verify outputs exist
            self._log("▶ Step 4/5: Verifying outputs...", "STEP")
            self.progress.emit("▶ Step 4/5: Verifying results...")
            
            if not os.path.exists(self.output_raster):
                raise RuntimeError("Output raster not created")
            
            raster_size_mb = os.path.getsize(self.output_raster) / (1024 * 1024)
            self._log(f"Raster output: {raster_size_mb:.2f} MB", "DEBUG")
            
            # Optional: Vectorize if needed
            if not os.path.exists(self.output_vector) or os.path.getsize(self.output_vector) == 0:
                self._log("Vector file empty, vectorizing raster...", "DEBUG")
                
                try:
                    import geoai
                    geoai.utils.raster_to_vector(
                        self.output_raster,
                        self.output_vector,
                        simplify=True,
                        mode="binary",
                    )
                    self._log("✓ Raster vectorized", "OK")
                except Exception as e:
                    self._log(f"Vectorization error: {str(e)}", "WARN")
            
            vector_size_mb = os.path.getsize(self.output_vector) / (1024 * 1024) if os.path.exists(self.output_vector) else 0
            self._log(f"Vector output: {vector_size_mb:.2f} MB", "DEBUG")
            self._log("✓ Output verification passed", "OK")
            
            # Step 5: Complete
            self._log("▶ Step 5/5: Workflow complete!", "STEP")
            self.progress.emit("▶ Step 5/5: Complete!")
            self._log("═" * 60, "END")
            self._log("Water segmentation successful!", "SUCCESS")
            
            self.finished.emit(self.output_vector)
            
        except Exception as e:
            self._log(f"FATAL ERROR: {str(e)}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            self._log("═" * 60, "ERROR")
            self.error.emit(str(e))


# -------------------------------------------------
# Credentials Dialog (Copernicus / satellite providers)
# -------------------------------------------------


class CredentialsDialog(QDialog):
    """Modal dialog to collect Copernicus Data Space login credentials."""

    def __init__(self, parent=None, saved_user: str = "", saved_pass: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Copernicus Credentials")
        self.setMinimumWidth(380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            "Enter your <b>Copernicus Data Space</b> account credentials.<br>"
            "<small>Register free at <i>dataspace.copernicus.eu</i></small>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self._user = QLineEdit(saved_user)
        self._user.setPlaceholderText("user@example.com")
        self._pwd = QLineEdit(saved_pass)
        self._pwd.setEchoMode(QLineEdit.Password)
        self._pwd.setPlaceholderText("password")
        form.addRow("Username:", self._user)
        form.addRow("Password:", self._pwd)
        layout.addLayout(form)

        self._remember = QCheckBox("Remember for this session")
        self._remember.setChecked(bool(saved_user))
        layout.addWidget(self._remember)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Connect")
        ok_btn.setStyleSheet("background:#4CAF50;color:white;font-weight:bold;padding:6px 18px;")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def credentials(self) -> tuple[str, str, bool]:
        return self._user.text().strip(), self._pwd.text().strip(), self._remember.isChecked()


# -------------------------------------------------
# Layer Selection Dialog
# -------------------------------------------------


class LayerSelectionDialog(QDialog):
    """Dialog for selecting which raster files to import from downloaded data."""

    def __init__(self, file_list: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Bands / Layers to Import")
        self.setMinimumWidth(520)
        self.setMinimumHeight(380)
        self._file_list = file_list
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        hdr = QLabel("Select which files to import into QGIS:")
        hdr.setStyleSheet("font-weight:bold;font-size:12px;")
        layout.addWidget(hdr)

        # Quick filter row
        filter_row = QHBoxLayout()
        for label, res in [("10 m (RGB)", "R10m"), ("20 m", "R20m"), ("60 m", "R60m")]:
            btn = QPushButton(label)
            btn.setMaximumWidth(90)
            btn.clicked.connect(lambda _, r=res: self._filter_res(r))
            filter_row.addWidget(btn)
        sel_all = QPushButton("All")
        sel_all.setMaximumWidth(60)
        sel_all.clicked.connect(self._select_all)
        clr = QPushButton("None")
        clr.setMaximumWidth(60)
        clr.clicked.connect(self._clear_all)
        filter_row.addWidget(sel_all)
        filter_row.addWidget(clr)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.ExtendedSelection)
        for idx, item in enumerate(self._file_list):
            text = f"{item['name'][:48]}  [{item.get('res', '?')}]"
            li = QListWidgetItem(text)
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked if "R10m" in item.get("res", "") else Qt.Unchecked)
            li.setData(Qt.UserRole, idx)
            self._list.addItem(li)
        layout.addWidget(self._list, 1)

        btns = QHBoxLayout()
        ok = QPushButton("Import Selected")
        ok.setStyleSheet("background:#1976D2;color:white;font-weight:bold;padding:6px 16px;")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _select_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Checked)

    def _clear_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Unchecked)

    def _filter_res(self, res_tag: str):
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setCheckState(Qt.Checked if res_tag in item.text() else Qt.Unchecked)

    def get_selected(self) -> list[dict]:
        result = []
        for i in range(self._list.count()):
            li = self._list.item(i)
            if li.checkState() == Qt.Checked:
                result.append(self._file_list[li.data(Qt.UserRole)])
        return result


# -------------------------------------------------
# Satellite Download Worker (Copernicus via eodag)
# -------------------------------------------------


class SatelliteDownloadWorker(QThread):
    """Downloads best Sentinel-2 L2A scene for a given bbox via eodag."""

    progress = pyqtSignal(str)
    done = pyqtSignal(str)    # path to downloaded product/directory
    failed = pyqtSignal(str)

    def __init__(self, cfg: dict):
        super().__init__()
        self._cfg = cfg
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            os.environ["EODAG__COP_DATASPACE__AUTH__CREDENTIALS__USERNAME"] = self._cfg["username"]
            os.environ["EODAG__COP_DATASPACE__AUTH__CREDENTIALS__PASSWORD"] = self._cfg["password"]
            os.environ["EODAG_CACHE_PATH"] = str(Path(tempfile.gettempdir()) / "eodag_cache")

            try:
                from eodag import EODataAccessGateway, setup_logging
            except ImportError:
                self.failed.emit(
                    "eodag is not installed.\nRun: pip install eodag"
                )
                return

            setup_logging(verbose=0)
            self.progress.emit("🌍 Connecting to Copernicus Data Space…")
            dag = EODataAccessGateway()
            dag.set_preferred_provider("cop_dataspace")

            bbox = self._cfg["bbox"]
            end_date = date.today()
            start_date = end_date - timedelta(days=self._cfg.get("days_back", 30))

            self.progress.emit(
                f"🔍 Searching Sentinel-2 L2A products…\n"
                f"   Area: [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]\n"
                f"   Dates: {start_date} → {end_date}\n"
                f"   Max cloud: {self._cfg.get('cloud_max', 20)}%"
            )

            search_result = dag.search(
                productType="S2_MSI_L2A",
                cloudCover=self._cfg.get("cloud_max", 20),
                start=str(start_date),
                end=str(end_date),
                geom={"lonmin": bbox[0], "latmin": bbox[1], "lonmax": bbox[2], "latmax": bbox[3]},
            )
            results = search_result[0] if isinstance(search_result, tuple) else search_result

            if not results:
                self.failed.emit(
                    "No products found. Try:\n"
                    "• Increasing days_back (e.g. 90 days)\n"
                    "• Raising cloud cover limit"
                )
                return

            results.sort(key=lambda p: p.properties.get("cloudCover", 100))
            best = results[0]
            cloud = best.properties.get("cloudCover", "?")
            title = best.properties.get("title", "product")
            self.progress.emit(
                f"✓ Found {len(results)} product(s).\n"
                f"  Best: {title}\n"
                f"  Cloud cover: {cloud:.1f}%"
            )

            if self._cancel:
                self.failed.emit("Cancelled.")
                return

            out_dir = self._cfg.get("output_dir", str(Path.home() / "GeoSegment_Data"))
            Path(out_dir).mkdir(parents=True, exist_ok=True)

            self.progress.emit("⬇ Downloading… (this may take several minutes)")
            downloaded = best.download(outputs_prefix=str(out_dir), extract=False)
            downloaded_path = Path(str(downloaded))

            # Move to output dir if needed
            target = Path(out_dir) / downloaded_path.name
            if target.exists():
                self.done.emit(str(target))
            elif downloaded_path != target:
                import shutil
                try:
                    shutil.move(str(downloaded_path), str(target))
                    self.done.emit(str(target))
                except Exception:
                    self.done.emit(str(downloaded_path))
            else:
                self.done.emit(str(downloaded))

        except Exception as exc:
            err = str(exc)
            if "401" in err or "Unauthorized" in err:
                err = "Authentication failed (401). Check your Copernicus username and password."
            self.failed.emit(err)


# -------------------------------------------------
# Spectral Index Worker
# -------------------------------------------------

# Band index mapping for Sentinel-2 (1-indexed, standard band order in geoai)
# B02=1(Blue), B03=2(Green), B04=3(Red), B08=4(NIR), B8A=5(RedEdge), B11=6(SWIR1), B12=7(SWIR2)
def _safe_div(a, b):
    import numpy as np
    return np.where(b != 0, a / b.astype(float), 0.0)


_SPECTRAL_FORMULA: dict[str, Any] = {
    "NDVI":  lambda b: _safe_div(b[3] - b[2], b[3] + b[2]),           # NIR, Red
    "NDWI":  lambda b: _safe_div(b[1] - b[3], b[1] + b[3]),           # Green, NIR
    "SAVI":  lambda b: 1.5 * _safe_div(b[3] - b[2], b[3] + b[2] + 0.5),
    "EVI":   lambda b: 2.5 * _safe_div(b[3] - b[2], b[3] + 6*b[2] - 7.5*b[0] + 1),
    "NDSI":  lambda b: _safe_div(b[1] - b[5], b[1] + b[5]),           # Green, SWIR1
    "NDBI":  lambda b: _safe_div(b[5] - b[3], b[5] + b[3]),           # SWIR1, NIR
    "NBR":   lambda b: _safe_div(b[3] - b[6], b[3] + b[6]),           # NIR, SWIR2
    "GCI":   lambda b: _safe_div(b[3], b[1]) - 1,                     # NIR/Green - 1
    "SIPI":  lambda b: _safe_div(b[3] - b[0], b[3] + b[2]),           # NIR-Blue/NIR+Red
    "DNBR":  lambda b: _safe_div(b[3] - b[6], b[3] + b[6]),           # Same as NBR (pre-fire)
}

# Per-task spectral pipeline configuration
# index: which spectral formula to compute
# threshold: pixels above this value are treated as the target class
# label: human-readable name for the resulting vector layer
# color: RGBA fill colour string for the QGIS renderer
# sam_prompt: hint text passed to SAMGeo (informational, used for logging)
_TASK_CONFIG: dict[str, dict] = {
    "water":    {"index": "NDWI", "threshold":  0.0,  "label": "Water Bodies",    "color": "30,144,255,160",  "sam_prompt": "water body lake river flood"},
    "trees":    {"index": "NDVI", "threshold":  0.3,  "label": "Tree Canopy",     "color": "34,139,34,160",   "sam_prompt": "tree canopy forest vegetation"},
    "building": {"index": "NDBI", "threshold":  0.0,  "label": "Urban/Buildings", "color": "169,169,169,160", "sam_prompt": "buildings rooftops urban structures"},
    "burn":     {"index": "NBR",  "threshold": -0.1,  "label": "Burned Areas",    "color": "139,0,0,160",     "sam_prompt": "burned area fire damage charcoal"},
    "snow":     {"index": "NDSI", "threshold":  0.4,  "label": "Snow/Ice",        "color": "255,255,255,160", "sam_prompt": "snow ice glacier frozen"},
    "crop":     {"index": "SAVI", "threshold":  0.15, "label": "Cropland",        "color": "154,205,50,160",  "sam_prompt": "agricultural crops farmland"},
}


class SpectralIndexWorker(QThread):
    """Compute a spectral index on the active raster layer using GDAL/NumPy."""

    progress = pyqtSignal(str)
    done = pyqtSignal(str, str)   # (output_path, index_name)
    failed = pyqtSignal(str)

    def __init__(self, input_path: str, index_name: str):
        super().__init__()
        self.input_path = input_path
        self.index_name = index_name.upper()

    def run(self):
        try:
            import numpy as np
            try:
                from osgeo import gdal
            except ImportError:
                gdal = None

            if gdal is None:
                self.failed.emit("GDAL is not available. Cannot compute spectral index.")
                return

            formula = _SPECTRAL_FORMULA.get(self.index_name)
            if formula is None:
                self.failed.emit(f"Unknown spectral index: {self.index_name}")
                return

            self.progress.emit(f"📊 Opening raster: {os.path.basename(self.input_path)}")
            ds = gdal.Open(self.input_path)
            if not ds:
                self.failed.emit(f"Cannot open raster: {self.input_path}")
                return

            n_bands = ds.RasterCount
            self.progress.emit(f"  Bands: {n_bands}, Size: {ds.RasterXSize}×{ds.RasterYSize}")

            bands = []
            for i in range(n_bands):
                band = ds.GetRasterBand(i + 1)
                arr = band.ReadAsArray().astype(np.float32)
                nodata = band.GetNoDataValue()
                if nodata is not None:
                    arr[arr == nodata] = np.nan
                # Sentinel-2: values are in reflectance × 10000, normalize
                if arr.max() > 5.0:
                    arr = arr / 10000.0
                bands.append(arr)

            if len(bands) < 4:
                self.failed.emit(
                    f"Raster has only {len(bands)} bands. "
                    "Need at least 4 (Blue, Green, Red, NIR) for spectral indices."
                )
                return

            self.progress.emit(f"  Computing {self.index_name}…")
            result = formula(bands)
            result = np.clip(result, -1.0, 1.0)

            # Write result
            out_path = tempfile.mktemp(suffix=f"_{self.index_name}.tif")
            driver = gdal.GetDriverByName("GTiff")
            out_ds = driver.Create(
                out_path,
                ds.RasterXSize,
                ds.RasterYSize,
                1,
                gdal.GDT_Float32,
            )
            out_ds.SetGeoTransform(ds.GetGeoTransform())
            out_ds.SetProjection(ds.GetProjection())
            out_band = out_ds.GetRasterBand(1)
            out_band.WriteArray(result.astype(np.float32))
            out_band.SetNoDataValue(-9999)
            out_band.ComputeStatistics(False)
            out_ds.FlushCache()
            out_ds = None
            ds = None

            self.progress.emit(f"✓ {self.index_name} computed successfully")
            self.done.emit(out_path, self.index_name)

        except Exception as e:
            self.failed.emit(f"Spectral index error: {str(e)}\n{traceback.format_exc()}")


# -------------------------------------------------
# Spectral → SAMGeo Pipeline Worker
# -------------------------------------------------


class SpectralSAMGeoWorker(QThread):
    """
    Four-step pipeline: spectral index → threshold → optional SAMGeo → vectorize.

    Step 1 – Compute the spectral index defined in _TASK_CONFIG for *task*.
    Step 2 – Apply threshold + morphological cleanup to produce a binary mask.
    Step 3 – Optionally run SAMGeo automatic segmentation on the index image for
             more accurate polygon boundaries (can be disabled for speed).
    Step 4 – Vectorize the binary/SAM raster mask to GeoPackage polygons.
    """

    progress = pyqtSignal(str)
    done = pyqtSignal(str, str)   # (vector_path, label)
    failed = pyqtSignal(str)

    def __init__(self, input_path: str, task: str, use_samgeo: bool = True):
        super().__init__()
        self.input_path = input_path
        self.task = task          # key in _TASK_CONFIG (e.g. "water", "trees")
        self.use_samgeo = use_samgeo

    # ------------------------------------------------------------------
    def run(self):  # noqa: C901
        try:
            import numpy as np
        except ImportError:
            self.failed.emit("NumPy is not available.")
            return
        try:
            from osgeo import gdal, ogr, osr
        except ImportError:
            self.failed.emit("GDAL is not available. Cannot run Spectral pipeline.")
            return

        cfg = _TASK_CONFIG.get(self.task, _TASK_CONFIG["water"])
        index_name = cfg["index"]
        threshold  = cfg["threshold"]
        label      = cfg["label"]

        try:
            # ── Step 1: Compute spectral index ───────────────────────────────
            self.progress.emit(f"📊 <b>Step 1/4</b>: Computing {index_name}…")
            formula = _SPECTRAL_FORMULA.get(index_name)
            if formula is None:
                self.failed.emit(f"Unknown spectral index: {index_name}")
                return

            ds = gdal.Open(self.input_path)
            if not ds:
                self.failed.emit(f"Cannot open raster: {self.input_path}")
                return

            geo_transform = ds.GetGeoTransform()
            projection    = ds.GetProjection()
            xsize         = ds.RasterXSize
            ysize         = ds.RasterYSize

            bands = []
            for i in range(ds.RasterCount):
                bnd = ds.GetRasterBand(i + 1)
                arr = bnd.ReadAsArray().astype(np.float32)
                nd  = bnd.GetNoDataValue()
                if nd is not None:
                    arr[arr == nd] = np.nan
                if np.nanmax(arr) > 5.0:     # Sentinel-2 DN → reflectance
                    arr /= 10_000.0
                bands.append(arr)
            ds = None

            if len(bands) < 4:
                self.failed.emit(
                    f"Raster has only {len(bands)} band(s). "
                    "Need ≥4 (Blue, Green, Red, NIR) for spectral indices."
                )
                return

            index_arr = formula(bands)
            index_arr = np.where(np.isnan(index_arr), -9999.0, np.clip(index_arr, -1.0, 1.0))

            # Save spectral index to a temp GeoTIFF
            spectral_path = tempfile.mktemp(suffix=f"_{index_name}.tif")
            drv = gdal.GetDriverByName("GTiff")
            out_ds = drv.Create(spectral_path, xsize, ysize, 1, gdal.GDT_Float32)
            out_ds.SetGeoTransform(geo_transform)
            out_ds.SetProjection(projection)
            out_b = out_ds.GetRasterBand(1)
            out_b.WriteArray(index_arr.astype(np.float32))
            out_b.SetNoDataValue(-9999)
            out_b.ComputeStatistics(False)
            out_ds.FlushCache()
            out_ds = None

            valid = index_arr != -9999
            vals  = index_arr[valid]
            self.progress.emit(
                f"  ✓ {index_name} range: [{float(vals.min()):.3f}, {float(vals.max()):.3f}]"
            )

            # ── Step 2: Threshold → binary mask ────────────────────────────
            self.progress.emit(
                f"🔲 <b>Step 2/4</b>: Threshold ({index_name} &gt; {threshold})…"
            )
            binary = np.zeros((ysize, xsize), dtype=np.uint8)
            binary[(index_arr > threshold) & valid] = 1

            # Optional morphological cleanup (closes small gaps / noise)
            try:
                from scipy.ndimage import binary_erosion, binary_dilation
                struct = np.ones((3, 3), dtype=bool)
                binary = binary_dilation(
                    binary_erosion(binary.astype(bool), struct), struct
                ).astype(np.uint8)
            except ImportError:
                pass  # scipy not available; use raw threshold mask

            n_pix = int(binary.sum())
            self.progress.emit(f"  ✓ {n_pix:,} pixels above threshold")

            if n_pix < 10:
                self.failed.emit(
                    f"No significant {label.lower()} detected "
                    f"({index_name} &gt; {threshold}).\n"
                    "Check band order (Blue, Green, Red, NIR…) or lower the threshold."
                )
                return

            mask_path = tempfile.mktemp(suffix="_mask.tif")
            out_ds = drv.Create(mask_path, xsize, ysize, 1, gdal.GDT_Byte)
            out_ds.SetGeoTransform(geo_transform)
            out_ds.SetProjection(projection)
            out_b = out_ds.GetRasterBand(1)
            out_b.WriteArray(binary)
            out_b.SetNoDataValue(0)
            out_ds.FlushCache()
            out_ds = None

            # ── Step 3: Optional SAMGeo refinement ─────────────────────────
            sam_mask_path = mask_path
            if self.use_samgeo:
                self.progress.emit("🎯 <b>Step 3/4</b>: SAMGeo refinement…")
                sam_result = self._run_samgeo(spectral_path)
                if sam_result and os.path.exists(sam_result):
                    sam_mask_path = sam_result
                    self.progress.emit("  ✓ SAMGeo masks applied")
                else:
                    self.progress.emit("  ⚠ SAMGeo unavailable — using threshold mask")
            else:
                self.progress.emit("⏭ <b>Step 3/4</b>: SAMGeo skipped (threshold-only mode)")

            # ── Step 4: Vectorize ──────────────────────────────────────────
            self.progress.emit("🗺 <b>Step 4/4</b>: Vectorizing mask to polygons…")
            out_vector = tempfile.mktemp(suffix=f"_{self.task}.gpkg")
            self._vectorize(sam_mask_path, out_vector, label, projection, gdal, ogr, osr)
            self.progress.emit(f"  ✓ {label} polygons ready")

            self.done.emit(out_vector, label)

        except Exception as e:
            self.failed.emit(f"Pipeline error: {str(e)}\n{traceback.format_exc()}")

    # ------------------------------------------------------------------
    def _run_samgeo(self, spectral_path: str) -> "str | None":
        """Attempt to run SAMGeo automatic mask generation; return path or None."""
        try:
            out_tif = tempfile.mktemp(suffix="_sam_masks.tif")
            if os.name == "nt":
                # On Windows: avoid DLL conflicts by using subprocess client
                from ..core.samgeo_subprocess import SamGeoSubprocessClient  # type: ignore
                client = SamGeoSubprocessClient()
                client.initialize(model_type="vit_h")
                client.generate(spectral_path, out_tif)
                return out_tif
            # Non-Windows: try direct import
            from samgeo import SamGeo   # type: ignore
            sam = SamGeo(model_type="vit_h", automatic=True)
            sam.generate(spectral_path, out_tif)
            return out_tif
        except Exception:
            return None

    # ------------------------------------------------------------------
    @staticmethod
    def _vectorize(
        raster_path: str,
        out_vector: str,
        layer_name: str,
        projection: str,
        gdal,
        ogr,
        osr,
    ) -> None:
        """Convert binary raster mask to vector polygons (GDAL Polygonize)."""
        src_ds   = gdal.Open(raster_path)
        src_band = src_ds.GetRasterBand(1)
        srs      = osr.SpatialReference()
        srs.ImportFromWkt(projection)
        drv_v   = ogr.GetDriverByName("GPKG")
        out_ds  = drv_v.CreateDataSource(out_vector)
        out_lyr = out_ds.CreateLayer(layer_name, srs=srs, geom_type=ogr.wkbPolygon)
        field   = ogr.FieldDefn("class", ogr.OFTInteger)
        out_lyr.CreateField(field)
        gdal.Polygonize(src_band, src_band, out_lyr, 0, [], callback=None)
        out_ds.FlushCache()
        out_ds = None
        src_ds = None


# -------------------------------------------------
# DeepForest Inference Worker
# -------------------------------------------------


class DeepForestInferenceWorker(QThread):
    """Run DeepForest tree detection on the active raster layer."""

    progress = pyqtSignal(str)
    done = pyqtSignal(str)   # output vector path
    failed = pyqtSignal(str)

    def __init__(self, input_path: str):
        super().__init__()
        self.input_path = input_path

    def run(self):
        try:
            self.progress.emit("🌲 Loading DeepForest model (subprocess)…")

            if os.name == "nt":
                # Use subprocess client on Windows to avoid DLL conflicts
                try:
                    from ..core.deepforest_subprocess import DeepForestSubprocessClient
                    client = DeepForestSubprocessClient(
                        model_name="weecology/deepforest-tree",
                        revision="main",
                        device="cpu",
                    )
                    self.progress.emit("  Initializing model…")
                    client.initialize()

                    self.progress.emit("  Running tree detection…")
                    out_path = tempfile.mktemp(suffix="_trees.gpkg")
                    results = client.predict_tile(
                        raster_path=self.input_path,
                        output_path=out_path,
                        patch_size=400,
                        patch_overlap=0.05,
                    )
                    self.progress.emit(f"✓ Detection complete: {results}")
                    self.done.emit(out_path if os.path.exists(out_path) else str(results))
                    return
                except ImportError:
                    pass

            # Direct import fallback
            self.progress.emit("  Importing deepforest…")
            from deepforest import main as df_main
            model = df_main.deepforest()
            model.use_release()

            self.progress.emit("  Running prediction on tile…")
            import numpy as np
            predicted_boxes = model.predict_tile(
                raster_path=self.input_path,
                return_plot=False,
                patch_size=400,
                patch_overlap=0.05,
            )

            if predicted_boxes is None or len(predicted_boxes) == 0:
                self.failed.emit("No trees detected in this image.")
                return

            # Save to temp GeoJSON
            out_path = tempfile.mktemp(suffix="_trees.geojson")
            predicted_boxes.to_file(out_path, driver="GeoJSON")
            self.progress.emit(f"✓ Detected {len(predicted_boxes)} tree crowns")
            self.done.emit(out_path)

        except ImportError:
            self.failed.emit(
                "DeepForest is not installed.\n"
                "Install via the plugin dependency installer for automatic setup."
            )
        except Exception as e:
            self.failed.emit(f"DeepForest error: {str(e)}\n{traceback.format_exc()}")


# -------------------------------------------------
# Moondream Inference Worker
# -------------------------------------------------


class MoondreamInferenceWorker(QThread):
    """Run Moondream VLM captioning/querying on the active raster."""

    progress = pyqtSignal(str)
    done = pyqtSignal(str)   # text result
    failed = pyqtSignal(str)

    def __init__(self, input_path: str, question: str = "Describe this satellite image in detail."):
        super().__init__()
        self.input_path = input_path
        self.question = question

    def run(self):
        try:
            self.progress.emit("👁 Loading Moondream VLM (subprocess)…")

            try:
                from ..core.moondream_subprocess import MoondreamSubprocessClient
                client = MoondreamSubprocessClient(
                    model_name="vikhyatk/moondream2",
                    device=None,
                )
                self.progress.emit("  Initializing model…")
                client.initialize()

                self.progress.emit(f"  Querying: {self.question}")

                # Export active layer region as PNG for VLM
                img_path = self._export_raster_as_image(self.input_path)

                result = client.query(img_path, self.question)
                answer = result.get("answer", str(result)) if isinstance(result, dict) else str(result)
                self.progress.emit("✓ Moondream analysis complete")
                self.done.emit(answer)

            except ImportError:
                self.failed.emit(
                    "Moondream subprocess client not found.\n"
                    "Install dependencies via the plugin installer."
                )

        except Exception as e:
            self.failed.emit(f"Moondream error: {str(e)}\n{traceback.format_exc()}")

    def _export_raster_as_image(self, raster_path: str) -> str:
        """Export raster to a viewable PNG/JPEG for VLM input."""
        try:
            from osgeo import gdal
            import numpy as np

            ds = gdal.Open(raster_path)
            if not ds:
                return raster_path  # fallback: pass original

            # Read first 3 bands (or fewer) as RGB
            n = min(ds.RasterCount, 3)
            channels = []
            for i in range(1, n + 1):
                arr = ds.GetRasterBand(i).ReadAsArray().astype(np.float32)
                arr_max = arr.max()
                if arr_max > 1.0:
                    arr = (arr / max(arr_max, 10000.0) * 255).clip(0, 255)
                channels.append(arr.astype(np.uint8))

            if len(channels) == 1:
                channels = channels * 3

            out_img = tempfile.mktemp(suffix="_preview.png")
            from PIL import Image
            rgb = np.stack(channels, axis=-1)
            Image.fromarray(rgb).save(out_img)
            ds = None
            return out_img
        except Exception:
            return raster_path  # fallback


# -------------------------------------------------
# Workflow Orchestrator
# -------------------------------------------------


class WorkflowOrchestrator:
    """Executes end-to-end geospatial workflows with automatic step chaining."""

    def __init__(self, chat_callback, error_callback, parent=None):
        """Initialize orchestrator.
        
        Args:
            chat_callback: Function(message_html) to update chat history
            error_callback: Function(error_msg) to display errors
            parent: Parent widget (for message boxes if needed)
        """
        self.chat = chat_callback
        self.error = error_callback
        self.parent = parent
        self._temp_files = []

    def _log(self, msg: str) -> None:
        """Log to QGIS message log."""
        QgsMessageLog.logMessage(msg, "Geo Segment AI", Qgis.Info)

    def _get_active_raster_layer(self):
        """Get the currently active raster layer from QGIS."""
        # Search all loaded layers for the first valid raster layer
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer) and layer.isValid():
                return layer
        return None

    def _execute_water_segmentation_workflow(self) -> str | None:
        """Execute: Select raster → Water Seg → Vector → Display workflow.
        
        Uses background thread for non-blocking execution with detailed logging.
        Returns: Path to output geopackage file, or None on failure.
        """
        try:
            # Step 0: Get active raster layer
            self.chat("<b>▶ STEP 1/5: Validating input...</b>")
            layer = self._get_active_raster_layer()
            if not layer:
                self.error("❌ No active raster layer found. Load a raster (GeoTIFF, JP2, etc.) first.")
                return None
            
            input_path = layer.source()
            layer_name = layer.name()
            self.chat(f"✓ Input layer: <b>{layer_name}</b>")
            self.chat(f"  File: {os.path.basename(input_path)}")
            self.chat(f"  📊 Size: {layer.width()}×{layer.height()} pixels")
            
            # Step 1: Create output paths
            self.chat("<b>▶ STEP 2/5: Preparing output...</b>")
            output_raster = tempfile.mktemp(suffix="_water_mask.tif")
            output_vector = tempfile.mktemp(suffix="_water_bodies.gpkg")
            self._temp_files.extend([output_raster, output_vector])
            
            self.chat(f"✓ Output paths created")
            
            # Step 2: Create and configure worker thread
            self.chat("<b>▶ STEP 3/5: Running water segmentation...</b>")
            self.chat(f"  ⏳ This may take 1-5 minutes depending on image size...")
            
            worker = WaterSegmentationWorker(input_path)
            
            # Connect signals
            worker.progress.connect(lambda msg: self.chat(msg))
            worker.log_msg.connect(lambda msg: self._log(msg))
            worker.finished.connect(
                lambda vec_path: self._on_water_segmentation_complete(worker, vec_path, output_vector)
            )
            worker.error.connect(
                lambda err: self._on_water_segmentation_error(err)
            )
            
            # Apply the output paths to worker
            worker.output_raster = output_raster
            worker.output_vector = output_vector
            
            # Store worker reference if parent is the panel
            if self.parent and hasattr(self.parent, '_water_worker'):
                self.parent._water_worker = worker
            
            # Start worker thread (non-blocking)
            worker.start()
            
            # Enable spinner animation if parent has _timer
            if self.parent and hasattr(self.parent, '_timer'):
                self.parent._timer.start(100)
            
            return "PENDING"  # Indicates async execution
            
        except Exception as e:
            if self.parent and hasattr(self.parent, '_timer'):
                self.parent._timer.stop()
            self.error(f"❌ Workflow setup failed: {str(e)}")
            return None

    def _on_water_segmentation_complete(self, worker, vec_path: str, expected_output: str) -> None:
        """Handle successful water segmentation completion."""
        try:
            if self.parent and hasattr(self.parent, '_set_processing'):
                self.parent._set_processing(False)
            elif self.parent and hasattr(self.parent, '_timer'):
                self.parent._timer.stop()
            
            # Step 4: Verify outputs
            self.chat("<b>▶ STEP 4/5: Verifying results...</b>")
            
            if not os.path.exists(expected_output):
                self.chat(f"⚠️  Vector not auto-generated, using raster...")
                vec_path = worker.output_raster
            else:
                vec_size_mb = os.path.getsize(expected_output) / (1024 * 1024)
                self.chat(f"✓ Vector file verified ({vec_size_mb:.2f} MB)")
            
            # Step 5: Add layers to QGIS map
            self.chat("<b>▶ STEP 5/5: Loading results into map...</b>")
            
            # Load vector layer
            if os.path.exists(expected_output):
                vector_layer = QgsVectorLayer(expected_output, "Water Bodies", "ogr")
                if vector_layer.isValid():
                    QgsProject.instance().addMapLayer(vector_layer)
                    
                    # Apply styling
                    from qgis.core import QgsFillSymbol
                    symbol = QgsFillSymbol.createSimple({
                        'color': '100, 180, 255, 160',
                        'color_border': '0, 80, 200, 255',
                        'width_border': '1.5'
                    })
                    vector_layer.renderer().setSymbol(symbol)
                    vector_layer.triggerRepaint()
                    
                    self.chat(f"✓ Vector layer: <b>{vector_layer.name()}</b> added to map")
            
            # Load raster layer (optional)
            if os.path.exists(worker.output_raster):
                raster_layer = QgsRasterLayer(worker.output_raster, "Water Mask (Raster)")
                if raster_layer.isValid():
                    QgsProject.instance().addMapLayer(raster_layer)
                    self.chat(f"✓ Raster layer: <b>{raster_layer.name()}</b> added to map")
            
            self.chat("")
            self.chat("<b>✅ WATER SEGMENTATION COMPLETE!</b>")
            self.chat(f"  Output: {os.path.basename(expected_output)}")
            self.chat(f"  💾 Temporary location: {expected_output}")
            
        except Exception as e:
            if self.parent and hasattr(self.parent, '_timer'):
                self.parent._timer.stop()
            self.error(f"❌ Completion handler failed: {str(e)}")
            traceback.print_exc()

    def _on_water_segmentation_error(self, err: str) -> None:
        """Handle water segmentation error."""
        if self.parent and hasattr(self.parent, '_set_processing'):
            self.parent._set_processing(False)
        elif self.parent and hasattr(self.parent, '_timer'):
            self.parent._timer.stop()
        self.error(f"❌ Water segmentation failed:\n{err}")

    # ── Spectral Index ───────────────────────────────────────────────────────

    def execute_spectral(self, index_name: str) -> str | None:
        """Compute a spectral index on the active raster layer."""
        layer = self._get_active_raster_layer()
        if not layer:
            self.error("❌ No raster layer loaded. Load a satellite image first.")
            return None

        input_path = layer.source()
        self.chat(f"📊 <b>Computing {index_name}</b> on <b>{layer.name()}</b>…")

        worker = SpectralIndexWorker(input_path, index_name)
        worker.progress.connect(lambda msg: self.chat(msg))
        worker.done.connect(self._on_spectral_done)
        worker.failed.connect(self._on_spectral_failed)
        if self.parent and hasattr(self.parent, '_active_workers'):
            self.parent._active_workers.append(worker)
        worker.start()
        return "PENDING"

    def _on_spectral_done(self, out_path: str, index_name: str) -> None:
        if self.parent and hasattr(self.parent, '_set_processing'):
            self.parent._set_processing(False)
        layer = QgsRasterLayer(out_path, f"{index_name} Index")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self.chat(f"✅ <b>{index_name}</b> layer added to map.")
        else:
            self.error(f"Could not load {index_name} layer: {out_path}")

    def _on_spectral_failed(self, err: str) -> None:
        if self.parent and hasattr(self.parent, '_set_processing'):
            self.parent._set_processing(False)
        self.error(f"❌ Spectral index failed:\n{err}")

    # ── DeepForest ───────────────────────────────────────────────────────────

    def execute_deepforest(self) -> str | None:
        """Run DeepForest tree detection on the active raster."""
        layer = self._get_active_raster_layer()
        if not layer:
            self.error("❌ No raster layer loaded. Load a satellite image first.")
            return None

        input_path = layer.source()
        self.chat(f"🌲 <b>DeepForest tree detection</b> on <b>{layer.name()}</b>…")
        self.chat("  ⏳ Loading model and running detection (may take a few minutes)…")

        worker = DeepForestInferenceWorker(input_path)
        worker.progress.connect(lambda msg: self.chat(msg))
        worker.done.connect(self._on_deepforest_done)
        worker.failed.connect(self._on_deepforest_failed)
        if self.parent and hasattr(self.parent, '_active_workers'):
            self.parent._active_workers.append(worker)
        worker.start()
        return "PENDING"

    def _on_deepforest_done(self, out_path: str) -> None:
        if self.parent and hasattr(self.parent, '_set_processing'):
            self.parent._set_processing(False)
        vec_layer = QgsVectorLayer(out_path, "Tree Crowns (DeepForest)", "ogr")
        if vec_layer.isValid():
            QgsProject.instance().addMapLayer(vec_layer)
            count = vec_layer.featureCount()
            self.chat(f"✅ <b>Tree detection complete:</b> {count} tree crowns detected.")
        else:
            self.error(f"Could not load tree detection results: {out_path}")

    def _on_deepforest_failed(self, err: str) -> None:
        if self.parent and hasattr(self.parent, '_set_processing'):
            self.parent._set_processing(False)
        self.error(f"❌ DeepForest failed:\n{err}")

    # ── Moondream VLM ────────────────────────────────────────────────────────

    def execute_moondream(self, question: str) -> str | None:
        """Run Moondream VLM on the active raster."""
        layer = self._get_active_raster_layer()
        if not layer:
            self.error("❌ No raster layer loaded. Load a satellite image first.")
            return None

        input_path = layer.source()
        self.chat(f"👁 <b>Moondream VLM</b> analyzing <b>{layer.name()}</b>…")
        self.chat(f'  Question: "<i>{question}</i>"')

        worker = MoondreamInferenceWorker(input_path, question)
        worker.progress.connect(lambda msg: self.chat(msg))
        worker.done.connect(self._on_moondream_done)
        worker.failed.connect(self._on_moondream_failed)
        if self.parent and hasattr(self.parent, '_active_workers'):
            self.parent._active_workers.append(worker)
        worker.start()
        return "PENDING"

    def _on_moondream_done(self, answer: str) -> None:
        if self.parent and hasattr(self.parent, '_set_processing'):
            self.parent._set_processing(False)
        self.chat(f"✅ <b>Moondream analysis:</b><br>{answer}")
        # Feed answer back into conversation
        if self.parent and hasattr(self.parent, '_conversation'):
            self.parent._conversation.append({"role": "assistant", "content": answer})

    def _on_moondream_failed(self, err: str) -> None:
        if self.parent and hasattr(self.parent, '_set_processing'):
            self.parent._set_processing(False)
        self.error(f"❌ Moondream failed:\n{err}")

    # ── Satellite Download ───────────────────────────────────────────────────

    def execute_satellite_download(self, bbox: list, days_back: int = 30, cloud_max: int = 20) -> str | None:
        """Ask for credentials then download Sentinel-2 for the given bbox."""
        saved_user = ""
        saved_pass = ""
        if self.parent and hasattr(self.parent, '_credentials'):
            saved_user = self.parent._credentials.get("user", "")
            saved_pass = self.parent._credentials.get("pwd", "")

        dlg = CredentialsDialog(self.parent, saved_user, saved_pass)
        if dlg.exec() != QDialog.Accepted:
            self.chat("⚠️ Download cancelled (no credentials provided).")
            return None

        user, pwd, remember = dlg.credentials()
        if not user or not pwd:
            self.error("❌ Username and password are required.")
            return None

        if remember and self.parent and hasattr(self.parent, '_credentials'):
            self.parent._credentials = {"user": user, "pwd": pwd}

        out_dir = str(Path.home() / "GeoSegment_Data")
        self.chat(
            f"🛰 <b>Satellite download</b><br>"
            f"  Area: [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]<br>"
            f"  Days back: {days_back} | Max cloud: {cloud_max}%<br>"
            f"  Output: {out_dir}"
        )

        cfg = {
            "username": user,
            "password": pwd,
            "bbox": bbox,
            "days_back": days_back,
            "cloud_max": cloud_max,
            "output_dir": out_dir,
        }

        worker = SatelliteDownloadWorker(cfg)
        worker.progress.connect(lambda msg: self.chat(msg))
        worker.done.connect(lambda p: self._on_satellite_done(p))
        worker.failed.connect(lambda e: self._on_satellite_failed(e))
        if self.parent and hasattr(self.parent, '_active_workers'):
            self.parent._active_workers.append(worker)
        if self.parent and hasattr(self.parent, '_sat_worker'):
            self.parent._sat_worker = worker
        worker.start()
        return "PENDING"

    def _on_satellite_done(self, path: str) -> None:
        """After download, show layer selection dialog and import chosen files."""
        self.chat(f"✓ <b>Download complete:</b> {os.path.basename(path)}")
        self.chat("  Scanning for available bands/files…")

        try:
            download_path = Path(path)

            # Extract ZIP if needed
            if download_path.suffix.lower() == ".zip":
                import zipfile as _zf
                self.chat("  Extracting archive…")
                extract_dir = download_path.parent / download_path.stem
                if not extract_dir.exists():
                    with _zf.ZipFile(str(download_path), "r") as zf:
                        zf.extractall(str(extract_dir))
                download_path = extract_dir

            # Collect raster files
            tif_files = sorted(download_path.rglob("*.tif")) + sorted(download_path.rglob("*.TIF"))
            jp2_files = sorted(download_path.rglob("*.jp2")) + sorted(download_path.rglob("*.JP2"))
            all_files = tif_files + jp2_files

            if not all_files:
                self.error(f"No raster files found in {download_path}")
                if self.parent and hasattr(self.parent, '_set_processing'):
                    self.parent._set_processing(False)
                return

            file_list = []
            for f in all_files:
                res = "?"
                fname = str(f)
                if "R10m" in fname: res = "R10m (10m RGB)"
                elif "R20m" in fname: res = "R20m (20m)"
                elif "R60m" in fname: res = "R60m (60m)"
                file_list.append({"path": f, "name": f.stem[:50], "res": res})

            self.chat(f"  Found {len(file_list)} raster file(s). Showing selection dialog…")

            dlg = LayerSelectionDialog(file_list, self.parent)
            if dlg.exec() == QDialog.Accepted:
                selected = dlg.get_selected()
                if selected:
                    loaded = 0
                    for fi in selected:
                        layer = QgsRasterLayer(str(fi["path"]), fi["name"])
                        if layer.isValid():
                            QgsProject.instance().addMapLayer(layer)
                            loaded += 1
                            self.chat(f"  ✓ Loaded: <b>{fi['name']}</b> [{fi['res']}]")
                        else:
                            self.chat(f"  ⚠ Failed to load: {fi['name']}")
                    self.chat(f"<b>✅ {loaded} layer(s) imported to QGIS map.</b>")
                    self.chat("You can now run water segmentation, spectral analysis, or any other workflow.")
                else:
                    self.chat("No layers selected. Data is at: " + str(path))
            else:
                self.chat("Import cancelled. Data saved at: " + str(path))

        except Exception as e:
            self.error(f"❌ Layer import failed: {str(e)}")
        finally:
            if self.parent and hasattr(self.parent, '_set_processing'):
                self.parent._set_processing(False)

    def _on_satellite_failed(self, err: str) -> None:
        if self.parent and hasattr(self.parent, '_set_processing'):
            self.parent._set_processing(False)
        self.error(f"❌ Download failed:\n{err}")

    # ── Spectral → SAMGeo pipeline ───────────────────────────────────────────

    def execute_spectral_samgeo(self, task: str) -> "str | None":
        """
        Run the Spectral Index → threshold → (optional SAMGeo) → vectorize pipeline.

        *task* must be a key in _TASK_CONFIG (e.g. "water", "trees", "building").
        Returns "PENDING" when the worker has been started, or None on early failure.
        """
        layer = self._get_active_raster_layer()
        if not layer:
            self.error(
                "❌ No raster layer detected. "
                "Please load a Sentinel-2 image first (use the satellite download flow)."
            )
            return None

        # Read the "Use SAMGeo refinement" checkbox from the panel (if available)
        use_sam = (
            self.parent is not None
            and hasattr(self.parent, "_use_samgeo_chk")
            and self.parent._use_samgeo_chk is not None
            and self.parent._use_samgeo_chk.isChecked()
        )

        cfg = _TASK_CONFIG.get(task, _TASK_CONFIG["water"])
        self.chat(
            f"🔬 <b>Spectral Pipeline</b>: {cfg['index']} → "
            f"{'SAMGeo' if use_sam else 'Threshold'} → {cfg['label']}"
        )

        worker = SpectralSAMGeoWorker(layer.source(), task, use_samgeo=use_sam)
        worker.progress.connect(lambda msg: self.chat(msg))
        worker.done.connect(lambda p, lbl: self._on_spectral_samgeo_done(p, lbl, cfg))
        worker.failed.connect(self._on_spectral_samgeo_failed)
        if self.parent and hasattr(self.parent, "_active_workers"):
            self.parent._active_workers.append(worker)
        worker.start()
        return "PENDING"

    def _on_spectral_samgeo_done(self, vector_path: str, label: str, cfg: dict) -> None:
        """Load the vectorized result into QGIS with a colour fill."""
        try:
            vlayer = QgsVectorLayer(vector_path, label, "ogr")
            if not vlayer.isValid():
                self.error(f"❌ Could not load result layer: {vector_path}")
                return

            # Apply fill colour from _TASK_CONFIG
            rgba  = cfg.get("color", "0,0,255,128").split(",")
            r, g, b, a = (int(x.strip()) for x in rgba)
            sym = QgsFillSymbol.createSimple(
                {"color": f"{r},{g},{b},{a}", "outline_width": "0.3"}
            )
            vlayer.renderer().setSymbol(sym)
            vlayer.triggerRepaint()
            QgsProject.instance().addMapLayer(vlayer)
            n = vlayer.featureCount()
            self.chat(f"<b>✅ {label}</b> layer loaded ({n} polygon{'s' if n != 1 else ''}).")
        except Exception as e:
            self.error(f"❌ Failed to display result: {str(e)}")
        finally:
            if self.parent and hasattr(self.parent, "_set_processing"):
                self.parent._set_processing(False)

    def _on_spectral_samgeo_failed(self, err: str) -> None:
        self.error(f"❌ Spectral pipeline failed:\n{err}")
        if self.parent and hasattr(self.parent, "_set_processing"):
            self.parent._set_processing(False)

    # ── Main dispatcher ──────────────────────────────────────────────────────

    def execute_workflow(self, workflow_key: str, **kwargs) -> str | None:
        """Dispatch workflow by key (backward-compatible)."""
        if workflow_key == "water_seg":
            return self._execute_water_segmentation_workflow()
        elif workflow_key == "deepforest":
            return self.execute_deepforest()
        elif workflow_key == "moondream":
            q = kwargs.get("question", "Describe this satellite image in detail.")
            return self.execute_moondream(q)
        elif workflow_key == "spectral":
            idx = kwargs.get("index", "NDVI")
            return self.execute_spectral(idx)
        elif workflow_key == "download_satellite":
            bbox = kwargs.get("bbox", [])
            days = kwargs.get("days_back", 30)
            cloud = kwargs.get("cloud_max", 20)
            return self.execute_satellite_download(bbox, days, cloud)
        elif workflow_key == "samgeo":
            self.chat(
                "🎯 <b>SAM Geo</b>: For interactive point/box-based segmentation, "
                "please open the <b>SAMGeo tab</b> from the module grid.<br>"
                "<i>Automated non-interactive SAM is on the roadmap.</i>"
            )
            if self.parent and hasattr(self.parent, '_set_processing'):
                self.parent._set_processing(False)
            return None
        elif workflow_key in ("instance_seg", "semantic_seg"):
            label = "Instance Segmentation" if workflow_key == "instance_seg" else "Semantic Segmentation"
            self.chat(
                f"🏗 <b>{label}</b>: Please open the dedicated <b>{label} tab</b> "
                "from the module grid for full control.<br>"
                "<i>Automated inference within the AI chat is coming soon.</i>"
            )
            if self.parent and hasattr(self.parent, '_set_processing'):
                self.parent._set_processing(False)
            return None
        else:
            self.chat(f"⚠ Unknown workflow: <b>{workflow_key}</b>")
            if self.parent and hasattr(self.parent, '_set_processing'):
                self.parent._set_processing(False)
            return None


# -------------------------------------------------
# Global SAM Geo Model Manager
# -------------------------------------------------


class GlobalSamGeoManager:
    """Centralized SAM Geo model manager with singleton pattern."""
    
    _instance = None
    _lock = threading.Lock()
    _model = None
    _version = None
    _unload_callbacks = []

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register_unload_callback(cls, callback):
        """Register callback to unload SAM Geo from a specific window."""
        cls._unload_callbacks.append(callback)

    @classmethod
    def unload_all(cls) -> bool:
        """Unload SAM Geo from all windows globally."""
        for callback in cls._unload_callbacks:
            try:
                callback()
            except Exception as e:
                QgsMessageLog.logMessage(f"SAM Geo unload error: {str(e)}", "Geo Segment", Qgis.Warning)
        cls._model = None
        cls._version = None
        return True

    @classmethod
    def set_model(cls, model, version: str):
        """Set current model instance."""
        cls._model = model
        cls._version = version

    @classmethod
    def get_model(cls):
        """Get current model."""
        return cls._model

    @classmethod
    def get_version(cls):
        """Get current model version."""
        return cls._version


# -------------------------------------------------
# Worker thread – calls OpenRouter with full conversation history
# -------------------------------------------------


class AIWorker(QThread):
    """Sends the full conversation history to OpenRouter and returns the response."""

    action_ready  = pyqtSignal(dict)   # Parsed JSON action
    text_response = pyqtSignal(str)    # Plain-text conversational reply
    error         = pyqtSignal(str)    # Last error after all keys exhausted

    # Backward-compat alias
    result_ready = action_ready

    def __init__(self, messages: list, qgis_context: str = "") -> None:
        super().__init__()
        self.messages = messages          # Full conversation (without system)
        self.qgis_context = qgis_context

    def run(self) -> None:
        url        = "https://openrouter.ai/api/v1/chat/completions"
        last_error = "No valid API keys configured."

        tools_list   = ", ".join(MODULE_FRIENDLY.values())
        indices_list = ", ".join(SPECTRAL_INDICES.values())
        system_content = _SYSTEM_PROMPT.format(
            qgis_context=self.qgis_context or "No layers loaded",
            tools_list=tools_list,
            indices_list=indices_list,
        )
        full_messages = [{"role": "system", "content": system_content}] + self.messages

        for key in OPENROUTER_KEYS:
            if not key or not key.strip() or key.startswith("YOUR_KEY"):
                continue
            try:
                resp = requests.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {key.strip()}",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "model":    OPENROUTER_MODEL,
                        "messages": full_messages,
                        "temperature": 0.2,
                    },
                    timeout=30,
                )

                if resp.status_code == 401:
                    last_error = f"Invalid API key (401); trying next key…"
                    continue
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                    continue

                content = resp.json()["choices"][0]["message"]["content"].strip()

                # Try to extract JSON action from the response
                action = self._parse_action(content)
                if action:
                    self.action_ready.emit(action)
                    return

                # Plain-text response
                self.text_response.emit(content)
                return

            except (json.JSONDecodeError, KeyError, ValueError):
                last_error = "Could not parse API response."
            except requests.RequestException as exc:
                last_error = str(exc)

        self.error.emit(last_error)

    @staticmethod
    def _parse_action(content: str) -> dict | None:
        """Extract and validate a JSON action from LLM output."""
        # Try fenced code block first
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        raw = match.group(1).strip() if match else content.strip()

        # Find the first { ... } in the string
        if not raw.startswith("{"):
            brace_start = raw.find("{")
            if brace_start != -1:
                raw = raw[brace_start:]

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None

        # Accept new "action" key or old "workflow" key (backward compat)
        if "action" in data:
            return data
        if "workflow" in data and isinstance(data["workflow"], list):
            # Convert old format to new
            steps = data["workflow"]
            if steps:
                tool = steps[0].get("tool", "")
                index = steps[0].get("index", "NDVI")
                if tool == "spectral":
                    return {"action": "run_spectral", "index": index}
                action_map = {
                    "water_seg":    "run_water_seg",
                    "deepforest":   "run_deepforest",
                    "moondream":    "run_moondream",
                    "samgeo":       "run_samgeo",
                    "instance_seg": "run_instance_seg",
                    "semantic_seg": "run_semantic_seg",
                }
                mapped = action_map.get(tool, tool)
                return {"action": mapped}
        return None


# -------------------------------------------------
# Assistant Panel  (fully automated v2)
# -------------------------------------------------


class AIAssistantPanel(QWidget):
    """Multi-turn AI assistant with full workflow automation."""

    module_requested = pyqtSignal(str)   # Legacy compatibility signal

    _SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Conversation history (user/assistant messages – system is added by AIWorker)
        self._conversation: list[dict] = []
        # Cached Copernicus credentials for this session
        self._credentials: dict = {}
        # Keep worker references alive so Qt doesn't GC them mid-run
        self._active_workers: list = []
        self._spinner_idx = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_spinner)
        self._sat_worker = None   # current satellite download worker (for cancel)
        self._model_enabled: dict = {}   # {task_key: QCheckBox} — set by _build_method_panel
        self._use_samgeo_chk = None      # QCheckBox for SAMGeo refinement toggle
        self._orchestrator = WorkflowOrchestrator(
            chat_callback=self._chat_ai,
            error_callback=self._chat_error,
            parent=self,
        )
        self._build()
        self._welcome()

    # ── Welcome message ──────────────────────────────

    def _welcome(self) -> None:
        self._chat_ai(
            "<b>Welcome to Geo Segment AI Assistant!</b><br><br>"
            "I can automatically:<br>"
            "• 🛰 <b>Download satellite data</b> – give me coordinates or a city name<br>"
            "• 💧 <b>Detect water bodies</b> – AI model (OmniWaterMask) <i>or</i> Spectral (NDWI→SAMGeo)<br>"
            "• 🌲 <b>Detect trees</b> – AI model (DeepForest) <i>or</i> Spectral (NDVI→SAMGeo)<br>"
            "• 🏗 <b>Map buildings</b> – Spectral (NDBI→SAMGeo)<br>"
            "• 🔥 <b>Detect burn scars</b> – Spectral (NBR→SAMGeo)<br>"
            "• 📊 <b>Compute spectral indices</b> (NDVI, NDWI, SAVI, EVI…)<br>"
            "• 👁 <b>Describe images</b> – Moondream VLM<br><br>"
            "Use the <b>Analysis Methods</b> panel below to choose between "
            "AI Model or Spectral+SAMGeo for each task.<br><br>"
            "Try: <i>'Download Sentinel-2 for Chennai'</i> or <i>'Detect water bodies'</i>"
        )

    # ── QGIS Context ────────────────────────────────

    def _get_qgis_context(self) -> str:
        try:
            layers = QgsProject.instance().mapLayers()
            if not layers:
                return "No layers currently loaded in QGIS."
            lines = [f"Loaded layers ({len(layers)}):"]
            for layer in layers.values():
                ltype = "Raster" if isinstance(layer, QgsRasterLayer) else "Vector"
                try:
                    crs = layer.crs().authid() if layer.crs().isValid() else "No CRS"
                    ext = layer.extent()
                    if isinstance(layer, QgsRasterLayer):
                        lines.append(
                            f"  • {layer.name()} ({ltype}, {crs}): "
                            f"{layer.width()}×{layer.height()}px, {layer.bandCount()} bands"
                        )
                    else:
                        lines.append(
                            f"  • {layer.name()} ({ltype}, {crs}): "
                            f"{layer.featureCount()} features"
                        )
                except Exception as e:
                    lines.append(f"  • {layer.name()} – {str(e)}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error reading project: {str(e)}"

    # ── Analysis method selection panel ─────────────────────────────────────

    def _build_method_panel(self) -> QGroupBox:
        """
        Build the "Analysis Methods" group box.

        Each row shows a task (water, trees…) with:
          • checkbox  "Use AI Model" — when checked, the pre-trained ML model is used;
                                       when unchecked, the Spectral→SAMGeo pipeline runs.
          • dynamic description label that updates with the checkbox state.

        At the bottom: a "Use SAMGeo refinement" toggle for the spectral pipeline.
        """
        box = QGroupBox("Analysis Methods")
        box.setStyleSheet(
            "QGroupBox{font-size:10px;font-weight:bold;color:#ddd;"
            "border:1px solid #444;border-radius:4px;margin-top:6px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 2px;}"
        )
        vlay = QVBoxLayout(box)
        vlay.setSpacing(3)
        vlay.setContentsMargins(6, 12, 6, 6)

        hint = QLabel(
            "☑ <b>Use AI Model</b> = pretrained ML model  ·  "
            "☐ = Spectral index → SAMGeo segmentation"
        )
        hint.setStyleSheet("color:#888;font-size:9px;")
        hint.setWordWrap(True)
        vlay.addWidget(hint)

        # (checkbox_key, display_label, ai_desc, has_ai_model, task_config_key)
        model_defs = [
            ("water_seg",  "💧 Water Seg.",   "OmniWaterMask → water polygons",     True,  "water"),
            ("deepforest", "🌲 DeepForest",   "DeepForest → tree crown detections", True,  "trees"),
            ("moondream",  "👁 Moondream VLM","Moondream → image caption",          True,  None),
            ("urban",      "🏗 Urban/Build.", "NDBI → SAMGeo → building polygons",  False, "building"),
            ("vegetation", "🌿 Vegetation",   "SAVI → SAMGeo → cropland polygons",  False, "crop"),
            ("burn_scar",  "🔥 Burn Scars",   "NBR  → SAMGeo → burned area polys",  False, "burn"),
            ("snow_ice",   "❄ Snow/Ice",      "NDSI → SAMGeo → snow/ice polygons",  False, "snow"),
        ]

        grid = QGridLayout()
        grid.setSpacing(3)
        grid.setColumnStretch(2, 1)

        for col, header_txt in enumerate(["Task", "Use AI\nModel", "Active method"]):
            h = QLabel(f"<b>{header_txt}</b>")
            h.setStyleSheet("color:#aaa;font-size:9px;")
            grid.addWidget(h, 0, col)

        self._model_enabled = {}
        for row, (key, task_lbl, ai_desc, has_model, task_key) in enumerate(model_defs, 1):
            # Task name
            t_lbl = QLabel(task_lbl)
            t_lbl.setStyleSheet("font-size:10px;font-weight:bold;color:#eee;")
            grid.addWidget(t_lbl, row, 0)

            # "Use AI Model" checkbox
            chk = QCheckBox()
            chk.setChecked(has_model)
            chk.setEnabled(has_model)
            if not has_model:
                chk.setToolTip("No bundled AI model — Spectral+SAMGeo pipeline is used.")
            else:
                chk.setToolTip("Uncheck to use the Spectral→SAMGeo pipeline instead.")
            self._model_enabled[key] = chk
            grid.addWidget(chk, row, 1, Qt.AlignCenter)

            # Build spectral description from _TASK_CONFIG
            if task_key and task_key in _TASK_CONFIG:
                idx = _TASK_CONFIG[task_key]["index"]
                spec_desc = f"Spectral ({idx}) → SAMGeo → {_TASK_CONFIG[task_key]['label']}"
            else:
                spec_desc = "(no spectral alternative)"

            init_text = ai_desc if has_model else spec_desc
            init_style = "color:#7af;font-size:9px;" if has_model else "color:#fa7;font-size:9px;"
            d_lbl = QLabel(init_text)
            d_lbl.setStyleSheet(init_style)
            d_lbl.setWordWrap(True)
            grid.addWidget(d_lbl, row, 2)

            def _on_toggle(checked, dl=d_lbl, ai=ai_desc, sp=spec_desc):
                dl.setText(ai if checked else sp)
                dl.setStyleSheet(
                    "color:#7af;font-size:9px;" if checked else "color:#fa7;font-size:9px;"
                )

            chk.toggled.connect(_on_toggle)

        vlay.addLayout(grid)

        # SAMGeo refinement toggle
        sam_row = QHBoxLayout()
        self._use_samgeo_chk = QCheckBox("Use SAMGeo refinement in Spectral pipeline")
        self._use_samgeo_chk.setChecked(True)
        self._use_samgeo_chk.setStyleSheet("font-size:9px;color:#ccc;")
        self._use_samgeo_chk.setToolTip(
            "Checked:   spectral index image → SAMGeo automatic masks (more accurate)\n"
            "Unchecked: spectral index → Otsu threshold → polygonize (faster, no GPU needed)"
        )
        sam_row.addWidget(self._use_samgeo_chk)
        sam_row.addStretch()
        vlay.addLayout(sam_row)

        return box

    # ── UI builder ──────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(4, 4, 4, 4)

        # Header row
        hdr = QHBoxLayout()
        title = QLabel("🤖 Geo Segment AI Assistant")
        title.setFont(QFont("", 13, QFont.Bold))
        hdr.addWidget(title)
        hdr.addStretch()

        clear_btn = QPushButton("Clear Chat")
        clear_btn.setMaximumWidth(85)
        clear_btn.setStyleSheet("color:#aaa;font-size:10px;")
        clear_btn.clicked.connect(self._clear_chat)
        hdr.addWidget(clear_btn)
        root.addLayout(hdr)

        subtitle = QLabel(
            "Ask me anything — I'll run the right workflow automatically."
        )
        subtitle.setStyleSheet("color:#888;font-size:10px;")
        root.addWidget(subtitle)

        # Chat history
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setMinimumHeight(240)
        self.history.setStyleSheet(
            "QTextEdit { background:#1e1e1e; color:#ddd; border:1px solid #444; "
            "border-radius:4px; font-size:11px; }"
        )
        root.addWidget(self.history)

        # Indeterminate progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            "QProgressBar{border:none;background:#2a2a2a;}"
            "QProgressBar::chunk{background:#FF9800;}"
        )
        self._progress_bar.hide()
        root.addWidget(self._progress_bar)

        # Quick action examples
        box = QGroupBox("Quick Actions")
        grid = QGridLayout(box)
        grid.setSpacing(4)
        quick_actions = [
            ("💧 Detect Water",      "detect water bodies in this image"),
            ("🌲 Detect Trees",      "detect trees and forest canopy"),
            ("📊 Compute NDVI",      "compute NDVI spectral index"),
            ("📊 Compute NDWI",      "compute NDWI water index"),
            ("👁 Describe Image",    "describe what you see in this satellite image"),
            ("🛰 Download Satellite", "download satellite data for this area"),
        ]
        for i, (label, prompt) in enumerate(quick_actions):
            btn = QPushButton(label)
            btn.setStyleSheet("font-size:10px;padding:3px;")
            btn.clicked.connect(lambda _, p=prompt: self._submit(p))
            grid.addWidget(btn, i // 2, i % 2)
        root.addWidget(box)

        # Analysis method selection panel
        root.addWidget(self._build_method_panel())

        # Control row
        ctrl = QHBoxLayout()
        self._unload_btn = QPushButton("Unload SAM Geo")
        self._unload_btn.setMaximumWidth(110)
        self._unload_btn.setStyleSheet("font-size:10px;")
        self._unload_btn.clicked.connect(self._unload_samgeo_globally)
        ctrl.addWidget(self._unload_btn)
        ctrl.addStretch()

        # Status strip
        self._status_label = QLabel("● Ready")
        self._status_label.setStyleSheet(
            f"color:{_C['status_ok']};font-weight:bold;font-size:10px;"
        )
        ctrl.addWidget(self._status_label)
        root.addLayout(ctrl)

        # Input row
        row = QHBoxLayout()
        self.prompt = QLineEdit()
        self.prompt.setPlaceholderText(
            "e.g.  'download Sentinel-2 for New Delhi'  or  'detect water bodies'"
        )
        self.prompt.returnPressed.connect(lambda: self._submit(self.prompt.text()))
        row.addWidget(self.prompt)

        self._send_btn = QPushButton("Send")
        self._send_btn.setMinimumWidth(60)
        self._send_btn.setStyleSheet(
            "background:#1976D2;color:white;font-weight:bold;padding:4px 10px;"
        )
        self._send_btn.clicked.connect(lambda: self._submit(self.prompt.text()))
        row.addWidget(self._send_btn)
        root.addLayout(row)

    # ── Processing indicator ─────────────────────────

    def _set_processing(self, active: bool) -> None:
        self._send_btn.setEnabled(not active)
        if active:
            self._send_btn.setText("…")
            self._progress_bar.show()
            self._timer.start(100)
        else:
            self._timer.stop()
            self._spinner_idx = 0
            self._send_btn.setText("Send")
            self._progress_bar.hide()
            self._status_label.setText("● Ready")
            self._status_label.setStyleSheet(
                f"color:{_C['status_ok']};font-weight:bold;font-size:10px;"
            )

    def _tick_spinner(self) -> None:
        self._spinner_idx = (self._spinner_idx + 1) % len(self._SPINNER_FRAMES)
        frame = self._SPINNER_FRAMES[self._spinner_idx]
        self._status_label.setText(f"{frame}  Processing…")
        self._status_label.setStyleSheet(
            f"color:{_C['status_busy']};font-weight:bold;font-size:10px;"
        )

    # ── Chat helpers ─────────────────────────────────

    def _clear_chat(self) -> None:
        self.history.clear()
        self._conversation.clear()
        self._chat_ai("Chat cleared. How can I help you?")

    def _chat_user(self, text: str) -> None:
        self.history.append(
            f'<span style="color:{_C["user"]};font-weight:bold;">You:</span> '
            f'<span style="color:#ddd;">{text}</span>'
        )
        self.history.verticalScrollBar().setValue(self.history.verticalScrollBar().maximum())

    def _chat_ai(self, text: str) -> None:
        self.history.append(
            f'<span style="color:{_C["assistant"]};font-weight:bold;">Assistant:</span> '
            f'<span style="color:#ddd;">{text}</span>'
        )
        self.history.verticalScrollBar().setValue(self.history.verticalScrollBar().maximum())

    def _chat_error(self, text: str) -> None:
        self.history.append(
            f'<span style="color:{_C["error"]};font-weight:bold;">Error:</span> '
            f'<span style="color:#ffaaaa;">{text}</span>'
        )
        self.history.verticalScrollBar().setValue(self.history.verticalScrollBar().maximum())

    def _chat_system(self, text: str) -> None:
        self.history.append(
            f'<span style="color:{_C["status_busy"]};font-weight:bold;">System:</span> '
            f'<span style="color:#ffd580;">{text}</span>'
        )
        self.history.verticalScrollBar().setValue(self.history.verticalScrollBar().maximum())

    # ── SAM Geo unload ───────────────────────────────

    def _unload_samgeo_globally(self) -> None:
        try:
            mgr = GlobalSamGeoManager()
            if mgr.unload_all():
                self._chat_ai("✓ SAM Geo model unloaded from memory (all windows)")
            else:
                self._chat_error("No SAM Geo model currently loaded")
        except Exception as e:
            self._chat_error(f"Unload failed: {str(e)}")

    # ── Submission ───────────────────────────────────

    def _submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.prompt.clear()
        self._chat_user(text)
        self._set_processing(True)

        # Add to conversation history
        self._conversation.append({"role": "user", "content": text})

        # Fire AI worker with full conversation history
        qgis_context = self._get_qgis_context()
        self._worker = AIWorker(list(self._conversation), qgis_context)
        self._worker.action_ready.connect(self._handle_action)
        self._worker.text_response.connect(self._handle_text_response)
        self._worker.error.connect(lambda err: self._on_llm_error(err, text))
        self._worker.start()

    # ── LLM response handlers ────────────────────────

    def _handle_text_response(self, text: str) -> None:
        """Handle a conversational plain-text reply from the LLM."""
        self._set_processing(False)
        # Clean up common markdown artifacts
        text = re.sub(r"```\w*", "", text).replace("```", "").strip()
        self._chat_ai(text)
        # Add to conversation so LLM remembers what it said
        self._conversation.append({"role": "assistant", "content": text})

    def _handle_action(self, action: dict) -> None:
        """Dispatch a JSON action returned by the LLM."""
        action_name = action.get("action", "")
        summary = f"<b>→ Action: {action_name}</b>"
        self._chat_system(summary)
        # Track action in history as assistant turn
        self._conversation.append({"role": "assistant", "content": json.dumps(action)})
        self._dispatch_action(action)

    def _dispatch_action(self, action: dict) -> None:
        """Execute the appropriate workflow based on action name."""
        name = action.get("action", "")

        if name == "download_satellite":
            bbox = action.get("bbox", [])
            if not bbox or len(bbox) < 4:
                self._chat_error("❌ Cannot download: no valid bounding box in action.")
                self._set_processing(False)
                return
            days = action.get("days_back", 30)
            cloud = action.get("cloud_max", 20)
            result = self._orchestrator.execute_satellite_download(bbox, days, cloud)
            if result != "PENDING":
                self._set_processing(False)

        elif name == "run_water_seg":
            chk = self._model_enabled.get("water_seg")
            use_ai = chk is not None and chk.isChecked()
            if use_ai:
                result = self._orchestrator._execute_water_segmentation_workflow()
            else:
                result = self._orchestrator.execute_spectral_samgeo("water")
            if result != "PENDING":
                self._set_processing(False)

        elif name == "run_deepforest":
            chk = self._model_enabled.get("deepforest")
            use_ai = chk is not None and chk.isChecked()
            if use_ai:
                result = self._orchestrator.execute_deepforest()
            else:
                result = self._orchestrator.execute_spectral_samgeo("trees")
            if result != "PENDING":
                self._set_processing(False)

        elif name == "run_spectral":
            index = action.get("index", "NDVI").upper()
            result = self._orchestrator.execute_spectral(index)
            if result != "PENDING":
                self._set_processing(False)

        elif name == "run_moondream":
            question = action.get("question", "Describe this satellite image in detail.")
            result = self._orchestrator.execute_moondream(question)
            if result != "PENDING":
                self._set_processing(False)

        elif name in ("run_samgeo", "run_instance_seg", "run_semantic_seg"):
            result = self._orchestrator.execute_workflow(
                name.replace("run_", "")
            )
            if result != "PENDING":
                self._set_processing(False)

        elif name in (
            "run_urban", "run_building", "run_burn", "run_snow",
            "run_crop", "run_vegetation",
        ):
            # Pure spectral pipeline tasks (no bundled AI model)
            _spectral_task_map = {
                "run_urban":      ("urban",      "building"),
                "run_building":   ("urban",      "building"),
                "run_burn":       ("burn_scar",  "burn"),
                "run_snow":       ("snow_ice",   "snow"),
                "run_crop":       ("vegetation", "crop"),
                "run_vegetation": ("vegetation", "crop"),
            }
            chk_key, task_key = _spectral_task_map.get(name, ("urban", "building"))
            chk = self._model_enabled.get(chk_key)
            use_ai = chk is not None and chk.isChecked()
            if use_ai:
                self._chat_system(
                    f"⚠ No bundled AI model for <b>{name}</b> — "
                    "falling back to Spectral pipeline."
                )
            result = self._orchestrator.execute_spectral_samgeo(task_key)
            if result != "PENDING":
                self._set_processing(False)

        else:
            self._chat_error(f"Unknown action from AI: <b>{name}</b>")
            self._set_processing(False)

    # ── LLM error / keyword fallback ─────────────────

    def _on_llm_error(self, err: str, original_prompt: str) -> None:
        """LLM unavailable: fall back to keyword routing."""
        self._set_processing(False)
        key = route_prompt(original_prompt)
        if key:
            self._chat_system(
                f"LLM unavailable ({err[:60]}…). "
                f"Keyword routing → <b>{MODULE_FRIENDLY.get(key, key)}</b>"
            )
            self._set_processing(True)
            try:
                result = self._orchestrator.execute_workflow(key)
                if result != "PENDING":
                    self._set_processing(False)
            except Exception as e:
                self._chat_error(f"Workflow error: {str(e)}")
                self._set_processing(False)
        else:
            # Check if it looks like a coordinate / city request
            lower = original_prompt.lower()
            coord_hint = any(
                w in lower for w in
                ["coordinate", "bbox", "download", "sentinel", "satellite",
                 "city", "location", "area", "region"]
            )
            if coord_hint:
                self._chat_ai(
                    "I need the LLM to process this request. "
                    "Make sure you have a valid API key and internet connection.<br>"
                    "<i>Tip: Try again in a moment, or use the Sandbox tab to "
                    "manually enter coordinates and download data.</i>"
                )
            else:
                self._chat_ai(
                    f"<i>LLM unavailable ({err[:60]}).</i><br>"
                    "I can help with: <b>water detection</b>, <b>tree detection</b>, "
                    "<b>spectral indices</b>, <b>satellite download</b>, and <b>image description</b>.<br>"
                    "Try: 'detect water' or 'compute NDVI'."
                )

    # ── Backward-compatible handler ──────────────────

    def _handle_plan(self, plan: dict) -> None:
        """Backward-compatible: old LLM {'workflow': [...]} format."""
        action = AIWorker._parse_action(json.dumps(plan))
        if action:
            self._handle_action(action)
        else:
            self._chat_error("AI returned an unrecognised plan.")
            self._set_processing(False)

    def _log(self, msg: str) -> None:
        try:
            QgsMessageLog.logMessage(msg, "Geo Segment AI", Qgis.Info)
        except Exception:
            pass