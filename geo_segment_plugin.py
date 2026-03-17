"""
Geo Segment Plugin for QGIS - Main Plugin Class

This module contains the main plugin class that manages the QGIS interface
integration, menu items, and toolbar buttons.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox


class GeoSegmentPlugin:
    """Geo Segment Plugin implementation class for QGIS."""

    def __init__(self, iface):
        """Constructor.

        Args:
            iface: An interface instance that provides the hook to QGIS.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = None
        self.toolbar = None

        # Main unified dock panel (lazy loaded)
        self._geo_segment_dock = None

        # Dependency installation state
        self._deps_available = False
        self._deps_install_worker = None
        self._deps_dock = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        checkable=False,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar.

        Args:
            icon_path: Path to the icon for this action.
            text: Text that appears in the menu for this action.
            callback: Function to be called when the action is triggered.
            enabled_flag: A flag indicating if the action should be enabled.
            add_to_menu: Flag indicating whether action should be added to menu.
            add_to_toolbar: Flag indicating whether action should be added to toolbar.
            status_tip: Optional text to show in status bar when mouse hovers over action.
            checkable: Whether the action is checkable (toggle).
            parent: Parent widget for the new action.

        Returns:
            The action that was created.
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.menu.addAction(action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Create menu
        self.menu = QMenu("&Geo Segment")
        self.iface.mainWindow().menuBar().addMenu(self.menu)

        # Create toolbar
        self.toolbar = QToolBar("Geo Segment Toolbar")
        self.toolbar.setObjectName("GeoSegmentToolbar")
        self.iface.addToolBar(self.toolbar)

        icon_base = os.path.join(self.plugin_dir, "icons")

        # Main panel icon – prefer the plugin's own icon.png
        panel_icon = os.path.join(icon_base, "icon.png")
        if not os.path.exists(panel_icon):
            panel_icon = ":/images/themes/default/mActionShowAllLayers.svg"

        # Single toolbar + menu entry: Open Geo Segment Panel
        self.open_panel_action = self.add_action(
            panel_icon,
            "Open Geo Segment Panel",
            self.toggle_geo_segment_panel,
            status_tip="Open / close the Geo Segment workspace panel",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # ---- Menu-only extras ----
        self.menu.addSeparator()

        gpu_icon = os.path.join(icon_base, "gpu.svg")
        if not os.path.exists(gpu_icon):
            gpu_icon = ":/images/themes/default/mActionRefresh.svg"

        self.add_action(
            gpu_icon,
            "Clear GPU Memory",
            self.clear_gpu_memory,
            add_to_toolbar=False,
            status_tip="Release GPU memory and clear CUDA cache",
            parent=self.iface.mainWindow(),
        )

        self.menu.addSeparator()

        about_icon = os.path.join(icon_base, "about.svg")
        if not os.path.exists(about_icon):
            about_icon = ":/images/themes/default/mActionHelpContents.svg"

        self.add_action(
            ":/images/themes/default/mActionRefresh.svg",
            "Check for Updates...",
            self.show_update_checker,
            add_to_toolbar=False,
            status_tip="Check for plugin updates from GitHub",
            parent=self.iface.mainWindow(),
        )

        self.add_action(
            about_icon,
            "About Geo Segment",
            self.show_about,
            add_to_toolbar=False,
            status_tip="About Geo Segment Plugin",
            parent=self.iface.mainWindow(),
        )

    def unload(self):
        """Remove the plugin menu item and icon from QGIS GUI."""
        # Stop install worker if running
        if self._deps_install_worker:
            if self._deps_install_worker.isRunning():
                try:
                    self._deps_install_worker.cancel()
                    self._deps_install_worker.terminate()
                    self._deps_install_worker.wait(5000)
                except RuntimeError:
                    pass
            self._deps_install_worker = None

        # Remove deps dock
        if self._deps_dock:
            self.iface.removeDockWidget(self._deps_dock)
            self._deps_dock.deleteLater()
            self._deps_dock = None

        # Remove main workspace dock
        if self._geo_segment_dock:
            self.iface.removeDockWidget(self._geo_segment_dock)
            self._geo_segment_dock.deleteLater()
            self._geo_segment_dock = None

        # Remove actions from menu
        for action in self.actions:
            self.iface.removePluginMenu("&Geo Segment", action)

        # Remove toolbar
        if self.toolbar:
            del self.toolbar

        # Remove menu
        if self.menu:
            self.menu.deleteLater()

    # ------------------------------------------------------------------
    # Dependency management
    # ------------------------------------------------------------------

    def _ensure_dependencies(self, action_name):
        """Check if dependencies are installed, show installer if not.

        Args:
            action_name: Descriptive name used when reopening the panel after
                installation completes.

        Returns:
            True if dependencies are available, False if installer was shown.
        """
        if self._deps_available:
            return True

        try:
            from .core.venv_manager import (
                ensure_venv_packages_available,
                get_venv_status,
            )

            is_ready, message = get_venv_status()
            if is_ready:
                ensure_venv_packages_available()
                self._deps_available = True
                return True
        except Exception:
            pass

        # Dependencies not available -- show the installer dock
        self._show_deps_install_dock()
        return False

    def _show_deps_install_dock(self):
        """Create and show the dependency installation dock widget."""
        if self._deps_dock is not None:
            self._deps_dock.show()
            self._deps_dock.raise_()
            return

        from .dialogs.deps_install_dialog import DepsInstallDockWidget

        self._deps_dock = DepsInstallDockWidget(self.iface.mainWindow())
        self._deps_dock.install_requested.connect(self._on_install_requested)
        self._deps_dock.cancel_requested.connect(self._on_cancel_install)

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self._deps_dock)
        self._deps_dock.show()
        self._deps_dock.raise_()

    def _on_install_requested(self):
        """Handle install button click from the deps dock."""
        if self._deps_install_worker and self._deps_install_worker.isRunning():
            return

        from .core.venv_manager import detect_nvidia_gpu
        from .workers.deps_install_worker import DepsInstallWorker

        has_gpu, _ = detect_nvidia_gpu()

        self._deps_install_worker = DepsInstallWorker(cuda_enabled=has_gpu)
        self._deps_install_worker.progress.connect(self._on_install_progress)
        self._deps_install_worker.finished.connect(self._on_install_finished)

        if self._deps_dock:
            self._deps_dock.show_progress_ui()

        self._deps_install_worker.start()

    def _on_install_progress(self, percent, message):
        """Handle progress updates from the install worker.

        Args:
            percent: Progress percentage (0-100).
            message: Status message.
        """
        if self._deps_dock:
            self._deps_dock.set_progress(percent, message)

    def _on_install_finished(self, success, message):
        """Handle installation completion.

        Args:
            success: Whether installation succeeded.
            message: Completion message.
        """
        if self._deps_dock:
            self._deps_dock.show_complete_ui(success, message)

        if success:
            self._deps_available = True

            # Ensure venv packages are on sys.path
            try:
                from .core.venv_manager import ensure_venv_packages_available

                ensure_venv_packages_available()
            except Exception:
                pass

            # Close the deps dock and open the main panel
            if self._deps_dock:
                self.iface.removeDockWidget(self._deps_dock)
                self._deps_dock.deleteLater()
                self._deps_dock = None

            self.toggle_geo_segment_panel()

    def _on_cancel_install(self):
        """Handle cancel button click during installation."""
        if self._deps_install_worker and self._deps_install_worker.isRunning():
            self._deps_install_worker.cancel()
        if self._deps_dock:
            self._deps_dock.show_install_ui()

    # ------------------------------------------------------------------
    # Main panel toggle
    # ------------------------------------------------------------------

    def toggle_geo_segment_panel(self):
        """Toggle the unified Geo Segment workspace dock panel."""
        if self._geo_segment_dock is None:
            try:
                from .dialogs.geo_segment_dock import GeoSegmentDockWidget

                self._geo_segment_dock = GeoSegmentDockWidget(
                    self.iface, self.iface.mainWindow()
                )
                self._geo_segment_dock.visibilityChanged.connect(
                    self._on_panel_visibility_changed
                )
                self.iface.addDockWidget(
                    Qt.RightDockWidgetArea, self._geo_segment_dock
                )
                self._geo_segment_dock.show()
                self._geo_segment_dock.raise_()
                return

            except Exception as exc:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Geo Segment panel:\n{exc}",
                )
                self.open_panel_action.setChecked(False)
                return

        if self._geo_segment_dock.isVisible():
            self._geo_segment_dock.hide()
        else:
            self._geo_segment_dock.show()
            self._geo_segment_dock.raise_()

    def _on_panel_visibility_changed(self, visible):
        """Keep the toolbar action checked state in sync."""
        self.open_panel_action.setChecked(visible)

    def clear_gpu_memory(self):
        """Clear accelerator memory and release model resources."""
        import gc

        cleared_items = []

        # Import torch early to use for cleanup
        torch = None
        torch_import_error = None
        try:
            import torch as _torch

            torch = _torch
        except (ImportError, OSError) as e:
            # PyTorch may be unavailable in QGIS (e.g. Windows DLL conflict) even if
            # it is installed in the plugin venv. Continue with best-effort model cleanup.
            torch_import_error = e

        # Release models held by the unified workspace panel
        module_docks = {}
        if self._geo_segment_dock is not None:
            module_docks = getattr(self._geo_segment_dock, "_module_docks", {})

        _model_attr_map = {
            "Moondream VLM": "moondream",
            "SAMGeo": "sam",
            "DeepForest": "deepforest",
        }

        for module_name, attr in _model_attr_map.items():
            dock = module_docks.get(module_name)
            if dock is None:
                continue
            try:
                model_obj = getattr(dock, attr, None)
                if model_obj is None:
                    continue
                if hasattr(model_obj, "close") and callable(model_obj.close):
                    try:
                        model_obj.close()
                    except Exception:
                        pass
                if hasattr(model_obj, "model") and model_obj.model is not None:
                    try:
                        model_obj.model.cpu()
                    except Exception:
                        pass
                    try:
                        for param in model_obj.model.parameters():
                            param.data = None
                            if param.grad is not None:
                                param.grad = None
                    except Exception:
                        pass
                    del model_obj.model
                    model_obj.model = None
                for a in list(vars(model_obj).keys()):
                    try:
                        setattr(model_obj, a, None)
                    except Exception:
                        pass
                setattr(dock, attr, None)
                del model_obj
                cleared_items.append(f"{module_name} model")
                # Update status labels where they exist
                for status_attr in ("model_status", "image_status"):
                    lbl = getattr(dock, status_attr, None)
                    if lbl is not None:
                        try:
                            lbl.setText("Model: Not loaded" if "model" in status_attr else "Image: Not set")
                            lbl.setStyleSheet("color: gray;")
                        except Exception:
                            pass
            except Exception:
                pass

        # Run garbage collection multiple times
        for _ in range(5):
            gc.collect()

        # Clear PyTorch accelerator cache (CUDA or Apple MPS)
        if torch is not None and torch.cuda.is_available():
            try:
                # Synchronize first
                torch.cuda.synchronize()
                # Empty cache
                torch.cuda.empty_cache()
                # IPC collect if available
                if hasattr(torch.cuda, "ipc_collect"):
                    torch.cuda.ipc_collect()
                # Run gc and empty cache again
                gc.collect()
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

                cleared_items.append("CUDA cache")

                # Get memory info for display
                allocated = torch.cuda.memory_allocated() / 1024**2
                reserved = torch.cuda.memory_reserved() / 1024**2
                memory_info = f"\n\nGPU Memory:\n  Allocated: {allocated:.1f} MB\n  Reserved: {reserved:.1f} MB"

                if allocated > 100:  # More than 100MB still allocated
                    memory_info += "\n\nNote: Some GPU memory may still be held by PyTorch's memory allocator. Restart QGIS to fully release all GPU memory."
            except Exception as e:
                memory_info = f"\n\nError clearing CUDA: {str(e)}"
        elif (
            torch is not None
            and hasattr(torch, "backends")
            and hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        ):
            try:
                if hasattr(torch, "mps") and hasattr(torch.mps, "synchronize"):
                    torch.mps.synchronize()

                mps_cache_cleared = False
                if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                    torch.mps.empty_cache()
                    mps_cache_cleared = True

                gc.collect()

                if hasattr(torch, "mps") and hasattr(torch.mps, "synchronize"):
                    torch.mps.synchronize()

                if mps_cache_cleared:
                    cleared_items.append("MPS cache")
                    memory_info = "\n\nApple Metal (MPS) cache cleared."
                else:
                    memory_info = (
                        "\n\nApple Metal (MPS) is available, but this PyTorch build "
                        "does not expose torch.mps.empty_cache(). Models were released "
                        "and garbage collection was run."
                    )
            except Exception as e:
                memory_info = f"\n\nError clearing MPS cache: {str(e)}"
        elif torch is None:
            if isinstance(torch_import_error, OSError):
                memory_info = (
                    "\n\nPyTorch is installed but not available in the QGIS process "
                    f"(likely DLL conflict): {torch_import_error}"
                    "\nSubprocess-backed models are still released by this action."
                )
            elif torch_import_error is not None:
                memory_info = (
                    "\n\nPyTorch is not available in this QGIS session: "
                    f"{torch_import_error}"
                )
            else:
                memory_info = "\n\nPyTorch not installed."
        else:
            memory_info = "\n\nNo CUDA or MPS accelerator available."

        if cleared_items:
            message = f"Cleared: {', '.join(cleared_items)}{memory_info}"
        else:
            message = f"No models loaded to clear.{memory_info}"

        self.iface.statusBarIface().showMessage("Accelerator memory cleared", 3000)
        QMessageBox.information(
            self.iface.mainWindow(),
            "Clear GPU Memory",
            message,
        )

    def show_about(self):
        """Display the about dialog."""
        # Read version from metadata.txt
        version = "Unknown"
        try:
            metadata_path = os.path.join(self.plugin_dir, "metadata.txt")
            with open(metadata_path, "r", encoding="utf-8") as f:
                import re

                content = f.read()
                version_match = re.search(r"^version=(.+)$", content, re.MULTILINE)
                if version_match:
                    version = version_match.group(1).strip()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Geo Segment Plugin",
                f"Could not read version from metadata.txt:\n{str(e)}",
            )

        about_text = f"""
<h2>Geo Segment Plugin for QGIS</h2>
<p>Version: {version}</p>
<p>Author: Qiusheng Wu</p>

<h3>Features:</h3>
<ul>
<li><b>Moondream Vision-Language Model:</b> AI-powered image captioning, querying, object detection, and point localization</li>
<li><b>Semantic Segmentation:</b> Train and run inference with deep learning models (U-Net, DeepLabV3+, FPN, etc.)</li>
<li><b>Instance Segmentation:</b> Train and run Mask R-CNN models for instance-level object detection and segmentation</li>
<li><b>SamGeo:</b> Segment Anything Model (SAM, SAM2, SAM3) for geospatial data with text, point, and box prompts</li>
<li><b>DeepForest:</b> Tree crown detection and forest analysis using pretrained deep learning models</li>
<li><b>Water Segmentation:</b> Water body detection from satellite/aerial imagery using OmniWaterMask</li>
<li><b>Spectral Indices:</b> Compute NDVI, NDWI, SAVI, EVI, NDSI, NBR, GCI, SIPI, FDI, Deforestation Index, and 9 RGB band composites from Sentinel-2 rasters</li>
</ul>

<h3>Links:</h3>
<ul>
<li><a href="https://github.com/opengeos/geo-segment">GitHub Repository</a></li>
<li><a href="https://github.com/opengeos/geo-segment/issues">Report Issues</a></li>
</ul>

<p>Licensed under MIT License</p>
"""
        QMessageBox.about(
            self.iface.mainWindow(),
            "About Geo Segment Plugin",
            about_text,
        )

    def show_update_checker(self):
        """Display the update checker dialog."""
        try:
            from .dialogs.update_checker import UpdateCheckerDialog
        except ImportError as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to import update checker dialog:\n{str(e)}",
            )
            return

        try:
            dialog = UpdateCheckerDialog(self.plugin_dir, self.iface.mainWindow())
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to open update checker:\n{str(e)}",
            )
