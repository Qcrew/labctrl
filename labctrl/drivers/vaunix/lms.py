""" """

from __future__ import annotations

from ctypes import CDLL, c_int
from numbers import Real
from pathlib import Path

from labctrl.instrument import Instrument, ConnectionError
from labctrl.parameter import Parameter

DLL = CDLL(str(Path(__file__).parent / "lms.dll"))  # driver


class LabBrick(Instrument):
    """ """

    rf = Parameter(bounds=(bool, {0, 1}))

    min_frequency = Parameter()
    max_frequency = Parameter()
    _unit_frequency = 10.0  # LMS encodes frequency as an integer of 10Hz steps
    _to_frequency = lambda value: value * LabBrick._unit_frequency
    _from_frequency = lambda frequency: int(frequency / LabBrick._unit_frequency)
    _check_frequency = lambda value, lb: lb.min_frequency <= value <= lb.max_frequency
    frequency = Parameter(bounds=[Real, _check_frequency])

    min_power = Parameter()
    max_power = Parameter()
    _unit_power = 0.25  # LMS encodes power level as an integer of 0.25dB steps
    _to_power = lambda value: value * LabBrick._unit_power
    _from_power = lambda power: int(power / LabBrick._unit_power)
    _check_power = lambda value, lb: lb.min_power <= value <= lb.max_power
    power = Parameter(bounds=[Real, _check_power])

    def __init__(self, name: str, id: int, **parameters) -> None:
        """ """
        super().__init__(name, id, **parameters)
        DLL.fnLMS_SetTestMode(False)  # we are using actual hardware
        DLL.fnLMS_SetUseInternalRef(self._handle, False)  # use external 10MHz reference
        self.idle()

    def connect(self) -> None:
        """ """
        if self._handle is not None:  # close any existing connection
            try:
                self.disconnect()
            except ConnectionError:
                raise ConnectionError(f"please reconnect {self} at USB port") from None

        numdevices = DLL.fnLMS_GetNumDevices()
        deviceinfo = (c_int * numdevices)()
        DLL.fnLMS_GetDevInfo(deviceinfo)
        ids = [DLL.fnLMS_GetSerialNumber(deviceinfo[i]) for i in range(numdevices)]
        if self.id in ids:
            handle = deviceinfo[ids.index(self.id)]
            error = DLL.fnLMS_InitDevice(handle)
            if not error:  # 0 indicates successful device initialization
                self._handle = handle
                return
            raise ConnectionError(f"failed to open {self}")
        raise ConnectionError(f"could not find {self}")

    def idle(self):
        """ """
        self.rf = False

    def disconnect(self):
        """ """
        self.idle()
        status = DLL.fnLMS_CloseDevice(self._handle)
        if status != 0:  # non-zero return values indicate disconnection error
            raise ConnectionError(f"failed to close {self}")
        self._handle = None

    def _errorcheck(self, errorcode: int) -> None:
        """ """
        if errorcode:  # non-zero return values indicate error
            raise ConnectionError(f"got {errorcode = } from {self}")

    @rf.getter
    def rf(self) -> int:
        """ """
        return DLL.fnLMS_GetRF_On(self._handle)

    @rf.setter
    def rf(self, value: bool) -> None:
        """ """
        self._errorcheck(DLL.fnLMS_SetRFOn(self._handle, value))

    @min_frequency.getter(parser=_to_frequency)
    def min_frequency(self) -> float:
        """ """
        return DLL.fnLMS_GetMinFreq(self._handle)

    @max_frequency.getter(parser=_to_frequency)
    def max_frequency(self) -> float:
        """ """
        return DLL.fnLMS_GetMaxFreq(self._handle)

    @frequency.getter(parser=_to_frequency)
    def frequency(self) -> float:
        """ """
        return DLL.fnLMS_GetFrequency(self._handle)

    @frequency.setter(parser=_from_frequency)
    def frequency(self, value: Real) -> None:
        """ """
        self._errorcheck(DLL.fnLMS_SetFrequency(self._handle, value))

    @min_power.getter(parser=_to_power)
    def min_power(self) -> float:
        """ """
        return DLL.fnLMS_GetMinPwr(self._handle)

    @max_power.getter(parser=_to_power)
    def max_power(self) -> float:
        """ """
        return DLL.fnLMS_GetMaxPwr(self._handle)

    @power.getter(parser=_to_power)
    def power(self) -> float:
        """ """
        return DLL.fnLMS_GetAbsPowerLevel(self._handle)

    @power.setter(parser=_from_power)
    def power(self, value: Real) -> None:
        """ """
        self._errorcheck(DLL.fnLMS_SetPowerLevel(self._handle, value))
