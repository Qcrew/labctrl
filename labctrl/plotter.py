""" """

import numpy as np
from PySide6 import QtWidgets
import pyqtgraph as pg


class PlottingError(Exception):
    """ """


class LivePlotter(QtWidgets.QMainWindow):
    """A pyqtgraph-based plotter for real-time plotting on a 2D Cartesian grid."""

    def __init__(
        self,
        title: str = None,
        xlabel: str = None,
        xunits: str = None,
        ylabel: str = None,
        yunits: str = None,
    ) -> None:
        """ """
        super().__init__()
        self.setWindowTitle("LivePlotter")

        self.widget = pg.PlotWidget()
        self.setCentralWidget(self.widget)

        self.plt = self.widget.getPlotItem()
        self.plt.setLabels(title=title, bottom=(xlabel, xunits), left=(ylabel, yunits))
        self.plt.showGrid(x=True, y=True, alpha=0.1)
        self.plt.setMenuEnabled(False)
        self.legend = self.plt.addLegend()


class LiveDataPlotter(LivePlotter):
    """for line and scatter plots, with fits and error bars"""

    def __init__(
        self,
        scatter: bool = True,
        legend: list[str] = None,  # labels to identify multiple y traces
        show_fit: bool = False,
        show_err: bool = False,
        **kwargs,
    ) -> None:
        """ """
        super().__init__(**kwargs)

        # set plot hooks for more direct live plot updating
        code = f"{int(show_fit)}{int(show_err)}{int(legend is None)}"
        plot_hook_dict = {
            "000": self._update_many_plot,
            "001": self._update_one_plot,
            "010": self._update_many_plot_err,
            "011": self._update_one_plot_err,
            "100": self._update_many_plot_fit,
            "101": self._update_one_plot_fit,
            "110": self._update_many_plot_fit_err,
            "111": self._update_one_plot_fit_err,
        }
        self._hook = plot_hook_dict[code]

        legend = ["y"] if legend is None else legend  # to initialize plots in one loop
        num_plots = len(legend) * 2 if show_fit else len(legend)
        self.plots, self.errorbars = [], []
        for idx, name in enumerate(legend):  # initialize plots and error bars
            intcolor = (idx, num_plots)
            if scatter:
                plot = pg.ScatterPlotItem(name=name, brush=intcolor, pen=None, size=5)
            else:
                pen = pg.mkPen(*intcolor, width=2)
                plot = pg.PlotCurveItem(name=name, pen=pen)
            self.plots.append(plot)
            self.plt.addItem(plot)
            if show_err:
                errorbar = pg.ErrorBarItem(pen=intcolor)
                self.errorbars.append(errorbar)
                self.plt.addItem(errorbar)

        self.fits = []
        if show_fit:
            for idx, name in enumerate(legend, start=len(legend)):
                pen = pg.mkPen(idx, num_plots, width=2)
                plot = pg.PlotCurveItem(name=f"{name}_fit", pen=pen)
                self.fits.append(plot)
                self.plt.addItem(plot)

    def plot(self, *, x=None, y=None, yfit=None, xerr=None, yerr=None) -> None:
        """x/xerr must be 1D np array, y/yerr/yfit can be 1D or 2D np array"""
        self._hook(x=x, y=y, yfit=yfit, xerr=xerr, yerr=yerr)

    def _update_many_plot(self, **kwargs) -> None:
        """ """
        x, y = kwargs["x"], kwargs["y"]
        for idx in range(y.shape[0]):
            self.plots[idx].setData(x, y[idx])

    def _update_one_plot(self, **kwargs) -> None:
        """ """
        self.plots[0].setData(kwargs["x"], kwargs["y"])

    def _update_many_plot_err(self, **kwargs) -> None:
        """ """
        x, y, xerr, yerr = kwargs["x"], kwargs["y"], kwargs["xerr"], kwargs["yerr"]
        for idx in range(y.shape[0]):
            self.plots[idx].setData(x, y[idx])
            self.errorbars[idx].setData(x=x, y=y[idx], height=yerr[idx], width=xerr)

    def _update_one_plot_err(self, **kwargs) -> None:
        """ """
        x, y, xerr, yerr = kwargs["x"], kwargs["y"], kwargs["xerr"], kwargs["yerr"]
        self.plots[0].setData(x, y)
        self.errorbars[0].setData(x=x, y=y, height=yerr, width=xerr)

    def _update_many_plot_fit(self, **kwargs) -> None:
        """ """
        x, y, yfit = kwargs["x"], kwargs["y"], kwargs["yfit"]
        for idx in range(y.shape[0]):
            self.plots[idx].setData(x, y[idx])
            self.fits[idx].setData(x, yfit[idx])

    def _update_one_plot_fit(self, **kwargs) -> None:
        """ """
        x, y, yfit = kwargs["x"], kwargs["y"], kwargs["yfit"]
        self.plots[0].setData(x, y)
        self.fits[0].setData(x, yfit)

    def _update_many_plot_fit_err(self, **kwargs) -> None:
        """ """
        x, y = kwargs["x"], kwargs["y"]
        yfit, xerr, yerr = kwargs["yfit"], kwargs["xerr"], kwargs["yerr"]
        for idx in range(y.shape[0]):
            self.plots[idx].setData(x, y[idx])
            self.fits[idx].setData(x, yfit[idx])
            self.errorbars[idx].setData(x=x, y=y, height=yerr[idx], width=xerr)

    def _update_one_plot_fit_err(self, **kwargs) -> None:
        """ """
        x, y = kwargs["x"], kwargs["y"]
        yfit, xerr, yerr = kwargs["yfit"], kwargs["xerr"], kwargs["yerr"]
        self.plots[0].setData(x, y)
        self.fits[0].setData(x, yfit)
        self.errorbars[0].setData(x=x, y=y, height=yerr, width=xerr)


