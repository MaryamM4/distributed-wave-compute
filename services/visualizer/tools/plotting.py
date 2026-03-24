import numpy as np

# Note: Test viridis, plasma & inferno for color map
# Transparency: 1.0 (None) -> 0.0 (Fully transparent)

class SurfacePlot:
    def __init__(self, ax, grid_size, clr_map="viridis", transparency=0.9):
        self.ax = ax
        self.grid_size = grid_size
        self.clr_map = clr_map
        self.transp = transparency

        x = np.arange(grid_size)
        y = np.arange(grid_size)
        self.X, self.Y = np.meshgrid(x, y)

        self.surface = None

        self.ax.set_zlim(0, 1)
        self.ax.set_title("Wave Function")
    
    def update(self, Z):
        if self.surface:
            self.surface.remove()

        self.ax.set_zlim(0, Z.max() + 1e-6)
        self.surface = self.ax.plot_surface(self.X, self.Y, Z, cmap=self.clr_map, linewidth=0, antialiased=False, alpha=self.transp)