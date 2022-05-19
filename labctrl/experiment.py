"""
Specifies interface for Experiments which take in run parameters set by the user and Resources from a Stage, bring about some interaction between Resources, generate data for plotting and saving/loading to disk, and perform analysis which may lead to some characterization (i.e. gain in knowledge) of some Resource(s) parameters
"""

from collections import Counter
import contextlib
import dataclasses as dc
from datetime import datetime
from typing import Any

from labctrl.datasaver import DataSaver
from labctrl.dataset import Dataset
from labctrl.logger import logger
from labctrl.parameter import parametrize
from labctrl.plotter import LivePlotter
from labctrl.resource import Resource
from labctrl.settings import Settings
from labctrl.sweep import Sweep


class DatasetSpecificationError(Exception):
    """ """


class SweepSpecificationError(Exception):
    """ """


class ResourceSpecificationError(Exception):
    """ """


class ExperimentMetaclass(type):
    """ """

    def __init__(cls, name, bases, kwds) -> None:
        """ """
        super().__init__(name, bases, kwds)

        annotations = cls.__annotations__
        cls.resourcespec = [v for v in annotations.values() if issubclass(v, Resource)]
        cls.dataspec: dict[str, Dataset] = parametrize(cls, filter=Dataset)
        cls.sweepspec: dict[str, Sweep] = parametrize(cls, filter=Sweep)

    def __repr__(cls) -> str:
        """ """
        return f"<class '{cls.__name__}'>"


