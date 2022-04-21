""" Module to handle writing to and reading from hdf5 (.h5) files

Decides data handling for Experiments so user doesn't have to know the nitty-gritties of h5py
1. one .h5 file per experimental run, all datasets generated by experiment to be written to file inside a single DataSaver session i.e. one entry-exit of DataSaver context.
2. fixed group structure - only one top level group
    - contains datasets (linked to dimension scales, if specified)
    - and contains groups equal to the number of dicts supplied to save_metadata. each dict is meant to be the snapshot of a resource involved in the experiment run.
3. built to run in swmr mode which allows for live data saving and loading
4. datasets to be specified (name, shape, chunks, dimension labels, data type, units) through DataSaver's dataspec attribute during DataSaver initialization and prior to saving the experimental data generated i.e. no dynamic dataset creation. Dimension scales will be linked to datasets automatically.
"""

from __future__ import annotations

from numbers import Number
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
        "shape": REQUIRED tuple[int], dataset shape, enter max possible shape the dataset may have
        "chunks": OPTIONAL tuple[int], if not specified, h5py does auto-chunking. If tuple[int] (must be same shape as dataset), we pass the tuple as the 'chunks' attribute to h5py's create_dataset() method.
        "dims": OPTIONAL (tuple[str]) label(s) for each dimension in the shape, use this to relate each dim of dependent variable data to independent variable data. will be simply ignored for coordinates as it doesn't make sense to attach dimension scales to coordinates (as the coordinates are nothing but dimension scales themselves).
        "dtype": OPTIONAL str, data type string (same as those used by numpy), must be single valued as datasets contain homogeneous data. will be passed as the 'dtype' attribute to h5py's create_dataset() method.
        "units": OPTIONAL str
    }

    """

    _dataspec_keys: set[str] = {"shape", "chunks", "dtype", "dims", "units"}

    def __init__(self, path: Path, **dataspec) -> None:
        """path: full path to the datafile (must end in .h5 or .hdf5). DataSaver is not responsible for setting datafile naming/saving convention, the caller is."""

        if not dataspec:
            message = f"No dataset specification found, 'dataspec' can't be empty."
            logger.error(message)
            raise DataSavingError(message) from None

        self._file = None  # will be updated by __enter__() and __exit__()
        self._lock = False  # prevent write to file once first DataSaver context exits
        self._path = path
        self._validate_path()

        self._dataspec: dict[str, dict] = dataspec
        try:
            self._initialize_datasets()
        except (AttributeError, TypeError):
            message = (
                f"Please check whether you provided a valid dataset specification."
            )
            logger.error(message)
            raise DataSavingError(message)
        except FileExistsError:
            message = (
                f"Data file already exists at specified path '{self._path}'. "
                f"Please choose a new data file path and try again."
            )
            logger.error(message)
            raise DataSavingError(message) from None

        logger.debug(f"Initialized a DataSaver tagged to data file at {self._path}.")

    def _validate_path(self) -> None:
        """validate path, also create folder(s)/file as needed"""
        try:
            # ensure path ends in .h5, .hdf5, .he5, .hdf
            if self._path.suffix not in (".h5", ".hdf5", ".he5", ".hdf"):
                message = f"Path '{self._path}' must end in .h5, .hdf5, .he5, or .hdf'."
                logger.error(message)
                raise DataSavingError(message)
            # ensure folder containing the datafile exists
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except (AttributeError, TypeError):
            message = f"Invalid data file path '{self._path}', must be of '{Path}'."
            logger.error(message)
            raise DataSavingError(message) from None

    def _initialize_datasets(self) -> None:
        """ """
        # mode = "x" means create file, fail if exists
        with h5py.File(self._path, mode="x", track_order=True) as file:
            coordinates = self._find_coordinates()  # coordinates are independent vars

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

    def _find_coordinates(self) -> set[str]:
        """coordinate datasets are those whose named strings appear in both the dataspec keyset and the 'dims' tuple of another dataset"""
        all_dims = []  # container to hold all dimension labels found in dataspec
        for spec in self._dataspec.values():
            dims = spec.get("dims", None)  # dims is an optional dataspec key
            if dims is not None:
                all_dims.extend(dims)
        coordinates = self._dataspec.keys() & set(all_dims)
        logger.debug(f"Found {len(coordinates)} {coordinates = } in the dataspec.")
        return coordinates

    def _create_dataset(
        self,
        file: h5py.File,
        name: str,
        shape: tuple[int],
        chunks: bool | tuple[int] = True,
        dtype: str = None,
        units: str = None,
    ) -> None:
        """wrapper for h5py method. default fillvalue decided by h5py."""
        # by default, we create resizable datasets with shape = maxshape
        # we resize the dataset in __exit__() after all data is written to it
        dataset = file.create_dataset(
            name=name,
            shape=shape,
            maxshape=shape,
            chunks=chunks,
            dtype=dtype,
            track_order=True,
        )

        if units is not None:
            dataset.attrs["units"] = str(units)

        logger.debug(
            f"Created dataset named '{name}' in file '{self._path.name}' with "
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

        # track the maximum value of the index the data is written to for each dimension
        # this will allow us to trim reziable datasets and mark uninitialized ones
        for spec in self._dataspec.values():
            rank = len(spec["shape"])
            spec["size"] = [0] * rank

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        # trim datasets
        for name, spec in self._dataspec.items():
            fin_shape = tuple(spec["size"])
            init_shape = spec["shape"]

            if all(idx == 0 for idx in fin_shape):  # dataset has not been written into
                del self._file[name]  # delete dataset
                logger.debug(f"Deleted datset '{name}' as it was not written into.")
            elif fin_shape != init_shape:  # dataset has been partially written into
                self._file[name].resize(fin_shape)  # trim dataset
                logger.debug(f"Resized dataset '{name}': {init_shape} -> {fin_shape}.")

        self._file.close()
        self._file = None
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

        data: np.ndarray incoming data to be written into dataset

        index = ... means that the incoming data is written to the entire dataset in one go i.e. we do dataset[...] = incoming_data. Use this when all the data to be saved is available in memory at the same time. this is the default option

        index = tuple[int | slice] means that you want to insert the incoming data to a specific location ("hyperslab") in the dataset. Use this while saving data that is being streamed in successive batches or in any other application that requires appending to existing dataset. we pass the index directly to h5py i.e. we do dataset[index] = incoming_data, so user must be familiar with h5py indexing convention to use this feature effectively. NOTE - we don't support ellipsis (...) please don't use it and use slice(None) instead. index must be a tuple (not list etc) to ensure proper saving behaviour. to ensure more explicit code and allow reliable tracking of written data, we also enforce that the index tuple dimensions match that of the dataset shape as declared in the dataspec - if you want to write along an entire dimension, pass in a slice(None) object at that dimension's index.
        """
        self._validate_session()
        dataset = self._get_dataset(name)
        self._validate_index(name, dataset, index)
        dataset[index] = data  # write to dataset TODO error handling
        self._file.flush()

        try:
            logger.debug(f"Wrote '{data.shape = }' to dataset '{name}' at '{index = }'")
        except AttributeError:  # if the supplied data is not an np array
            logger.debug(f"Wrote '{len(data) = }' to dataset '{name}' at '{index = }'.")

        self._track_size(name, index)  # for trimming dataset if needed in __exit__()

    def _validate_session(self) -> None:
        """check if hdf5 file is currently open (called when either save_data() or save_metadata() is called). enforces use of DataSaver context manager as the only means of writing to the data file."""
        if self._file is None:
            message = (
                f"The data file is not open. Please call data saving methods within a "
                f"DataSaver context manager and try again."
            )
            logger.error(message)
            raise DataSavingError(message)

    def _get_dataset(self, name: str) -> h5py.Dataset:
        """ """
        try:
            return self._file[name]
        except KeyError:
            message = f"Dataset '{name}' does not exist in {self._file.filename}."
            logger.error(message)
            raise DataSavingError(message) from None

    def _validate_index(
        self, name: str, dataset: h5py.Dataset, index: tuple[int | slice]
    ) -> None:
        """ """

        if index is ...:  # single ellipsis is a valid index
            return

        # isinstance check is necessary to ensure stable datasaving
        if not isinstance(index, tuple):
            message = (
                f"Expect index of {tuple}, got '{index}' of '{type(index)}' "
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

    def _track_size(self, name: str, index: tuple[int | slice]) -> None:
        """ """
        if index is ...:  # we have written to the entire dataset
            self._dataspec[name]["size"] = list(self._dataspec[name]["shape"])
            return

        size = self._dataspec[name]["size"].copy()  # to be updated below based on index
        for i, item in enumerate(index):
            if isinstance(item, slice):
                # stop = None means we have written data to this dimension completely
                if item.stop is None:
                    size[i] = self._dataspec[name]["shape"][i]  # maximum possible value
                else:  # compare with existing size along ith dimension
                    size[i] = max(size[i], item.stop)
            else:  # item is an int
                size[i] = max(size[i], item)
        logger.debug(
            f"Tracked dataset '{name}' size {self._dataspec[name]['size']} -> {size}."
        )
        self._dataspec[name]["size"] = size

    def save_metadata(self, name: str | None, **metadata) -> None:
        """save all key-value pairs in metadata dict as attributes of specified group name in data file. if name = None, we save to top-level group in hdf5 file (but make sure you don't overwrite attributes with subsequent calls to save_metadata() if you use name = None). all keys in metadata dict must be strings.
        name: str name of group to save metadata to.
        **metadata: key-value pairs to store as attributes of the named group
        if we find dict(s) inside the given metadata dict, we save them as metadata at the proper group level recursively.
        """
        self._validate_session()
        file = self._file
        group = file if name is None else file.create_group(name, track_order=True)
        self._save_metadata(group, **metadata)

    def _save_metadata(self, group: h5py.Group, **metadata) -> None:
        """internal method, made for recursive saving of metadata"""
        try:
            for key, value in metadata.items():
                value = self._parse_attribute(key, value)
                if isinstance(value, dict):
                    subgroup = group.create_group(key, track_order=True)
                    self._save_metadata(subgroup, **value)
                else:
                    group.attrs[key] = value

                    logger.debug(
                        f"Set {group = } attribute '{key}' with value of {type(value)}."
                    )
        except ValueError:
            message = (
                f"Got ValueError while saving metadata with {key = } and {value = }. "
                f"Data size is too large (>64k), please save it as a dataset instead."
            )
            logger.error(message)
            raise DataSavingError(message)
        except TypeError:
            message = (
                f"Got TypeError while saving metadata with {key = } and {value = }. "
                f"This is because h5py does not support the data type of the value."
            )
            logger.error(message)
            raise DataSavingError(message)

    def _parse_attribute(self, key, value):
        """TODO make these parsing rules more explicit once they have been settled"""
        if isinstance(value, (Number, np.number, str, bool, np.ndarray, dict)):
            return value
        elif isinstance(value, (list, tuple, set, frozenset)):
            value = list(value)

            if not value:  # return list as is if empty
                return value
            elif len(value) == 1:  # return the single value for lists of length one
                return value[0]

            # if list contains all numbers or all values of the same type, return as is
            is_numeric = all(isinstance(item, Number) for item in value)
            is_same_type = all(isinstance(item, type(value[0])) for item in value[1:])
            if is_numeric or is_same_type:
                return value
            else:  # else convert it to a dictionary with the index as the key
                dic = {str(idx): item for idx, item in enumerate(value)}
                print(f"{dic = }")
                return {str(idx): item for idx, item in enumerate(value)}
        elif value is None:
            return h5py.Empty("S10")
        else:
            logger.warning(
                f"Found unusual {value = } of {type(value)} while parsing metadata "
                f"{key = }, h5py attribute saving behaviour may not be reliable."
            )
            return value


if __name__ == "__main__":
    """ """
    import time

    start_time = time.perf_counter()

    x_len = 51
    y_len = 25
    reps = 10

    # this dataspec will be declared by each Experiment class
    dataspec_ = {
        # 1D independent variables x and y
        "x": {
            "shape": (x_len,),
            # "dtype": "f4",  # 32-bit floating point number
            "units": "Hz",
        },
        "y": {
            "shape": (y_len,),
            # "dtype": "f4",
            "units": "dB",
        },
        # 2D dependent variable z with shape (n, y, x) where n is number of repetitions
        # this dataset will be written to in batches (simulate live saving)
        "z": {
            "shape": (reps, y_len, x_len),  # let n = 40
            "dims": ("n", "y", "x"),  # dimension labels
            # "dtype": "f4",
            "units": "AU",
        },
        # 1D dependent variable avg which will be written to once
        "avg": {
            "shape": (y_len, x_len),  # average over n
            # "dtype": "f4",
            "units": "AU",
        },
    }

    # metadata dictionary
    metadata_dict = {
        "int": 2,
        "float": 1.5,
        "complex": 1.0 + 1j,
        "string": "hello wurdl",
        "none": None,  # should be saved z an empty attribute
        "bool": True,
        "nested_dict": {
            "1": 1,  # test if integer key is converted to str
            "e": "e",
            "another_nested_dict": {
                "stop": "nesting",
                "dicts": ["p", "l", "s"],
            },
        },
        "str_list": ["one", "two", "three"],
        "int_set": {1, 2, 3},
        "float_tuple": (1.0, 2.0, 3.0),
        "mixed_number_list": [1.0, 4, 3.4 + 2j],
        "empty_list": [],
        "single_value_list": [95],
        "mixed_type_set": {1, 2, 3, False, "hi"},
        "mixed_list": [None, "a", 1, 3.0, ["a", "b"]],
        "mixed_nested_list": [["a", ["b", ["c", 51], 50], 49], [4.0, 5.4, 3.4], 33],
    }

    # the experiment class will generate the data file name
    from datetime import datetime

    datestamp, timestamp = datetime.now().strftime("%Y%m%d %H%M%S").split()
    path = Path.cwd() / f"data/test/{datestamp}/{timestamp}_sweep.h5"

    # initialize datasaver and enter its context to save data
    # all data generated by the experiment must be saved within a single session

    with DataSaver(path=path, **dataspec_) as datasaver:
        datasaver.save_metadata("mdata", **metadata_dict)

        x = np.linspace(5e9, 6e9, x_len)
        y = np.linspace(0.0, 10.0, y_len)

        datasaver.save_data("x", x)
        datasaver.save_data("y", y)

        # simulate "live" saving in batches
        count = 0  # batch count
        while count < reps:  # enter experiment run loop
            batches = np.random.randint(1, int(reps / 2))
            if count + batches > reps:
                batches = reps - count

            z = np.random.random((batches, y_len, x_len))
            print(z)

            # calculate index position to save this batch of z data at
            index_ = (slice(count, count + batches), slice(None), slice(None))
            datasaver.save_data("z", z, index_)

            count += batches
            print(f"Data {count = }.")
            time.sleep(2)

        # save averaged data over all reps at the end
        avg = np.average(z, axis=0)
        datasaver.save_data("avg", avg)

        elapsed_time = time.perf_counter() - start_time
        print(f"Time: {elapsed_time: .5}s")
