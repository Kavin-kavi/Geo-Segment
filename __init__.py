"""
Geo Segment Plugin for QGIS

This plugin provides AI-powered geospatial analysis tools including:
- Moondream vision-language model for image analysis
- Semantic segmentation model training and inference
- Spectral indices and band composites (NDVI, NDWI, NDSI, NBR, EVI, etc.)
"""

from .geo_segment_plugin import GeoSegmentPlugin


def classFactory(iface):
    """Load GeoSegmentPlugin class from file geo_segment_plugin.

    Args:
        iface: A QGIS interface instance.

    Returns:
        GeoSegmentPlugin: The plugin instance.
    """
    return GeoSegmentPlugin(iface)
