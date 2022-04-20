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

must save all data in same context session!!! if not we will trim!
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

        if not self._dataspec:
            message = f"No dataset specification found, 'dataspec' can't be empty."
            logger.error(message)
            raise DataSavingError(message) from None

        self._file = None  # will be updated by __enter__()
        self._lock = False  # prevent write to file once first DataSaver context exits
        self._path = path
        self._validate_path()

        self._dataspec: dict[str, dict] = dataspec
        try:
            self._initialize_datasets()
        except (AttributeError, TypeError) as err:
            message = (
                f"While initializing datasets, encountered {err}. "
                f"Please check whether you provided a valid dataset specification."
            )
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
        if self._lock:
            message = (
                f" Data file at '{self._path}' has been opened during a previous "
                f"DataSaver session and can no longer be written into."
            )
            logger.error(message)
            raise DataSavingError(message)

        self._file = h5py.File(self._path, mode="r+")
        logger.debug(f"Started DataSaver session tagged to '{self._file.filename}'.")

        # track the maximum value of the index data is written to along each dimension 
        # for each dataset, this will be used to resize (trim) the dataset in __exit__()
        for spec in self._dataspec.values():
            if spec["chunks"] is not False:  # dataset is resizable
                rank = len(spec["shape"])
                spec["resize"] = (0, ) * rank

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        # trim resizable datasets
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
        self._lock = True  # lock data file, no more data can be written to it

    def save_data(
        self, name: str, data: np.ndarray, index: tuple[int | slice] | ... = ...
    ) -> None:
        """insert a batch of data to the named dataset at (optional) specified index. please call this method within a datasaver context, if not it will throw error.

        with DataSaver(path_to_datafile, dataset_specification) as datasaver:
            # key-value pairs in metadata_dict will be stored as group_name group attributes in .h5 file
            datasaver.save_metadata(group_name, metadata_dict)

            datasaver.save_data(name, incoming_data, [index])

        name: str the dataset name as declared in the dataspec. raises an error if we encounter a dataset that has not been declared prior to saving

        data: np.ndarray (using list will throw error, please use numpy arrays) incoming data to be written into dataset

        index = ... means that the incoming data is written to the entire dataset in one go i.e. we do dataset[...] = incoming_data. Use this when all the data to be saved is available in memory at the same time. this is the default option

        index = tuple[int | slice] means that you want to insert the incoming data to a specific location ("hyperslab") in the dataset. Use this while saving data that is being streamed in successive batches or in any other application that requires appending to existing dataset. we pass the index directly to h5py i.e. we do dataset[index] = incoming_data, so user must be familiar with h5py indexing convention to use this feature effectively. index must be a tuple (not list etc) to ensure proper saving behaviour. to ensure more explicit code and allow reliable tracking of written data, we also enforce that the index tuple dimensions match that of the dataset shape as declared in the dataspec - if you want to write along an entire dimension, pass in a slice(None) object at that dimension's index.
        """
        dataset = self._get_dataset(name)
        self._validate_index(name, dataset, index)
        dataset[index] = data  # write to dataset TODO error handling
        self._file.flush()

        # track size from indices for resizable datasets so we can trim them later
        if self._dataspec[name]["chunks"] is not False:
            self._track_size(name, index)

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

    def _validate_index(
        self, name: str, dataset: h5py.Dataset, index: tuple[int | slice]
    ) -> None:
        """ """
        # isinstance check is necessary to ensure stable datasaving
        if not isinstance(index, tuple):
            message = (
                f"Expect index of {tuple}, got '{index}' of '{type(index)}'"
                f"while writing to dataset '{name}'."
            )
            logger.error(message)
            raise DataSavingError(message)

        # dimensions of dataset and index must match to allow tracking of written data
        if not dataset.ndim == len(index):
            message = (
                f"Expect dataset '{name}' dimensions ({dataset.ndim}) to equal the"
                f"length of the index tuple, got {index = } with length {len(index)}."
            )
            logger.error(message)
            raise DataSavingError(message)

    def save_metadata(self):
        """ """


if __name__ == "__main__":
    """ """
    d = DataSaver(path=Path.cwd() / "data/sweep.h5")
