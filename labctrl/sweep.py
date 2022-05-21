"""
This module contains utilities to configure independent variable sweeps for running experiments. 
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Sweep:
    """ """

    points: list[float] = None  # discrete sweep points
    sweeps: tuple[Sweep] = None  # sweep composed of other sweeps

    start: float = None  # sweep start point
    stop: float = None  # sweep end point
    step: float = None  # distance between two sweep points
    endpoint: bool = True  # whether or not to include end point in sweep
    num: int = None  # number of points in sweep
    kind: str = "lin"  # "lin" or "log" (base 10) sweep

    save: bool = True  # whether this Sweep will be saved to datafile by the DataSaver
    dtype: str = "f4"  # dtype used to save sweep points dataset
    units: str | None = None  # units attribute sweep points dataset is saved with
    name: str | None = None  # name of sweep variable

    @property
    def metadata(self) -> dict[str, float | int | str]:
        """ """
        x = ("points", "sweeps", "save")  # excluded keys
        return {k: v for k, v in self.__dict__.items() if k not in x and v is not None}

    @property
    def data(self) -> np.ndarray:
        """
        order of precedence when evaluating sweep specification:
        1. sweep with discrete points
        2. sweep composed of other sweeps
        3. sweep with start, stop, step
        4. lin/log sweep with start, stop, num
        """
        if self.points is not None:
            return np.array(self.points)
        elif self.sweeps is not None:
            return np.concatenate([sweep.data for sweep in self.sweeps])
        elif not None in (self.start, self.stop):
            if self.step is not None:
                if self.endpoint:
                    return np.arange(self.start, self.stop + self.step / 2, self.step)
                else:
                    return np.arange(self.start, self.stop - self.step / 2, self.step)
            elif self.num is not None:
                if self.kind == "lin":
                    return np.linspace(self.start, self.stop, self.num, self.endpoint)
                elif self.kind == "log":
                    return np.logspace(self.start, self.stop, self.num, self.endpoint)

        raise ValueError(f"Underspecified sweep: {self}.")

    @property
    def length(self) -> int:
        """ """
        return len(self.data)

    @property
    def shape(self) -> tuple[int]:
        """ """
        return (self.length,)
