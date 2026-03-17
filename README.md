<style>
table {
  border-collapse: collapse;
  border: 1px solid #999;
  width: 100%;
  margin: 15px 0;
}
table th {
  border: 1px solid #999;
  padding: 8px;
  text-align: left;
  font-weight: bold;
}
table td {
  border: 1px solid #999;
  padding: 8px;
}
</style>

# Geo Segment QGIS Plugin — Professional Documentation

[![QGIS](https://img.shields.io/badge/QGIS-3.28+-blue.svg)](https://qgis.org)
[![Python](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)](https://pytorch.org/)
[![Version](https://img.shields.io/badge/Version-1.0.4-orange.svg)](#deployment)

**Enterprise-Grade AI/ML Geospatial Analysis Platform for QGIS** — Deploy foundation models, deep learning, and advanced remote sensing workflows with production-ready confidence.

---

## Table of Contents

- [Overview](#overview)
- [Core Features](#core-features)
- [Additional Capabilities](#additional-capabilities)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start Guide](#quick-start-guide)
- [Technical Reference](#technical-reference)
- [Learning Resources](#learning-resources)

---

## Overview

Geo Segment integrates cutting-edge AI/ML models and foundation model architectures into QGIS for production-scale geospatial analysis. Designed for researchers, remote sensing specialists, and GIS professionals, the plugin enables zero-code access to:

### Capabilities Matrix

| **Capability**               | **Technology**                   | **Input**              | **Output**               | **Sensors**               |
| ---------------------------- | -------------------------------- | ---------------------- | ------------------------ | ------------------------- |
| **Interactive Segmentation** | SAM1/SAM2/SAM3 foundation models | Text/points/boxes      | Vector/raster polygons   | Any optical               |
| **Spectral Analysis**        | 20+ radiometric indices          | Multi-spectral raster  | Index layers (GeoTIFF)   | Sentinel-2, Landsat, NAIP |
| **Object Detection**         | DeepForest, YOLO, Mask R-CNN     | Raster imagery         | Confidence-scored boxes  | Aerial/satellite          |
| **Semantic Segmentation**    | U-Net, DeepLabV3+, FPN, LinkNet  | Raster + training data | Per-pixel classification | Any optical               |
| **Water Detection**          | OmniWaterMask                    | Multi-spectral raster  | Binary/probability masks | Multi-sensor              |
| **Vision-Language**          | Moondream VLM                    | RGB imagery            | Descriptive text, Q&A    | Any optical               |

### Platform Architecture

- **Backend**: Python 3.9+ with PyTorch 2.0+ deep learning framework
- **Geospatial**: GDAL 3.4+ for raster/vector I/O; GeoPandas for vector operations
- **Acceleration**: GPU support (NVIDIA CUDA 11.8+, AMD ROCm, Apple Silicon MPS)
- **Deployment**: QGIS plugin architecture with lazy-loaded modules

---

## Core Features

### ⭐ SAMGeo — Foundation Model Segmentation

**Segment Anything Models (SAM1/SAM2/SAM3)** for zero-shot, prompt-driven interactive segmentation at production scale.

#### Segmentation Modes & Performance

| **Mode**           | **Input Method**            | **Use Case**                           | **Performance**       | **Accuracy**          |
| ------------------ | --------------------------- | -------------------------------------- | --------------------- | --------------------- |
| **Text Query**     | Natural language prompts    | Named entity (buildings, trees, water) | 0.5–2s per image      | High generalization   |
| **Point-Based**    | Interactive map clicks      | Feature extraction & manual QC         | <500ms feedback       | User-guided           |
| **Bounding Box**   | Vector polygon/rectangle    | Region-of-interest processing          | ~1s per ROI           | Sub-region refinement |
| **Batch (Vector)** | GeoPackage/Shapefile points | Systematic surveys, mass detection     | Parallelized 4+ cores | High throughput       |

#### Technical Specifications

**Model Architecture**:

- **SAM1** (ViT-B/L/H encoders): General-purpose zero-shot segmentation
- **SAM2** (Video-enabled): Temporal consistency tracking
- **SAM3** (Latest): Enhanced accuracy + optimized inference
- **Auto-Selection**: Automatic model choice based on available VRAM

**Processing Pipeline**:

- GPU-accelerated inference (CUDA/ROCm/MPS)
- Adaptive patch tiling for large scenes (>4GB rasters)
- Mask post-processing: morphological regularization, boundary refinement, hole-filling
- Multi-instance deduplication via Intersection-over-Union (IoU) thresholding

**Output Formats & Attributes**:

| **Format**     | **Geometry**       | **Attributes**                        | **Use Case**                        |
| -------------- | ------------------ | ------------------------------------- | ----------------------------------- |
| **GeoTIFF**    | Raster pixel masks | Confidence (0–255)                    | Machine learning pipeline input     |
| **GeoPackage** | Polygon features   | polygon_id, confidence_score, area_m² | Spatial database, attribute queries |
| **Shapefile**  | Polygon features   | Legacy format fields                  | ArcGIS compatibility                |
| **GeoJSON**    | Feature collection | Web-compatible JSON                   | Leaflet/Mapbox integration          |

**Quality Control Options**:

- Morphological filtering (median, closing, opening)
- Boundary smoothing (Ramer-Douglas-Peucker algorithm)
- Minimum area thresholding (user-defined in pixels²)
- Adjacency-based smart mask merging

---

### ⭐ Spectral Indices Calculator

**Radiometric Analysis Engine** — Compute 20+ spectral indices with automatic band detection and production-ready output.

#### Index Categories & Formulas

| **Category**         | **Indices**                | **Formula Basis**               | **Remote Sensing Application**                          |
| -------------------- | -------------------------- | ------------------------------- | ------------------------------------------------------- |
| **Vegetation**       | NDVI, SAVI, EVI, NDRE, GCI | (NIR − Red) / (NIR + Red)       | Crop phenology, chlorophyll estimation, biomass         |
| **Water & Moisture** | NDWI, MNDWI, NDMI          | (Green − NIR) / (Green + NIR)   | Aquatic vegetation, soil moisture, flood mapping        |
| **Urban & Built-up** | NDBI, NDIII, UI            | (SWIR − NIR) / (SWIR + NIR)     | Building density, urban heat island, impervious surface |
| **Burn & Fire**      | NBR, dNBR, BAI             | (NIR − SWIR) / (NIR + SWIR)     | Post-fire damage severity, burn extent mapping          |
| **Snow & Ice**       | NDSI, NDLIS                | (Green − SWIR) / (Green + SWIR) | Snow cover extent, glacier delineation                  |

#### Technical Processing

**Band Auto-Detection**:

- Sentinel-2 MSI: Bands 2/3/4/8/11 (10m, 20m, 60m resolutions)
- Landsat 8/9 OLI-2: Bands 2/3/4/5/6/7 (30m native)
- NAIP: RGB + NIR (1m typical)
- Custom imagery: Manual band assignment interface

**Radiometric Processing**:

- Radiometric scaling: Digital Number → Top-of-Atmosphere (TOA) reflectance
- Atmospheric correction workflows (optional Fmask, LEDAPS)
- NoData/invalid pixel masking with semantic preservation
- Missing band interpolation (for hyperspectral)

**Computational Features**:

- Multi-threaded processing (GDAL/NumPy backends)
- Tiling for memory efficiency (scenes >1GB)
- Floating-point output with double-precision intermediate calculations
- Batch processing: compute multiple indices in single pass

**Output Specifications**:

| **Type**           | **Format**            | **Data Type** | **Range**                 | **Application**                        |
| ------------------ | --------------------- | ------------- | ------------------------- | -------------------------------------- |
| **Index Layer**    | GeoTIFF (single-band) | Float32       | -1.0 to +1.0 (normalized) | Spatial analysis, visualization        |
| **Index Stack**    | GeoTIFF (multi-band)  | Float32       | Per-index normalized      | Time-series analysis, machine learning |
| **Confidence Map** | GeoTIFF (uint8)       | 0–255         | Per-pixel reliability     | Uncertainty quantification             |
| **RGB Composite**  | GeoTIFF (uint8)       | 0–255         | 3-band visualization      | Quick interpretation, presentations    |

**Visualization & Customization**:

- Per-index color ramps (viridis, plasma, RdYlGn, tableau colormap library)
- Dynamic value stretching: percentile-based (2%-98%) normalization
- Automated classification breaks (Jenks natural breaks, quantile)
- Cloud-Optimized GeoTIFF (COG) export for cloud analytics

---

## Additional Capabilities

### 🤖 Vision-Language Model Analysis

**Moondream VLM** — Multimodal foundation model for scene understanding and natural language reasoning.

**Capabilities**:

- **Scene Captioning**: Automated description generation (landscape type, features detected)
- **Visual Q&A**: Answer spatial questions with bounding box localization ("How many buildings within 500m water?")
- **Object Localization**: Confidence-scored bounding boxes from text queries
- **Multi-Modal Fusion**: Integration with raster metadata (sensor specs, acquisition date)

**Technical Details**:

- Vision transformer backbone + language model decoder
- Batch processing support for time-series imagery
- GPU acceleration (inference time: 2–5s per 512×512 image)

---

### 🔍 Object Detection & Instance Segmentation

#### DeepForest — Pre-Trained Ecological Detection

**Architecture**: ResNet backbone with region proposal network (RPN)

| **Component**          | **Specification**                         | **Details**                           |
| ---------------------- | ----------------------------------------- | ------------------------------------- |
| **Pre-Trained Models** | Tree crowns (WeEcology), birds, livestock | Domain-specific fine-tuned weights    |
| **Input**              | Single large scene or tiled image         | Sliding window + edge-blend stitching |
| **Inference**          | Parallel GPU processing                   | Batch tiling (e.g., 512×512 patches)  |
| **Output**             | Bounding boxes + confidence               | GeoPackage with geometry + attributes |
| **Post-Processing**    | NMS (Non-Maximum Suppression)             | IoU threshold for overlap filtering   |

**Fine-Tuning**: Transfer learning on custom ecological data (COCO/YOLO format)

---

#### Mask R-CNN — Instance-Level Segmentation

| **Component**           | **Specification**                             | **Implementation**                      |
| ----------------------- | --------------------------------------------- | --------------------------------------- |
| **Architecture**        | Mask R-CNN with Feature Pyramid Network (FPN) | Two-stage detector + segmentation head  |
| **Backbones**           | ResNet-50/101, MobileNet, EfficientNet        | Selectable for speed/accuracy trade-off |
| **Multi-Class Support** | Up to 256 object classes                      | Per-instance classification + masks     |
| **Output**              | Per-instance polygons                         | GeoPackage with class + confidence      |
| **Training**            | PyTorch (MMDetection backend)                 | Input: COCO or PASCAL VOC format        |

**Custom Training Workflow**:

1. Prepare labeled dataset (images + instance polygons)
2. Convert to COCO format
3. Configure architecture & hyperparameters
4. Train with early stopping & validation tracking
5. Export model for inference

---

### 🎨 Semantic Segmentation

**Pixel-Level Dense Classification** — Assign class labels to every pixel in raster imagery.

**Supported Architectures**:

| **Architecture** | **Encoder**      | **Best For**                    | **Inference Speed**    |
| ---------------- | ---------------- | ------------------------------- | ---------------------- |
| **U-Net**        | ResNet-34/50     | General-purpose segmentation    | Fast (real-time)       |
| **DeepLabV3+**   | Xception, ResNet | Multi-scale feature aggregation | Moderate               |
| **FPN**          | ResNet-50/101    | Multi-scale object detection    | Fast                   |
| **LinkNet**      | ResNet-18        | Lightweight, edge deployment    | Very fast              |
| **PSPNet**       | ResNet-50        | Pyramid scene parsing, context  | Slower (high accuracy) |

**Transfer Learning Pipeline**:

- ImageNet pre-trained encoders (ResNet, EfficientNet, DenseNet, VGG)
- Fine-tuning with early stopping to prevent overfitting
- Data augmentation: geometric (rotation, flip) + radiometric (brightness, contrast)
- Class weighting for imbalanced datasets

**Output & Uncertainty**:

- Per-pixel class probabilities (floating-point confidence)
- Argmax classification raster (single class per pixel)
- Bayesian uncertainty via MC-Dropout (optional)
- Thresholding maps for low-confidence regions

**Training Data Formats**: COCO, PASCAL VOC, or simple directory structure (images/ + masks/)

---

### 💧 Water Segmentation

**OmniWaterMask** — Automated water surface detection and classification.

**Capabilities**:

- Multi-sensor compatibility (Sentinel-2, Landsat 8/9, NAIP, drone/aerial)
- Inundation vs. permanent water classification
- Clouded/shadowed pixel masking with confidence scores
- Edge refinement (coastlines, river channels) via morphological operations
- Sub-pixel accuracy with active contour refinement (optional)

**Output Types**:

- Binary masks (water/non-water)
- Probability maps (0–1 continuous confidence)
- Water index rasters (NDWI-derived)

---

## System Requirements

### Runtime Environment

| **Component** | **Minimum** | **Recommended** | **Notes**                                |
| ------------- | ----------- | --------------- | ---------------------------------------- |
| **QGIS**      | 3.28.0+     | 3.34+ LTS       | Python 3 plugin environment required     |
| **Python**    | 3.9         | 3.11–3.12       | Shipped with QGIS; not standalone        |
| **RAM**       | 8 GB        | 16+ GB          | Per concurrent analysis task             |
| **Storage**   | 20 GB       | 50+ GB          | All models + dependencies + working data |

### GPU Acceleration (Optional, Highly Recommended)

| **Platform**          | **Driver**    | **Version** | **VRAM**     | **Performance Gain**     |
| --------------------- | ------------- | ----------- | ------------ | ------------------------ |
| **NVIDIA CUDA**       | nvidia-driver | 11.8+       | 6–8 GB       | 10–50× inference speedup |
| **AMD ROCm**          | amd-driver    | 5.0+        | 8 GB         | 8–40× acceleration       |
| **Apple Silicon MPS** | Built-in      | M1/M2/M3/M4 | 16 GB shared | 5–15× speedup            |

### Core Dependencies (Auto-Installed)

```
PyTorch 2.0+              (Deep learning framework)
GDAL 3.4+                 (Geospatial I/O)
GeoPandas 0.12+           (Vector processing)
scikit-image, OpenCV      (Image processing)
segmentation-models-pytorch (Pre-built model zoo)
NumPy, SciPy, pandas      (Scientific computing)
```

---

## Installation

### Deployment Steps

#### Step 1: Acquire the Plugin

**Via Git**:

```bash
git clone https://github.com/opengeoai/geo_segment.git
cd geo_segment/qgis_plugin
```

**Via Download**: Download and extract the source archive from the repository.

---

#### Step 2: Deploy to QGIS Plugin Directory

**Windows (PowerShell as Administrator)**:

```powershell
$PluginPath = "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins"
Copy-Item -Path "geo_segment" -Destination $PluginPath -Recurse -Force
Write-Host "Plugin installed to: $PluginPath"
```

**Linux (Bash)**:

```bash
PLUGIN_PATH="$HOME/.local/share/QGIS/QGIS3/profiles/default/python/plugins"
mkdir -p "$PLUGIN_PATH"
cp -r geo_segment "$PLUGIN_PATH/"
echo "Plugin installed to: $PLUGIN_PATH"
```

**macOS (Bash)**:

```bash
PLUGIN_PATH="$HOME/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins"
mkdir -p "$PLUGIN_PATH"
cp -r geo_segment "$PLUGIN_PATH/"
echo "Plugin installed to: $PLUGIN_PATH"
```

---

#### Step 3: Enable Plugin in QGIS

1. Launch QGIS
2. Navigate: **Plugins** → **Manage and Install Plugins...**
3. Search: `Geo Segment`
4. **Check box** to enable
5. Click **OK** and restart QGIS

---

#### Step 4: Install AI Models & Dependencies

On first launch:

1. Open **Plugins** → **Geo Segment** → **Geo Segment Dock**
2. Navigate: **Geo Segment** → **Dependency Manager**
3. Select required components:
    - ✓ **Essential**: SAMGeo models, Spectral tools
    - ☐ **Optional**: DeepForest, Moondream, Semantic segmentation models
4. Click **Install All** (downloads ~10–20GB depending on selection)
5. Monitor progress bar; total time: 30–120 minutes

**Verification Checklist**:

- ✓ Plugin appears in Plugins menu
- ✓ Toolbar icons load without errors
- ✓ **Geo Segment** → **About** shows version 1.0.4+
- ✓ Test: Load sample Sentinel-2 GeoTIFF and run Spectral Indices

---

## Quick Start Guide

### Workflow Pattern: Data → Analysis → Export

#### Phase 1: Load Multi-Spectral Imagery

**Supported Formats**:

- Sentinel-2 L2A (Multi-Spectral, .jp2 bands)
- Landsat 8/9 OLI-2 (\_B\*.TIF archive)
- NAIP 4-band imagery
- Aerial orthorectified GeoTIFF
- Hyperspectral (ENVI/HDF5 format)

**Load in QGIS**:

```
Layer → Add Layer → Add Raster Layer... → Select file
```

**Verify Metadata**:

- Layer → Properties → Information tab
- Confirm: CRS defined, band count matches sensor, georeferencing valid

---

#### Phase 2: Spectral Analysis (Recommended Entry Point)

**Step-by-Step**:

1. **Open Module**: Plugins → Geo Segment Dock → **Spectral Indices** tile (green)

2. **Configure Input**:
    - Select raster layer from dropdown
    - Click **Auto-Detect Bands** (recognizes Sentinel-2, Landsat automatically)
    - If not detected: manually assign Red, Green, NIR, SWIR bands

3. **Select Indices**:
    - ☑ NDVI (vegetation vigor)
    - ☑ NDWI (water extent)
    - ☑ NDBI (urbanization)
    - ☑ NBR (fire severity)

4. **Processing Options**:
    - ☐ Add to Map (auto-display result layer)
    - ☐ Export as GeoTIFF (save to disk)
    - Color Ramp: Select from dropdown (viridis, plasma, etc.)

5. **Execute**:
    - Click **Calculate**
    - Progress bar shows tiling progress
    - Result layer automatically added to canvas

**Output**: Single/multi-band GeoTIFF with values 0.0–1.0 (normalized)

---

#### Phase 3: Interactive Segmentation (SAMGeo)

**Text-Based Query**:

1. Open **Geo Segment Dock** → **SAMGeo** tile (orange)
2. Input raster visible on map canvas
3. Type query: `"trees"`, `"buildings"`, `"water"`, or custom class
4. Confidence Threshold: 0.5 (adjust sensitivity)
5. Click **Segment** (real-time preview on map)
6. Post-Processing:
    - Min Area: Filter small polygons (threshold in pixels²)
    - Simplify: Boundary smoothing tolerance
7. Click **Export** → Choose format (GeoPackage recommended)

**Point-Based Interactive**:

1. Click map to place foreground points (green markers)
2. Right-click to place background points (red markers)
3. Click **Predict** (mask updates in real-time)
4. Refine with additional points as needed

**Output Specification**:

- **Format**: GeoPackage (recommended) / Shapefile / GeoJSON
- **Attributes**: polygon_id, confidence_score, area_m²
- **CRS**: Matches input raster

---

#### Phase 4: Export & Integration

**Save Layers**:

```
Right-click layer → Export As...
```

**Format Selection**:

- **Raster**: GeoTIFF, COG (Cloud-Optimized), ENVI
- **Vector**: GeoPackage (full support), Shapefile (legacy), GeoJSON (web)

**Attribute Queries** (for exported vectors):

```
Right-click layer → Open Attribute Table
Select Features Using an Expression: "confidence_score" > 0.8 AND "area_m2" > 1000
```

---

### Common Analysis Scenarios

#### Scenario A: Water Body Mapping (Wetland Survey)

| Step | Tool             | Parameters                     | Output                         |
| ---- | ---------------- | ------------------------------ | ------------------------------ |
| 1    | Load             | Sentinel-2 L2A product         | Multi-band raster              |
| 2    | Spectral Indices | NDWI index computation         | Index 0–1 layer                |
| 3    | SAMGeo           | Query: "water" + threshold 0.6 | Water polygon layer            |
| 4    | Export           | Format: GeoPackage             | Database-ready vector          |
| 5    | Analysis         | Attribute table query          | Filtered water bodies >5000 m² |

#### Scenario B: Building Footprint Extraction (Urban Planning)

| Step | Tool         | Parameters                            | Output                  |
| ---- | ------------ | ------------------------------------- | ----------------------- |
| 1    | Load         | Aerial NAIP or drone orthomosaic      | RGB + NIR raster        |
| 2    | SAMGeo       | Query: "buildings" + confidence 0.7   | Building polygon layer  |
| 3    | Post-Process | Simplify 2m tolerance, merge adjacent | Cleaned footprints      |
| 4    | Export       | Format: Shapefile                     | ArcGIS-compatible layer |
| 5    | QC           | Visual verification + area statistics | Validation report       |

#### Scenario C: Crop Health Monitoring (Precision Agriculture)

| Step | Tool             | Parameters                              | Output                              |
| ---- | ---------------- | --------------------------------------- | ----------------------------------- |
| 1    | Load             | Multi-temporal Sentinel-2 stack         | Time-series rasters                 |
| 2    | Spectral Indices | NDVI + SAVI multi-temporal              | Vegetation trend maps               |
| 3    | Classification   | Threshold NDVI: [0.4–0.7] = stress zone | Stress classification               |
| 4    | Export           | Format: GeoTIFF                         | Raster for farm management software |
| 5    | Action           | Generate prescription maps              | Variable-rate input planning        |

---

## Technical Reference

### Spectral Index Formulas

| **Index** | **Formula**                                      | **Range**    | **Interpretation**                   |
| --------- | ------------------------------------------------ | ------------ | ------------------------------------ |
| **NDVI**  | (NIR − Red) / (NIR + Red)                        | –1.0 to +1.0 | Vegetation vigor; >0.6 = dense cover |
| **NDWI**  | (Green − NIR) / (Green + NIR)                    | –1.0 to +1.0 | Water extent; >0.3 = open water      |
| **NDBI**  | (SWIR − NIR) / (SWIR + NIR)                      | –1.0 to +1.0 | Urban/built-up; >0.1 = urban areas   |
| **NBR**   | (NIR − SWIR) / (NIR + SWIR)                      | –1.0 to +1.0 | Burn severity; <–0.1 = severe burn   |
| **SAVI**  | ((NIR − Red) / (NIR + Red + L)) × (1 + L)        | –1.0 to +1.0 | Vegetation in arid zones (L=0.5)     |
| **EVI**   | 2.5 × ((NIR − Red) / (NIR + 6Red − 7.5Blue + 1)) | –1.0 to +1.0 | Enhanced vegetation index            |
| **NDSI**  | (Green − SWIR) / (Green + SWIR)                  | –1.0 to +1.0 | Snow cover; >0.4 = snow present      |

### Output Format Specifications

**GeoTIFF Raster**:

- Geotransform: Affine transformation preserved
- CRS: Matches input imagery
- Data Type: Float32 (indices), UInt8 (classification)
- Compression: LZW lossless (default)
- No-Data Value: –9999 (indices), 0 (classification)

**GeoPackage Vector**:

- Geometry Type: Polygon (WKT format)
- Attributes: polygon_id (integer), confidence_score (0–1), area_m² (float)
- CRS: Matches input raster
- Indexed: Spatial index on geometry column

**Shapefile Vector**:

- Geometry Type: Polygon
- Attributes: ID, CONFIDENCE (0–255 scale), AREA (m²)
- Projection: Matches input (PRJ file)
- Encoding: UTF-8

---

## Learning Resources

### Official Documentation

**Core Plugin**:

- [Geo Segment User Manual](https://opengeoai.org/docs)
- [API Reference & Developer Guide](https://opengeoai.org/api)
- [GitHub Repository & Issues](https://github.com/opengeoai/geo_segment)

**QGIS & GIS**:

- [QGIS Documentation](https://docs.qgis.org/latest/en/)
- [QGIS Python API (PyQGIS)](https://docs.qgis.org/latest/en/docs/pyqgis_developer_guide/)

---

### Foundation Model & ML Theory

**SAM & Foundation Models**:

- [Segment Anything Model (Meta AI)](https://segment-anything.com/)
- [SAM2 Video Segmentation Research](https://ai.meta.com/segment-anything-2/)

**Remote Sensing Theory**:

- [USGS Spectral Index Database](https://www.usgs.gov/programs/VHP)
- [Sentinel-2 Band Reference](https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-2-msi/msi-geometric-processing)
- [Landsat 8/9 Collection 2 Guide](https://www.usgs.gov/landsat-missions/landsat-collection-2-system)

**Deep Learning for Geospatial**:

- [Segmentation Models PyTorch](https://github.com/qubvel-org/segmentation_models.pytorch)
- [MMDetection Framework](https://github.com/open-mmlab/mmdetection)
- [PyTorch Lightning Training](https://lightning.ai/)

---

### Data & Benchmarks

**Free Satellite Data**:

- [Copernicus Sentinel-2 Browser](https://browser.dataspace.copernicus.eu/) — L2A orthorectified imagery
- [USGS Earth Explorer](https://earthexplorer.usgs.gov/) — Landsat, MODIS archive
- [OpenTopography](https://cloud.sdsc.edu/v1/AUTH_openimages/) — DEMs, LiDAR, hyperspectral
- [Planet NICFI Program](https://www.planet.com/nicfi/) — 3m monthly (tropics)

**Benchmark Datasets**:

- [OpenEarthMap](https://github.com/zhu-xlab/open-earth-map) — Large-scale land-cover labels
- [TreeSatAI Dataset](https://github.com/zhu-xlab/TreeSatAI) — Tree crown detection
- [SEN12MS](http://madm.web.unc.edu/sentinel/) — Sentinel-1/2 paired scenes

---

### Geospatial Libraries

**Raster/Vector I/O**:

- [GDAL/OGR](https://gdal.org/) — Geospatial data format library
- [Rasterio](https://rasterio.readthedocs.io/) — Pythonic raster interface
- [GeoPandas](https://geopandas.org/) — Vector GIS in Python
- [Xarray](https://xarray.dev/) — N-dimensional array processing

**Visualization**:

- [Folium](https://python-visualization.github.io/folium/) — Interactive web maps
- [Leaflet.js](https://leafletjs.com/) — Web mapping library

---

### Community & Support

**Q&A Forums**:

- [GIS Stack Exchange](https://gis.stackexchange.com/) — Tag: `qgis`, `remote-sensing`, `spectral-indices`
- [GitHub Discussions](https://github.com/opengeoai/geo_segment/discussions)
- [Stack Overflow](https://stackoverflow.com/) — Tags: `qgis`, `gdal`, `geopandas`, `pytorch`

**Research Community**:

- [EarthVision Workshop (CVPR)](https://www.grss-ieee.org/) — Annual ML for geospatial conference
- [AGU Fall Meeting](https://www.agu.org/Fall-Meeting) — Largest geophysics conference
- [IGARSS (IEEE Geoscience & Remote Sensing)](https://igarss2024.org/) — Remote sensing symposium

---

## Troubleshooting

### Common Issues

**Plugin Not Loading**:

- Verify QGIS version ≥3.28
- Check plugin directory permissions
- Review QGIS Python console for import errors: **Plugins** → **Python Console**

**Out of Memory During Processing**:

- Reduce raster tile size in settings
- Enable GPU acceleration (CUDA/ROCm available)
- Process large scenes in smaller tiles

**Incorrect Band Detection**:

- Verify raster metadata (Layer → Properties → Information)
- Manually assign bands if auto-detection fails
- Ensure bands are in correct order (Red, Green, NIR, SWIR)

**Slow Inference**:

- Check GPU memory availability (`nvidia-smi` or `rocm-smi`)
- Reduce raster resolution or tile size
- Consider downsampling input before processing