class Experiment(metaclass=ExperimentMetaclass):
    """
    Base class. Responsible for resource check and preparing datasets for saving and plotting.

    To write child classes, inherit Experiment, use class annotations to declare Resource spec, use class variables to declare Dataset(s), Sweep(s), Parameter(s). The names of these variables may be passed as arguments to __init__().
    """

    # indicate Resources used in the Experiment as annotations here, e.g.
    # instrument: Resource

    # initialize all parameters that can be swept, e.g.
    # including those which might not be swept during runtime
    # set attributes "units" and "dtype" only as these do not change at runtime
    # frequency = Sweep(units="Hz")
    # power = Sweep(units="dBm")

    # initialize all Datasets this Experiment will generate (both raw and derived)
    # set attributes "axes", "units", "dtype", "chunks", "save", "plot" here
    # for plotted datasets, set "errfn" and "fitfn" too if needed
    # for derived datasets, set "datafn" too
    # whether or not the datasets are plotted / saved can be changed in run()
    # I = Dataset(axes=(power, frequency), units="AU")
    # signal: Dataset(axes=(power, frequency), units="AU", save=False, plot=True)
    # the number of repetitions (N) dimension will be added to the dataset at runtime
    # any uninitialized sweeps will also be removed from the axes at runtime

    def __init__(self, N: int, wait: float) -> None:
        """must be called by subclasses"""
        self.name = self.__class__.__name__
        self.N = N  # number of repetitions
        self.wait = wait  # time between 2 repetitions
        self._filepath = None

        # these are set by run()
        self._sweeps: dict[str, Sweep] = {}
        self._datasets: dict[str, Dataset] = {}
        self.datasaver: DataSaver = None
        self.plotter: LivePlotter = None

    def __repr__(self) -> str:
        """ """
        return f"Experiment '{self.name}'"

    def _check_resources(self) -> None:
        """ """
        spec = [v.__class__ for v in self.__dict__.values() if isinstance(v, Resource)]
        spec = dict(Counter(spec))
        expectedspec = dict(Counter(self.__class__.resourcespec))
        if spec != expectedspec:
            message = f"Expect resource specification {expectedspec}, got {spec}."
            logger.error(message)
            raise ResourceSpecificationError(message)

    def _prepare_sweeps(self) -> None:
        """sweep dtype and units will be those declared in sweepspec.
        each name in sweepspec must be set as self attribute upon initialization
        """
        for name, sweep in self.__class__.sweepspec.items():
            sweep.name = name  # to identify sweep name from sweep object later on
            try:
                value = self.__dict__[name]
            except KeyError:
                message = (
                    f"Name '{name}' is declared as a Sweep variable of {self}"
                    f" but is not set as an attribute."
                )
                logger.error(message)
                raise SweepSpecificationError(message) from None
            else:
                if isinstance(value, Sweep):
                    changes = {"dtype": sweep.dtype, "units": sweep.units, "name": name}
                    value = dc.replace(value, **changes)
                    self._sweeps[name] = value
        logger.debug(f"Found {len(self._sweeps)} sweep(s)!")

    def _prepare_datasets(self) -> None:
        """
        Add an "N" dimension to axes if N > 1
        Remove dimension from axes if not a sweep
        """
        sweeps = self.__class__.sweepspec.values()
        for name, dataset in self.__class__.dataspec.items():
            dataset.name = name  # to identify dataset name from dataset object later on
            axes = {} if self.N > 1 else {"N": self.N}
            for sweep in dataset.axes:
                if sweep in sweeps:
                    axes[sweep.name] = self._sweeps[sweep.name]
                else:
                    message = (
                        f"Invalid {sweep = } declared in Dataset {name} 'axes'. "
                        f"Axis must a pre-defined class variable 'Sweep'."
                    )
                    logger.error(message)
                    raise DatasetSpecificationError(message) from None
            dataset = dc.replace(dataset, axes=axes)
            setattr(self, name, dataset)  # used to save/plot datasets in sequence()
            self._datasets[name] = dataset
        logger.debug(f"Found {len(self._datasets)} dataset(s)!")

    def snapshot(self) -> dict[str, Any]:
        """
        snapshot includes instance attributes that do not start with "_" are are not instances of excluded classes - Resource, Sweep, Dataset, DataSaver, LivePlotter
        """
        excluded = (Resource, Sweep, Dataset, DataSaver, LivePlotter)
        snapshot = {}
        for name, value in self.__dict__.items():
            if not isinstance(value, excluded) and not name.startswith("_"):
                snapshot[name] = value
        return snapshot

    @property
    def metadata(self) -> dict[str | None, dict[str, Any]]:
        """ """
        resources = [v for v in self.__dict__.values() if isinstance(v, Resource)]
        metadata = {resource.name: resource.snapshot() for resource in resources}
        return {**metadata, None: self.snapshot()}

    @property
    def filepath(self) -> str:
        """ """
        if self._filepath is None:
            date, time = datetime.now().strftime("%Y%m%d %H%M%S").split()
            datafolder = Settings().datafolder
            self._filepath = datafolder + f"/{date}/{time}_{self.name}.h5"
        return self._filepath

    def run(
        self, save: tuple[Dataset] | None = None, plot: tuple[Dataset] | None = None
    ):
        """
        checks resources, prepares sweeps and datasets, sets which datasets to save/plot, enters context of datasaver and plotter/
        if save/plot are empty tuples, do not save/plot any dataset! if they are None, then we defer to the save/plot flags specified for datasets in the class definition. if they are not empty tuples, then we only save/plot the specified datasets.
        """
        self._check_resources()
        self._prepare_sweeps()
        self._prepare_datasets()
        datasets = self._datasets.values()

        savelist = (dataset.name for dataset in save) if save else ()
        plotlist = (dataset.name for dataset in plot) if plot else ()
        for dataset in datasets:
            dataset.save = dataset.name in savelist
            dataset.plot = dataset.name in plotlist

        do_save = not all(dataset.save for dataset in datasets)
        do_plot = not all(dataset.plot for dataset in datasets)
        with contextlib.ExitStack() as stack:
            if do_save:
                datasaver = DataSaver(self.filepath, *datasets)
                self.datasaver = stack.enter_context(datasaver)
                self.datasaver.save_metadata(self.metadata)
            if do_plot:
                plotter = LivePlotter(*datasets)
                self.plotter = stack.enter_context(plotter)
            logger.debug(f"Set up dataset saving and plotting! Running sequence...")
            self.sequence()

    def sequence(self) -> None:
        """
        the experimental sequence called by run(). in it, you can do
        ** generate your expt data, know what pos to insert it in **
        self.datasaver.save(self.<dataset_name>, data, pos)
        self.datasaver.save(self.<sweep_name>, data)
        self.plotter.plot(self.<dataset_name>, data)
        """
        raise NotImplementedError("Subclass(es) must implement sequence()!")
