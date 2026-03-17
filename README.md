# Geo Segment QGIS Plugin

[![QGIS](https://img.shields.io/badge/QGIS-3.28+-blue.svg)](https://qgis.org)[![Python](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)[![Version](https://img.shields.io/badge/version-1.0.4-orange.svg)](#)

**Professional AI-powered geospatial analysis in QGIS** — Apply state-of-the-art deep learning models for segmentation, object detection, and image classification directly from your GIS environment.

---

## Overview

Geo Segment is a comprehensive QGIS plugin that integrates cutting-edge AI/ML models for geospatial analysis. Designed for researchers, analysts, and GIS professionals, it provides production-ready tools for:

-   **Semantic & Instance Segmentation** — Segment buildings, water, vegetation, and custom classes
-   **Object Detection** — Tree detection, bird detection, livestock counting with customizable models
-   **Vision-Language AI** — Natural language queries on satellite and aerial imagery (Moondream)
-   **Spectral Analysis** — 20+ vegetation, water, and burn indices with single-click calculation
-   **Automated Water Detection** — OmniWaterMask for rapid water body identification
-   **Custom Model Training** — Train and deploy segmentation models on your data

All powered by intuitive graphical interfaces requiring no coding.

---

## Core Features

### ⭐ SAMGeo — Interactive Object Segmentation

**Segment Anything Models (SAM1/SAM2/SAM3)** for flexible, interactive object detection and segmentation.

-   **Text-Based**: Segment objects by name ("trees", "buildings", "water")
-   **Interactive Map Drawing**: Click points (foreground/background) or draw bounding boxes directly on the map
-   **Point-Based Batch**: Load point locations from vector files (GeoPackage, Shapefile, GeoJSON)
-   **Multi-Scale Processing**: Automatically handles objects of varying sizes
-   **Advanced Output**:
    -   GeoTIFF rasters with georeferencing
    -   GeoPackage polygons with properties
    -   Shapefile export for legacy systems
    -   GeoJSON for web integration
-   **Smart Filtering**: Regularization, boundary smoothing, hole filling, and smart mask merging

**Best For**: Rapid feature extraction, interactive mapping, exploratory analysis, custom object classes

---

### ⭐ Spectral Indices Calculator

**Compute 20+ indices in a single click** with automatic band detection for major satellite sensors.

Category

Indices

Typical Use

**Vegetation**

NDVI, SAVI, EVI, GCI, SIPI

Crop monitoring, forest health

**Water**

NDWI

Water body detection, wetland mapping

**Snow/Ice**

NDSI

Snow cover mapping, glacier monitoring

**Burn & Fire**

NBR, FDI, Deforestation Index

Fire damage assessment, deforestation tracking

**RGB Composites**

9 pre-configured visualizations

Quick visual interpretation

**Features**:

-   Auto-detect bands for Sentinel-2, Landsat, NAIP
-   Manual band assignment for custom imagery
-   Hyperspectral support
-   Custom color ramps and value stretching
-   Batch processing of multiple indices
-   Output as standard GeoTIFF for integration

**Best For**: Environmental monitoring, agricultural analysis, change detection, rapid assessment

---

## Additional Capabilities

### 🤖 Vision & Language Models

**Moondream VLM** — Natural language interaction with satellite imagery

-   Caption generation for imagery description
-   Visual question-answering ("How many trees?", "Where is water?")
-   Object detection with bounding boxes
-   Spatial reasoning and relationships

### 🔍 Object Detection

**DeepForest** — Ecological object detection with pre-trained models

-   Tree crown detection (general-purpose)
-   Bird, livestock, and habitat detection
-   Specialized models for specific ecosystems
-   Large-tile processing with patch-based inference
-   Confidence filtering and NMS

**Mask R-CNN** — Train custom instance segmentation models

-   Per-instance detection and segmentation
-   Multi-class object handling
-   Custom model training on your data

### 🎨 Semantic Segmentation

**Semantic Segmentation** — Pixel-level classification

-   Multi-architecture support: U-Net, DeepLabV3+, FPN, LinkNet, PSPNet
-   Transfer learning with ResNet, EfficientNet, DenseNet backbones
-   Real-time inference and probability maps
-   Custom model training for any class of interest

**Water Segmentation (OmniWaterMask)**

-   Automated water body detection
-   Multi-sensor compatibility (Sentinel-2, Landsat, NAIP, aerial)
-   Vector and raster output options

---

## Installation

### Step 1: Download the Plugin

Clone or download the `geo_segment` folder from the repository.

### Step 2: Install to QGIS

Navigate to your QGIS plugins directory and paste the `geo_segment` folder:

**Windows:**

```
C:Users[YourUsername]AppDataRoamingQGISQGIS3profilesdefaultpythonplugins
```

**Linux:**

```
~/.local/share/QGIS/QGIS3/profiles/default/python/plugins
```

**macOS:**

```
~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins
```

### Step 3: Enable in QGIS

1.  Open QGIS
2.  Go to **Plugins** → **Manage and Install Plugins...**
3.  Search for **"Geo Segment"**
4.  Check the box to enable
5.  Restart QGIS

### Step 4: Install Dependencies

When you first open the plugin:

1.  Navigate to **Plugins** → **Geo Segment**
2.  Click **Install Dependencies** on the main interface
3.  Select the AI models you need
4.  Wait for downloads to complete (~5-10 GB depending on model selection)

---

## System Requirements

-   **QGIS**: 3.28 or later
-   **Python**: 3.9 or later (bundled with QGIS)
-   **RAM**: Minimum 8GB (16GB recommended)
-   **GPU** (optional): NVIDIA CUDA 11.8+, AMD ROCm, or Apple Silicon MPS for acceleration
-   **Disk Space**: ~20GB for all models and dependencies

---

## Quick Start

### 1. Load Satellite Imagery

Add a raster layer to QGIS (Sentinel-2, Landsat, NAIP, aerial imagery, etc.)

### 2. Choose Your Analysis

#### **Water Detection**

-   Go to **Geo Segment** → **Water Segmentation**
-   Select your raster layer
-   Choose band configuration
-   Click **Run Analysis**

#### **Tree Detection (DeepForest)**

-   Go to **Geo Segment** → **DeepForest**
-   Load model (weecology/deepforest-tree or alternative)
-   Select input layer/file
-   Choose mode (Single Image or Large Tile)
-   Configure parameters (confidence, batch size)
-   Click **Run Prediction**

#### **Semantic Segmentation**

-   Go to **Geo Segment** → **Semantic Segmentation**
-   Provide labeled training data (images + masks) OR use pre-trained model
-   Select architecture and parameters
-   Run **Training** or **Inference**

#### **Natural Language Queries (Moondream)**

-   Go to **Geo Segment** → **AI Assistant**
-   Load image
-   Type your question or command
-   View results on map

#### **Spectral Indices**

-   Go to **Geo Segment** → **Spectral Indices**
-   Select multi-band raster
-   Assign bands (auto-detect for Sentinel/Landsat)
-   Select indices to compute
-   Adjust color ramps
-   Click **Calculate**

### 3. Save & Export Results

-   Automatically added to map when "Add to map" is checked
-   Supports: GeoPackage, Shapefile, GeoJSON, GeoTIFF, Raster formats
-   Training data export: PASCAL VOC, COCO, YOLO formats

---

## Learning Resources

### Documentation

-   [GeoAI Official Docs](https://opengeoai.org)
-   [QGIS Python API](https://docs.qgis.org/latest/en/docs/pyqgis_developer_guide/)
-   [PyTorch Segmentation Models](https://github.com/qubvel-org/segmentation_models.pytorch)
-   [DeepForest Docs](https://deepforest.readthedocs.io)
-   [SAM (Segment Anything) Docs](https://segment-anything.com)

### Sample Datasets

-   [Copernicus Sentinel-2 Browser](https://browser.dataspace.copernicus.eu/)
-   [USGS Earth Explorer](https://earthexplorer.usgs.gov/)
-   [OpenTopography](https://cloud.sdsc.edu/v1/AUTH_openimages/)

---
