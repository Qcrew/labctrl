""" Module to handle writing to and reading from hdf5 (.h5) files

Decides data handling for Experiments so user doesn't have to know the nitty-gritties of h5py
1. one .h5 file per experimental run
2. fixed group structure - only one top level group
    - contains datasets (linked to dimension scales, if specified)
    - and contains groups equal to the number of dicts supplied to save_metadata. each dict is meant to be the snapshot of a resource involved in the experiment run.
3. built to run in swmr mode which allows for live data saving and loading
4. datasets to be specified (name, maxshape, dimension labels, data type, units) through DataSaver's dataspec attribute or create_dataset() method prior to saving the experimental data generated i.e. no dynamic dataset creation. Dimension scales can be linked to datasets (giving dataspec does this automatically).
4. live save protocol.
5. numpy arrays only!!! (that's how h5py treats data anyways, so we also prescribe that users supply np arrays for saving)
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from labctrl.logger import logger


class DataSavingError(Exception):
    """ """


class DataSaver:
    """context manager for saving data to an .h5 file that is associated with an experimental run. only to be used as a context manager (for clean I/O).

    dataspec structure: each dataspec key is dataset name and value is a dict specifying dataset creation
    e.g. <dataset1_name> = {
        "shape": tuple[int], dataset shape, enter max possible shape if resize = True
        "chunks": bool or tuple[int], if True, resizable dataset with auto-chunking, if false, fixed-size dataset. If tuple[int] (must be same shape as dataset), then resizable dataset with manual chunking True. you would want to use resizable datasets for live saving and fixed size datasets to store independent data, for instance.
        "dims": (none or tuple[str]) label(s) for each dimension in the shape, use this to relate each dim of dependent variable data to independent variable data. will be simply ignored for coordinates as it doesn't make sense to attach dimension scales to coordinates (as the coordinates are nothing but dimension scales themselves).
        "dtype": optional str, data type string (same as those used by numpy), must be single valued as datasets contain homogeneous data
        "units": optional str
    }

    """

    _dataspec_keys: set[str] = {"shape", "chunks", "dtype", "dims", "units"}

    def __init__(self, path: Path, **dataspec) -> None:
        """path: full path to the datafile (must end in .h5 or .hdf5). DataSaver is not responsible for setting datafile naming/saving convention, the caller is."""
        logger.debug("Initializing a DataSaver...")

        self._file = None  # will be updated by __enter__()
        self._path = path
        self._validate_path()

        self._dataspec: dict[str, dict] = dataspec
        if self._dataspec:
            try:
                self._initialize_datasets()
            except (AttributeError, TypeError) as err:
                message = (
                    f"While initializing datasets, encountered {err}. "
                    f"Please check whether you provided a valid dataset specification."
                )
                logger.error(message)
                raise DataSavingError(message) from None

    def _validate_path(self) -> None:
        """validate path, also create folder(s)/file as needed"""
        try:
            # ensure folder containing the datafile exists
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # create datafile, throws error if file exists
            self._path.touch(exist_ok=False)
            logger.debug(f"Created an .h5 data file at '{self._path}'.")
        except (AttributeError, TypeError):
            message = (
                f"Invalid data file path supplied. "
                f"Expect path of '{Path}', not '{self._path}' of {type(self._path)}."
            )
            logger.error(message)
            raise DataSavingError(message) from None
        except FileExistsError:
            message = (
                f"Data file already exists at specified path '{self._path}'. "
                f"Please choose a new data file path and try again."
            )
            logger.error(message)
            raise DataSavingError(message) from None

    def _initialize_datasets(self) -> None:
        """ """
        with h5py.File(self._path, mode="r+") as file:
            coordinates = self._find_coordinates()

            for name in coordinates:  # create coordinate datasets first
                self._dataspec[name].pop("dims", None)  # ignore "dims" if specified
                self._create_dataset(file=file, name=name, **self._dataspec[name])

            for name in self._dataspec.keys() - coordinates:  # create other datasets
                dims = self._dataspec[name].pop("dims", None)
                self._create_dataset(file=file, name=name, **self._dataspec[name])
                if dims is not None:
                    self._dimensionalize_dataset(file, name, coordinates, dims)

    def _find_coordinates(self) -> set[str]:
        """coordinate datasets are those whose named strings appear in both the dataspec keyset and the 'dims' tuple of another dataset"""
        all_dims = []  # container to hold all dimension labels found in dataspec
        for spec in self._dataspec.values():
            dims = spec.get("dims", None)
            if dims is not None:
                all_dims.append(*dims)
        coordinates = self._dataspec.keys() & set(all_dims)
        logger.debug(f"Found {len(coordinates)} {coordinates = }.")
        return coordinates

    def create_dataset(
        self,
        name: str,
        shape: tuple[int],
        chunks: bool | tuple[int],
        dtype: str = None,
        dims: tuple[str] = None,  # accessed by locals() call
        units: str = None,
    ) -> None:
        """ """
        self._dataspec[name] = {  # update dataspec
            k: v for k, v in locals().items() if k in DataSaver._dataspec_keys
        }
        if name in self._dataspec.keys():
            logger.warning(f"Overwrote specification of dataset named '{name}'.")
        with h5py.File(self._path, mode="r+") as file:
            self._create_dataset(file, name, shape, chunks, dtype, units)

    def _create_dataset(
        self,
        file: h5py.File,
        name: str,
        shape: tuple[int],
        chunks: bool | tuple[int],
        dtype: str = None,
        units: str = None,
    ) -> None:
        """must open h5 file prior to calling this internal method. default fillvalue decided by h5py. internal method."""
        # False = fixed-size dataset, else = resizable dataset
        # for resizable datasets, chunks must be either True (auto-chunking)
        # or tuple with the same dimension as shape and we set shape = maxshape because # we resize (trim) dataset after all data is written to it
        chunks = None if chunks is False else chunks
        maxshape = None if chunks is False else shape
        dset = file.create_dataset(
            name=name, shape=shape, maxshape=maxshape, chunks=chunks, dtype=dtype
        )
        if units is not None:
            dset.attrs["units"] = str(units)
        logger.debug(
            f"Created dataset named '{name}' in file '{file.filename}' with "
            f"specification: {shape = }, {chunks = }, {dtype = }, {units = }."
        )

    def dimensionalize_datasets(self) -> None:
        """dimensionalize means attach dimension scales to specified datasets. call this when done specifying all datasets with create_dataset(). if using dataspec attribute, no need to call this, it is done automatically. no need to check if datasets exist bc unless _dataspec has been messed with, that is guaranteed."""
        with h5py.File(self._path, mode="r+") as file:
            coordinates = self._find_coordinates()
            for name in self._dataspec.keys() - coordinates:
                dims = self._dataspec[name].get("dims", None)
                if dims is not None:
                    self._dimensionalize_dataset(file, name, coordinates, dims)

    def _dimensionalize_dataset(
        self, file: h5py.File, name: str, coordinates: set[str], dims: tuple[str]
    ) -> None:
        """internal method, for attaching dim scales to a single dataset with name=name. no need to check if datasets exist because that's virtually guaranteed."""
        dset = file[name]
        for idx, label in enumerate(dims):
            dset.dims[idx].label = str(label)  # make dimension label
            message = f"Set dataset '{name}' dimension {idx} {label = }."
            if label in coordinates:  # make and attach dimension scale
                coordinate = file[label]
                coordinate.make_scale(label)
                dset.dims[idx].attach_scale(coordinate)
                message += f" Attached dimension scale."
        logger.debug(message)

    def __enter__(self) -> DataSaver:
        """ """
        # TODO implement SWMR!!!
        self._file = h5py.File(self._path, mode="r+")
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        self._file.flush()
        self._file.close()

    def save_data(self, data: dict[str, np.ndarray], pos: tuple[int] = None):
        """data is a dict with key = dataset name and value = np.ndarray. if pos (a tuple with rank equal to dataset rank) is specified, data will be appended if dataset is specified as resizable - use this for live saving. if pos is None then we will simply write the dataset with the incoming data (caller responsibility to avoid overwrite)."""
        # TODO warning mechanism for weird usage - i.e. if pos specified but dataset not resizable, if shape mismatch

    def save_metadata(self):
        """ """


if __name__ == "__main__":
    d = DataSaver(path=Path.cwd() / "data/sweep.h5")
