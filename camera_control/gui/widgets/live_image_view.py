"""Live image view widget with dynamic grid layout"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton
)
from PyQt5.QtCore import Qt

from ..constants import DEFAULT_PADDING
from .image_plot import ImagePlot


class LiveImageViewWidget(QWidget):
    """Widget containing a dynamic grid of camera plots"""
    def __init__(self, n_rows=1, n_cols=3, parent=None):
        super().__init__(parent)
        
        self.setObjectName("live-image-view")
        
        # Store initial dimensions as base size per plot
        self.base_plot_width = 512
        self.base_plot_height = 512
        
        self.n_rows = n_rows
        self.n_cols = n_cols

        self.plots = []

        # Don't set maximum height - let it grow/shrink with grid
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Main layout - use VBox to stack title, plots and buttons
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING)

        # Add title label at the top
        title_label = QLabel("Live Image View")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("live-image-view-title")
        main_layout.addWidget(title_label)

        # Container for plots and column buttons
        plot_container = QWidget()
        plot_container_layout = QHBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.setSpacing(0)

        # Grid layout for plots
        plot_grid_widget = QWidget()
        self.layout = QGridLayout(plot_grid_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        
        plot_container_layout.addWidget(plot_grid_widget)

        # Column control buttons (right side)
        col_button_layout = QVBoxLayout()
        col_button_layout.setContentsMargins(DEFAULT_PADDING, 0, 0, 0)
        col_button_layout.setSpacing(3 * DEFAULT_PADDING)
        
        row_button_height = 32
        col_button_width = 32
        
        # Calculate vertical centering for column buttons
        col_button_height = 50
        
        col_button_layout.addStretch()
        
        self.add_col_btn = QPushButton("+")
        self.add_col_btn.setFixedSize(col_button_width, col_button_height)
        self.add_col_btn.clicked.connect(self.add_column)
        
        col_button_layout.addWidget(self.add_col_btn)
        
        self.remove_col_btn = QPushButton("-")
        self.remove_col_btn.setFixedSize(col_button_width, col_button_height)
        self.remove_col_btn.clicked.connect(self.remove_column)
        
        col_button_layout.addWidget(self.remove_col_btn)
        
        col_button_layout.addStretch()
        
        plot_container_layout.addLayout(col_button_layout)

        main_layout.addWidget(plot_container)

        # Row control buttons (bottom) - centered horizontally
        row_button_layout = QHBoxLayout()
        row_button_layout.setContentsMargins(0, DEFAULT_PADDING, 0, 0)
        row_button_layout.setSpacing(DEFAULT_PADDING)
        
        row_button_width = 50
        row_button_height = 32
        
        row_button_layout.addStretch()
        
        self.add_row_btn = QPushButton("+")
        self.add_row_btn.setFixedSize(row_button_width, row_button_height)
        self.add_row_btn.clicked.connect(self.add_row)
        
        self.remove_row_btn = QPushButton("-")
        self.remove_row_btn.setFixedSize(row_button_width, row_button_height)
        self.remove_row_btn.clicked.connect(self.remove_row)
        
        row_button_layout.addWidget(self.add_row_btn)
        row_button_layout.addWidget(self.remove_row_btn)
        
        row_button_layout.addStretch()

        main_layout.addLayout(row_button_layout)

        self.initialize_plots()

    def add_row(self):
        """Add a new row of plots"""
        self.n_rows += 1
        self.rebuild_grid()

    def remove_row(self):
        """Remove a row of plots"""
        if self.n_rows > 1:
            self.n_rows -= 1
            self.rebuild_grid()

    def add_column(self):
        """Add a new column of plots"""
        self.n_cols += 1
        self.rebuild_grid()

    def remove_column(self):
        """Remove a column of plots"""
        if self.n_cols > 1:
            self.n_cols -= 1
            self.rebuild_grid()

    def rebuild_grid(self):
        """Rebuild the grid layout preserving existing plots where possible"""
        # Save existing plots in a flat list
        old_plots = []
        for row in self.plots:
            old_plots.extend(row)
        
        # Remove all widgets from layout (but don't delete them yet)
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
        
        # Use fixed plot sizes
        plot_width = self.base_plot_width
        plot_height = self.base_plot_height
        
        # Rebuild the 2D plots array
        self.plots = []
        plot_index = 0
        
        for r in range(self.n_rows):
            row_plots = []
            for c in range(self.n_cols):
                if plot_index < len(old_plots):
                    # Reuse existing plot
                    plot = old_plots[plot_index]
                    plot.setParent(self)  # Re-parent to this widget
                else:
                    # Create new plot
                    plot = ImagePlot(
                        width_px=plot_width, 
                        height_px=plot_height, 
                        buffer_size=20,
                        plot_number=plot_index + 1
                    )
                
                # Set fixed size to maintain aspect ratio
                plot.setFixedSize(plot_width, plot_height)
                self.layout.addWidget(plot, r, c)
                row_plots.append(plot)
                plot_index += 1
            self.plots.append(row_plots)
        
        # Delete any excess plots that are no longer needed
        for i in range(plot_index, len(old_plots)):
            old_plots[i].deleteLater()

    def clear_layout(self):
        """Remove all widgets from the layout"""
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Clear the plots list
        self.plots = []

    def initialize_plots(self):
        """Initialize plots and store them in a 2d list for easy access"""
        # Use fixed plot size regardless of grid dimensions
        plot_width = self.base_plot_width
        plot_height = self.base_plot_height
        
        self.plots = []
        
        plot_counter = 1
        
        for r in range(self.n_rows):
            row_plots = []
            for c in range(self.n_cols):
                plot = ImagePlot(
                    width_px=plot_width, 
                    height_px=plot_height, 
                    buffer_size=20,
                    plot_number=plot_counter
                )
                # Set fixed size to maintain aspect ratio
                plot.setFixedSize(plot_width, plot_height)
                self.layout.addWidget(plot, r, c)
                row_plots.append(plot)
                plot_counter += 1
            self.plots.append(row_plots)

    def get_plot_width_px(self):
        """Get width of individual plots in pixels"""
        return self.base_plot_width
    
    def get_plot_height_px(self):
        """Get height of individual plots in pixels"""
        return self.base_plot_height

    def get_plot(self, row, col):
        """Get a specific plot by row and column"""
        if 0 <= row < self.n_rows and 0 <= col < self.n_cols:
            return self.plots[row][col]
        return None

    def update_image_plots(self, images):
        """Update all plots with all camera images
        
        Each plot receives all images and can display them differently based on its settings.
        
        Args:
            images: 3D numpy array of shape (n_images, height, width) or list of 2D arrays
        """
        if images is None:
            return
        
        # Give all images to every plot
        # Each plot will handle the images according to its own settings
        for row in self.plots:
            for plot in row:
                plot.update_image(images)
