""" 
This module contains utilities to specify datasets to control how experimental data is saved and plotted. 
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

from labctrl.sweep import Sweep

@dataclass
class Dataset:
    """ """

    # axes defines the dataset's dimension labels and shape
    axes: tuple[Sweep] | dict[str, Sweep | int]

    # name of the dataset, as it will appear in the datafile
    name: str | None = None

    # function applied to incoming data before saving/plotting
    datafn: Callable[..., np.ndarray] = None

    # whether or not this dataset will be saved to the datafile by the DataSaver
    save: bool = True

    # data type string to be passed as the 'dtype' attribute to h5py's create_dataset()
    dtype: str = "f4"

    # units string which will be saved as an attribute of the dataset in the datafile
    units: str | None = None

    # if chunks is None, we do auto-chunking, else we pass the tuple[int] (must be the same shape as the dataset) to h5py's create_dataset().
    chunks: tuple[int] = None

    # whether or not this dataset will be live plotted during an experiment
    plot: bool = False

    # for 2D datasets, max number of line plots to show before switching to image plots
    maxlines: int = 10

    # functions to receive best fit and errorbar arrays during plotting
    fitfn: Callable[[np.ndarray], np.ndarray] = None
    errfn: Callable[[np.ndarray], np.ndarray] = None

    @property
    def shape(self) -> list[int]:
        """ """
        return [v.length if isinstance(v, Sweep) else v for v in self.axes.values()]