class LiveImagePlotter(LivePlotter):
    """for colormaps (linear scale)"""

    def __init__(
        self,
        xmin: float,
        xmax: float,
        xlen: int,
        ymin: float,
        ymax: float,
        ylen: int,
        cmap: str = "viridis",
        zlabel: str = None,
        **kwargs,
    ) -> None:
        """ """
        super().__init__(**kwargs)

        self.image = pg.ImageItem(
            image=np.zeros((ylen, xlen)),  # nominal z data
            axisOrder="row-major",
            rect=[xmin, ymin, xmax - xmin, ymax - ymin],  # bounding box for image
        )
        self.plt.addItem(self.image)
        cmap = pg.colormap.get(cmap, source="matplotlib")
        self.colorbar = pg.ColorBarItem(colorMap=cmap, label=zlabel, interactive=False)
        self.colorbar.setImageItem(self.image, insert_in=self.plt)

    def plot(self, zdata: np.ndarray) -> None:
        """ """
        self.image.setImage(image=zdata)
        self.colorbar.setLevels(low=zdata.min(), high=zdata.max())


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    """
    lp = LiveImagePlotter(
        title="live plot",
        xmin=0,
        xmax=2,
        xlen=10,
        ymin=1,
        ymax=4,
        ylen=8,
        xlabel="X",
        xunits="s",
        ylabel="Y",
        yunits="m",
        zlabel="test",
        cmap="twilight_shifted",
    )

    z = np.random.uniform(low=0.0, high=6.0, size=(8, 10))
    lp.plot(zdata=z)

    """
    lp = LiveDataPlotter(
        title="live plot",
        xlabel="X",
        xunits="s",
        ylabel="Y",
        yunits="m",
        scatter=False,
        legend=None,
        show_fit=True,
        show_err=True,
    )

    x = np.linspace(0, 1, 50)
    a = np.linspace(0, 5, 50)
    b = np.linspace(0, 4, 50)
    lp.plot(x=x, y=a, yerr=1, yfit=b)

    lp.show()
    app.exec()
