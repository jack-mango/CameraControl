"""Individual image plot widget with matplotlib integration"""

import logging
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, 
    QComboBox, QCheckBox, QLineEdit, QPushButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ..constants import COLORS

logger = logging.getLogger(__name__)

# TODO: Should clear the accumulated images buffer when we reach shots_per_parameter

# TODO: Add function builder, I think perhaps text input would be best?

# TODO: Remove colorbars next to images, also make images take up more of the widget.

# TODO: Flip the vertical in images so lower left is 0, 0.

# TODO: Add parula colormap


class ImagePlot(QWidget):
    """Individual plot widget for displaying camera images with configurable processing"""
    def __init__(self, width_px=400, height_px=300, dpi=100, buffer_size=10, plot_number=None, parent=None):
        super().__init__(parent)
        
        self.setObjectName("image-plot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # Plot settings as attributes
        self.plot_number = plot_number
        self.colormap = 'viridis'
        self.display_mode = 'current'
        self.processing_function = lambda x: x[0]
        self.image_data = None
        self.accumulated_images = []
        self.buffer_size = buffer_size
        self.cmin = None
        self.cmax = None
        
        # Convert pixels to inches
        width_inches = width_px / dpi
        height_inches = height_px / dpi
        
        # Create matplotlib figure with transparent background
        self.figure = Figure(figsize=(width_inches, height_inches), dpi=dpi, facecolor='none')
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111, facecolor='none')
        
        # Style the axes
        self.ax.spines['bottom'].set_color(COLORS['text_light'])
        self.ax.spines['top'].set_color(COLORS['text_light'])
        self.ax.spines['left'].set_color(COLORS['text_light'])
        self.ax.spines['right'].set_color(COLORS['text_light'])
        self.ax.tick_params(axis='x', colors=COLORS['text_light'], labelsize=8)
        self.ax.tick_params(axis='y', colors=COLORS['text_light'], labelsize=8)
        self.ax.xaxis.label.set_color(COLORS['text_light'])
        self.ax.yaxis.label.set_color(COLORS['text_light'])
        self.ax.xaxis.label.set_fontsize(8)
        self.ax.yaxis.label.set_fontsize(8)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create settings panel (hidden by default)
        self.settings_panel = self.create_settings_panel()
        self.settings_panel.hide()
        
        # Add canvas and settings panel (only one visible at a time)
        main_layout.addWidget(self.canvas)
        main_layout.addWidget(self.settings_panel)
        
        # Settings button - positioned absolutely over the canvas
        self.settings_btn = QPushButton("⋯", self)
        self.settings_btn.setObjectName("settings-button")
        self.settings_btn.setFixedSize(30, 30)
        self.settings_btn.clicked.connect(self.toggle_settings)
        self.settings_btn.raise_()
        
        # Store the image artist for faster updates
        self.im = None

    def resizeEvent(self, event):
        """Reposition the settings button when widget is resized"""
        super().resizeEvent(event)
        self.settings_btn.move(self.width() - self.settings_btn.width() - 5, 5)
    
    def create_settings_panel(self):
        """Create the settings configuration panel"""
        panel = QWidget()
        panel.setObjectName("settings-panel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title at the top
        title_label = QLabel(self.get_plot_title())
        title_label.setObjectName("settings-title")
        layout.addWidget(title_label)
        
        # Form layout for settings
        form_layout = QFormLayout()
        
        # Colormap selection
        self.colormap_combo = QComboBox()
        self.colormap_combo.setMinimumWidth(150)
        colormaps = ['viridis', 'plasma', 'inferno', 'magma', 'gray', 'hot', 'cool', 'jet']
        self.colormap_combo.addItems(colormaps)
        self.colormap_combo.setCurrentText(self.colormap)
        self.colormap_combo.currentTextChanged.connect(self.on_colormap_changed)
        form_layout.addRow("Colormap:", self.colormap_combo)
        
        # Display mode (current vs average)
        self.mode_combo = QComboBox()
        self.mode_combo.setMinimumWidth(150)
        self.mode_combo.addItems(['current', 'average'])
        self.mode_combo.setCurrentText(self.display_mode)
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        form_layout.addRow("Averaging Mode:", self.mode_combo)
        
        # Processing function selection
        self.function_combo = QComboBox()
        self.function_combo.setMinimumWidth(150)
        self.function_combo.addItems(['None', 'Log Scale', 'Square Root', 'Absolute Value'])
        self.function_combo.currentTextChanged.connect(self.on_function_changed)
        form_layout.addRow("Function:", self.function_combo)
        
        # Auto scale checkbox
        self.auto_scale_checkbox = QCheckBox("Auto Scale")
        self.auto_scale_checkbox.setChecked(True)
        self.auto_scale_checkbox.stateChanged.connect(self.on_auto_scale_changed)
        form_layout.addRow("", self.auto_scale_checkbox)
        
        # Color scale min
        self.cmin_edit = QLineEdit("")
        self.cmin_edit.setPlaceholderText("Auto")
        self.cmin_edit.setValidator(QDoubleValidator())
        self.cmin_edit.textChanged.connect(self.on_cmin_changed)
        self.cmin_edit.setEnabled(False)
        form_layout.addRow("Color Min:", self.cmin_edit)
        
        # Color scale max
        self.cmax_edit = QLineEdit("")
        self.cmax_edit.setPlaceholderText("Auto")
        self.cmax_edit.setValidator(QDoubleValidator())
        self.cmax_edit.textChanged.connect(self.on_cmax_changed)
        self.cmax_edit.setEnabled(False)
        form_layout.addRow("Color Max:", self.cmax_edit)
        
        # Set from current button
        set_from_current_btn = QPushButton("Set from current image")
        set_from_current_btn.clicked.connect(self.set_scale_from_current)
        form_layout.addRow("", set_from_current_btn)
        
        layout.addLayout(form_layout)
        
        # Add stretch before close button
        layout.addStretch()
        
        # Close button at bottom
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.toggle_settings)
        layout.addWidget(close_btn)
        
        return panel
    
    def get_plot_title(self):
        """Get the title for this plot"""
        if self.plot_number is not None:
            return f"Plot {self.plot_number} Config"
        else:
            return "Plot Config"
    
    def toggle_settings(self):
        """Toggle visibility of settings panel"""
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
            self.canvas.show()
            self.settings_btn.show()
        else:
            self.canvas.hide()
            self.settings_btn.hide()
            self.settings_panel.show()
    
    def on_colormap_changed(self, colormap):
        """Handle colormap change"""
        self.set_colormap(colormap)
    
    def on_mode_changed(self, mode):
        """Handle display mode change"""
        self.set_display_mode(mode)
    
    def on_auto_scale_changed(self, state):
        """Handle auto-scale checkbox change"""
        is_checked = state == Qt.Checked
        # Enable/disable manual color scale inputs
        self.cmin_edit.setEnabled(not is_checked)
        self.cmax_edit.setEnabled(not is_checked)
        
        if is_checked:
            # Clear manual values when switching to auto
            self.cmin = None
            self.cmax = None
            self.cmin_edit.clear()
            self.cmax_edit.clear()
            self.update_display()
    
    def on_cmin_changed(self, text):
        """Handle color min change"""
        if text:
            try:
                self.cmin = float(text)
                self.update_display()
            except ValueError:
                pass
        else:
            if not self.auto_scale_checkbox.isChecked():
                self.cmin = None
                self.update_display()
    
    def on_function_changed(self, function_name):
        """Handle processing function change"""
        if function_name == 'None':
            self.processing_function = None
        elif function_name == 'Log Scale':
            self.processing_function = lambda x: np.log1p(x)
        elif function_name == 'Square Root':
            self.processing_function = lambda x: np.sqrt(x)
        elif function_name == 'Absolute Value':
            self.processing_function = lambda x: np.abs(x)
        else:
            self.processing_function = None
        
        self.update_display()
    
    def on_cmax_changed(self, text):
        """Handle color max change"""
        if text:
            try:
                self.cmax = float(text)
                self.update_display()
            except ValueError:
                pass
        else:
            if not self.auto_scale_checkbox.isChecked():
                self.cmax = None
                self.update_display()
    
    def set_scale_from_current(self):
        """Set color limits from the current displayed image (not auto-updating)"""
        if self.image_data is None:
            logger.warning("No image data available")
            return
        
        # Get the data that's currently being displayed
        display_data = self.get_current_display_data()
        if display_data is None:
            return
        
        # Set min/max from data
        self.cmin = float(np.min(display_data))
        self.cmax = float(np.max(display_data))
        
        # Uncheck auto-scale
        self.auto_scale_checkbox.setChecked(False)
        
        # Update the text fields
        self.cmin_edit.setText(f"{self.cmin:.2f}")
        self.cmax_edit.setText(f"{self.cmax:.2f}")
                
        # Update display
        self.update_display()
    
    def get_current_display_data(self):
        """Get the data that should be displayed based on current settings"""
        if self.image_data is None:
            return None
        
        # Choose which data to display based on mode
        if self.display_mode == 'current':
            # Use only the most recent image from buffer
            display_data = self.image_data
        elif self.display_mode == 'average':
            # Average all images in the buffer
            if len(self.accumulated_images) == 0:
                return None
            display_data = np.mean(self.accumulated_images, axis=0)
        
        # Apply processing function if set
        if self.processing_function is not None:
            try:
                display_data = self.processing_function(display_data)
            except Exception as e:
                logger.warning(f"Error applying processing function: {e}")
                return None
        
        return display_data
    
    def set_colormap(self, colormap):
        """Set the colormap for the plot"""
        self.colormap = colormap
        if self.im is not None:
            self.im.set_cmap(colormap)
            self.canvas.draw()
    
    def set_display_mode(self, mode):
        """Set display mode: 'current' or 'average'"""
        if mode not in ['current', 'average']:
            raise ValueError("mode must be 'current' or 'average'")
        self.display_mode = mode
        self.update_display()
    
    def set_processing_function(self, func):
        """Set a function to process the image data before display"""
        self.processing_function = func
        self.update_display()
    
    def set_buffer_size(self, buffer_size):
        """Set the buffer size (called from MainWindow or controller)"""
        self.buffer_size = buffer_size
        # Trim accumulated images if buffer got smaller
        if len(self.accumulated_images) > buffer_size:
            self.accumulated_images = self.accumulated_images[-buffer_size:]
    
    def update_image(self, image_data):
        """Update with new image data from camera"""
        self.image_data = image_data
        
        # Add to accumulated images for averaging
        self.accumulated_images.append(image_data)
        if len(self.accumulated_images) > self.buffer_size:
            self.accumulated_images.pop(0)
        
        self.update_display()
    
    def update_display(self):
        """Update the display based on current settings"""
        display_data = self.get_current_display_data()
        if display_data is None:
            return
        
        # Determine color limits
        if self.auto_scale_checkbox.isChecked() or (self.cmin is None and self.cmax is None):
            # Auto-scale: use min/max from current data
            vmin = np.min(display_data)
            vmax = np.max(display_data)
        else:
            # Use manual limits (if set)
            vmin = self.cmin if self.cmin is not None else np.min(display_data)
            vmax = self.cmax if self.cmax is not None else np.max(display_data)
        
        # Update plot
        if self.im is None:
            # First time plotting
            self.im = self.ax.imshow(display_data)#, cmap=self.colormap, aspect='auto', vmin=vmin, vmax=vmax)
            self.figure.colorbar(self.im, ax=self.ax)
        else:
            # Update existing image
            self.im.set_data(display_data)
            self.im.set_clim(vmin=vmin, vmax=vmax)
        
        self.canvas.draw()
    
    def clear(self):
        """Clear the plot and accumulated data"""
        self.image_data = None
        self.accumulated_images = []
        self.ax.clear()
        self.im = None
        self.canvas.draw()
