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

    id = Parameter(bounds=int)

    rf = Parameter(bounds=bool)

    check_frequency = lambda value, lb: lb.min_frequency <= value <= lb.max_frequency
    frequency = Parameter(bounds=[Real, check_frequency])

    check_power = lambda value, lb: lb.min_power <= value <= lb.max_power
    power = Parameter(bounds=[Real, check_power])

    def __init__(self, name: str, id: int, **parameters) -> None:
        """ """
        super().__init__(name, id, **parameters)
        DLL.fnLMS_SetTestMode(False)  # we are using actual hardware
        DLL.fnLMS_SetUseInternalRef(self._handle, False)  # use external 10MHz reference

    def connect(self) -> None:
        """ """
        if self._handle is not None:  # close any existing connection
            try:
                self.disconnect()
            except ConnectionError:
                raise ConnectionError(f"please reconnect {self} at USB port") from None

        numdevices = DLL.fnLMS_GetNumDevices()
        device_info = DLL.fnLMS_GetDevInfo((c_int * numdevices)())
        ids = [DLL.fnLMS_GetSerialNumber(device_info[i]) for i in range(numdevices)]
        if self.id in ids:
            handle = device_info[ids.index(self.id)]
            status = DLL.fnLMS_InitDevice(handle)
            if status == 0:  # 0 indicates successful device initialization
                self._handle = handle
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

    @rf.getter(parser=bool)
    def rf(self) -> bool:
        """ """
        return DLL.fnLMS_GetRF_On(self._handle)

    @rf.setter
    def rf(self, value: bool) -> None:
        """ """
        DLL.fnLMS_SetRFOn(self._handle, value)

    unit_frequency = 10.0  # LMS encodes frequency as an integer of 10Hz steps
    to_frequency = lambda value: value * unit_frequency
    from_frequency = lambda frequency: int(frequency / unit_frequency)

    @property
    def min_frequency(self) -> float:
        """ """
        return self.to_frequency(DLL.fnLMS_GetMinFreq(self._handle))

    @property
    def max_frequency(self) -> float:
        """ """
        return self.to_frequency(DLL.fnLMS_GetMaxFreq(self._handle))

    @frequency.getter(parser=to_frequency)
    def frequency(self) -> float:
        """ """
        return DLL.fnLMS_GetFrequency(self._handle)

    @frequency.setter(parser=from_frequency)
    def frequency(self, value: Real) -> None:
        """ """
        self._errorcheck(DLL.fnLMS_SetFrequency(self._handle, value))

    unit_power = 0.25  # LMS encodes power level as an integer of 0.25dB steps
    to_power = lambda value: value * unit_power
    from_power = lambda power: int(power / unit_power)

    @property
    def min_power(self) -> float:
        """ """
        return self.to_power(DLL.fnLMS_GetMinPwr(self._handle))

    @property
    def max_power(self) -> float:
        """ """
        return self.to_power(DLL.fnLMS_GetMaxPwr(self._handle))

    @power.getter(parser=to_power)
    def power(self) -> float:
        """ """
        return DLL.fnLMS_GetAbsPowerLevel(self._handle)

    @power.setter(parser=from_power)
    def power(self, value: Real) -> None:
        """ """
        self._errorcheck(DLL.fnLMS_SetPowerLevel(self._handle, value))
