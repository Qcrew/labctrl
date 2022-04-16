""" Module to handle writing to and reading from hdf5 (.h5) files
Opinionated and limited. 
"""

from pathlib import Path

import h5py
import numpy as np

from labctrl.settings import Settings


class DataSavingError(Exception):
    """ """


class DataSaver:
    """context manager for saving data to an .h5 file that is associated with an experimental run. Each experimental run initializes a datasaver with a dataspec. Two groups - "data" where datasets are saved and "metadata" where other heterogenous attributes are saved. The groups are fixed so as to simplify data saving. We prescribe that each experimental run is associated with one hdf5 data file.

    Initialize the datasaver at the start of the Experiment run method. Then use it to save data after data is generated and fetched.

    dataspec structure: each dataspec key is dataset name and value is a dict specifying dataset creation
    e.g. <dataset1_name> = {
        "shape": tuple[int], max shape this dataset can have
        "dimlabels": labels for each dimension in the shape, use this to relate each dim of dependent variable data to independent variable data.
        "dtype": <dataset1_data_type> must be single valued, datasets contain homogeneous data
        "units": str
    }

    """

    def __init__(self, path: Path, **dataspec) -> None:
        """path: full path to the datafile (must end in .h5 or .hdf5). DataSaver is not responsible for setting datafile naming/saving convention, the caller is."""

        # TODO error handling
        # ensure folder containing the datafile exists
        path.parent.mkdir(parents=True, exist_ok=True)
        # create datafile, throws error if file exists
        path.touch(exist_ok=False)
        self._path = path

        dimlabels = {label for spec in dataspec.values() for label in spec["dimlabels"]}
        coordinates = dataspec.keys() & dimlabels

        with h5py.File(self._path, mode="r+") as file:
            data = file.create_group("data")

            for name in coordinates:
                # TODO error check if coordinates
                spec = dataspec[name]
                data.create_dataset(
                    name=name,
                    shape=spec["shape"],
                    dtype=spec["dtype"],
                    fillvalue=np.nan,
                )
                data[name].

            for name, spec in dataspec.items():
                # TODO spec key error checks
                # for now, do auto-chunking, let's worry about manual chunking later
                # we follow the strategy of adding data to dataset, keeping track of inserted shape, and trimming it after all data has been added
                data.create_dataset(
                    name=name,
                    shape=spec["shape"],
                    dtype=spec["dtype"],
                    chunks=True,
                )
                dimlabels.update(spec["dimlabels"])

            # link up coordinates and datasets
            coordinates = dataspec.keys() & dimlabels
            for name, spec in dataspec.items():
                if name in coordinates:
                    data[name].make_scale(name)

                for label in spec["dimlabels"]:
                    if label in self._dataspec.keys() and label not in coordinates:
                        # we have found a new coordinate (dimension scale)
                        coordinates.add(label)
                        data[name]

    def create_dataset(self, name, ):
        """ """


if __name__ == "__main__":
    d = DataSaver(path=Path.cwd() / "data/20220409/150857_sweep.h5")
