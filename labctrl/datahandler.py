""" Module to handle writing to and reading from hdf5 (.h5) files

Decides data handling for Experiments so user doesn't have to know the nitty-gritties of h5py
1. one .h5 file per experimental run
2. fixed group structure - only one top level group
    - contains datasets (linked to dimension scales, if specified)
    - and contains groups equal to the number of dicts supplied to save_metadata. each dict is meant to be the snapshot of a resource involved in the experiment run.
3. built to run in swmr mode which allows for live data saving and loading
4. datasets to be specified (name, maxshape, dimension labels, data type, units) through DataSaver's dataspec attribute during DataSaver initialization and prior to saving the experimental data generated i.e. no dynamic dataset creation. Dimension scales can be linked to datasets automatically.
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
        "dims": OPTIONAL (tuple[str]) label(s) for each dimension in the shape, use this to relate each dim of dependent variable data to independent variable data. will be simply ignored for coordinates as it doesn't make sense to attach dimension scales to coordinates (as the coordinates are nothing but dimension scales themselves).
        "dtype": OPTIONAL str, data type string (same as those used by numpy), must be single valued as datasets contain homogeneous data
        "units": OPTIONAL str
    }

    """

    _dataspec_keys: set[str] = {"shape", "chunks", "dtype", "dims", "units"}

    def __init__(self, path: Path, **dataspec) -> None:
        """path: full path to the datafile (must end in .h5 or .hdf5). DataSaver is not responsible for setting datafile naming/saving convention, the caller is."""

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
        else:
            message = f"No dataset specification found, 'dataspec' can't be empty."
            logger.error(message)
            raise DataSavingError(message) from None

        logger.debug(f"Initialized a DataSaver tagged to data file at {self._path}.")

    def _validate_path(self) -> None:
        """validate path, also create folder(s)/file as needed"""
        try:
            # ensure folder containing the datafile exists
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # create datafile, throws error if file exists
            self._path.touch(exist_ok=False)
            logger.debug(f"Created an .h5 data file at '{self._path}'.")
        except (AttributeError, TypeError):
            message = f"Invalid data file path '{self._path}', must be of '{Path}'."
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
                # ignore dims if specified, coordinates cannot have dims, they are dims!
                self._dataspec[name].pop("dims", None)
                # if self._dataspec[name] is not a mapping, TypeError will be thrown
                self._create_dataset(file=file, name=name, **self._dataspec[name])

            datasets = self._dataspec.keys() - coordinates  # create other datasets
            for name in datasets:
                dims = self._dataspec[name].pop("dims", None)
                self._create_dataset(file=file, name=name, **self._dataspec[name])
                if dims is not None:
                    self._dimensionalize_dataset(file, name, coordinates, dims)

            file.flush()

    def _find_coordinates(self) -> set[str]:
        """coordinate datasets are those whose named strings appear in both the dataspec keyset and the 'dims' tuple of another dataset"""
        all_dims = []  # container to hold all dimension labels found in dataspec
        for spec in self._dataspec.values():
            dims = spec.get("dims", None)  # dims is an optional dataspec key
            if dims is not None:
                all_dims.append(*dims)
        coordinates = self._dataspec.keys() & set(all_dims)
        logger.debug(f"Found {len(coordinates)} {coordinates = } in the dataspec.")
        return coordinates

    def _create_dataset(
        self,
        file: h5py.File,
        name: str,
        shape: tuple[int],
        chunks: bool | tuple[int],
        dtype: str = None,
        units: str = None,
    ) -> None:
        """wrapper for h5py method. default fillvalue decided by h5py."""
        # chunks = False for fixed-size dataset, else consider as resizable dataset
        # for resizable datasets, chunks must be either True (auto-chunking)
        # or tuple with the same dimension as shape
        chunks = None if chunks is False else chunks
        # shape = maxshape because we resize dataset after all data is written to it
        maxshape = None if chunks is False else shape

        dataset = file.create_dataset(
            name=name, shape=shape, maxshape=maxshape, chunks=chunks, dtype=dtype
        )

        if units is not None:
            dataset.attrs["units"] = str(units)

        logger.debug(
            f"Created dataset named '{name}' in file '{file.filename}' with "
            f"specification: {shape = }, {chunks = }, {dtype = }, {units = }."
        )

    def _dimensionalize_dataset(
        self, file: h5py.File, name: str, coordinates: set[str], dims: tuple[str]
    ) -> None:
        """internal method, for attaching dim scales to a single dataset with name=name."""
        dataset = file[name]
        for idx, label in enumerate(dims):
            dataset.dims[idx].label = str(label)  # make dimension label
            message = f"Set dataset '{name}' dimension {idx} {label = }."
            if label in coordinates:  # make and attach dimension scale
                coordinate = file[label]
                coordinate.make_scale(label)
                dataset.dims[idx].attach_scale(coordinate)
                message += f" Attached dimension scale."
        logger.debug(message)

    def __enter__(self) -> DataSaver:
        """ """
        self._file = h5py.File(self._path, mode="r+")
        logger.debug(f"Start DataSaver session tagged to file '{self._file.filename}'.")

        # track the data batch count saved to disk so far for each dataset(s)
        for spec in self._dataspec.values():
            if "batches" not in spec:
                spec["batches"] = 0
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        # trim resizable datasets if needed
        for name, spec in self._dataspec.items():
            # find resizable datasets that have been written to in batches
            # we ignore trimming in the case where a resizable dataset has not been
            # written to at all as it is a poor use case that doesn't need our attention
            if spec["chunks"] is not False and spec["batches"] != 0:
                dataset = self._file[name]
                shape = dataset.shape
                dataset.resize((spec["batches"], *shape[1:]))
                logger.debug(
                    f"Resized dataset '{name}' from {shape} to {dataset.shape} as "
                    f"{spec['batches']} batches were written to it."
                )

        self._file.flush()
        self._file.close()

    def save_data(self, name: str, data: np.ndarray, position: int = ...):
        """save a batch of data to the named dataset at (optional) position.

        incoming data must have same dimension n as declared under its name in the dataspec, and must match in the n-1 innermost dimensions, with the outermost dimension being treated as the "number of batches" which will be inserted into index specified by 'position', this "number of batches" is the outermost dimension. data resizing responsibility lies with caller. if position = ... then the whole dataset with 'name' will be written with the incoming data (caller must ensure data is not overwritten). can't use position to append to 1D datasets (they are considered a unit batch).
        """
        dataset = self._get_dataset(name)
        self._validate_shape(name, dataset, data, position)
        dataset[position] = data  # write to dataset
        self._file.flush()

        if position is not ...:
            self._dataspec[name]["batches"] += data.shape[0]  # track batch count
        else:
            self._dataspec[name]["batches"] = 0  # not being written to in batches

    def _get_dataset(self, name: str) -> h5py.Dataset:
        """ """
        try:
            return self._file[name]
        except TypeError:
            message = (
                f"The data file is not open. Did you try to call save_data() from "
                f"outside the DataSaver context? Please use the DataSaver context "
                f"manager and try again."
            )
            logger.error(message)
            raise DataSavingError(message) from None
        except KeyError:
            message = f"Dataset '{name}' does not exist in {self._file.filename}."
            logger.error(message)
            raise DataSavingError(message) from None

    def _validate_shape(
        self,
        name: str,
        dataset: h5py.Dataset,
        data: np.ndarray,
        position,
    ) -> None:
        """dataset is stored in .h5 file on disk with 'name'. data is incoming data to be written to that dataset."""
        slc = slice(None, None) if position is ... else slice(1, None)

        try:
            if dataset.shape[slc] != data.shape[slc]:
                if position is ...:
                    message = (
                        f"Failed to write dataset '{name}' as incoming {data.shape = }"
                        f"does not equal {dataset.shape = } declared in the dataspec."
                    )
                else:
                    message = (
                        f"Failed to append to dataset '{name}' as the lower n-1 dims of"
                        f" incoming {data.shape[1:] = } != {dataset.shape[1:] = }."
                    )
                logger.error(message)
                raise DataSavingError(message)
        except AttributeError:
            message = (
                f"Failed to validate shape of incoming data for dataset '{name}'. "
                f"Please check if the incoming datastream is of '{np.ndarray}' "
                f"and that the data file member named '{name}' is of '{h5py.Dataset}'."
            )
            logger.error(message)
            raise DataSavingError(message) from None
        except IndexError:
            message = (
                f"Invalid attempt to append one-dimensional data to dataset '{name}'. "
                f"Please reshape incoming data or redeclare the dataspec and try again."
            )
            logger.error(message)
            raise DataSavingError(message) from None

    def save_metadata(self):
        """ """


if __name__ == "__main__":
    """ """
    # d = DataSaver(path=Path.cwd() / "data/sweep.h5")

"""
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
    def dimensionalize_datasets(self) -> None:
        dimensionalize means attach dimension scales to specified datasets. call this when done specifying all datasets with create_dataset(). if using dataspec attribute, no need to call this, it is done automatically. no need to check if datasets exist bc unless _dataspec has been messed with, that is guaranteed
        with h5py.File(self._path, mode="r+") as file:
            coordinates = self._find_coordinates()
            for name in self._dataspec.keys() - coordinates:
                dims = self._dataspec[name].get("dims", None)
                if dims is not None:
                    self._dimensionalize_dataset(file, name, coordinates, dims)

"""
