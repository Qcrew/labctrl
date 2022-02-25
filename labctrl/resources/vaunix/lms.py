""" """

from __future__ import annotations

from ctypes import CDLL, c_int
from numbers import Real
from pathlib import Path

from labctrl.instrument import Instrument, ConnectionError
from labctrl.parameter import Parameter

DLL = CDLL(str(Path(__file__).parent / "lms.dll"))  # driver

_UNIT_FREQUENCY = 10.0
_UNIT_POWER = 0.25


def _to_frequency(value: int) -> float:
    """From LMS coded frequency to actual frequency. LMS encodes frequency as an integer of 10Hz steps"""
    return value * _UNIT_FREQUENCY


def _from_frequency(value: int) -> int:
    """From frequency to LMS coded frequency. LMS encodes frequency as an integer of 10Hz steps"""
    return int(value / _UNIT_FREQUENCY)


def _bound_frequency(value: float, lms: LMS) -> bool:
    """ """
    return lms.min_frequency <= value <= lms.max_frequency


def _to_power(value: int) -> float:
    """From LMS coded power to actual power. LMS encodes power level as an integer of 0.25dB steps"""
    return value * _UNIT_POWER


def _from_power(value: float) -> int:
    """From actual power to LMS coded power. LMS encodes power level as an integer of 0.25dB steps"""
    return int(value / _UNIT_POWER)


def _bound_power(value: float, lms: LMS) -> bool:
    """ """
    return lms.min_power <= value <= lms.max_power


class LMS(Instrument):
    """ """

    rf = Parameter(bounds=(bool, {0, 1}))
    pll = Parameter(bounds=bool)
    frequency = Parameter(bounds=[Real, _bound_frequency])
    power = Parameter(bounds=[Real, _bound_power])

    def __init__(self, name: str, id: int, **parameters) -> None:
        """ """
        self._handle = None
        super().__init__(name, id, **parameters)
        DLL.fnLMS_SetTestMode(False)  # we are using actual hardware
        DLL.fnLMS_SetUseInternalRef(self._handle, False)  # use external 10MHz reference
        self.rf = False

    @property
    def status(self) -> bool:
        """ """
        return DLL.fnLMS_GetDeviceStatus(self._handle) > 0

    def connect(self) -> None:
        """ """
        # close any existing connection
        if self._handle is not None:
            self.disconnect()

        numdevices = DLL.fnLMS_GetNumDevices()
        deviceinfo = (c_int * numdevices)()
        DLL.fnLMS_GetDevInfo(deviceinfo)
        ids = [DLL.fnLMS_GetSerialNumber(deviceinfo[i]) for i in range(numdevices)]
        if self.id in ids:  # LMS is found, try opening it
            handle = deviceinfo[ids.index(self.id)]
            error = DLL.fnLMS_InitDevice(handle)
            if not error:  # 0 indicates successful device initialization
                self._handle = handle
                return
            raise ConnectionError(f"Failed to connect {self}")
        raise ConnectionError(f"{self} is not available for connection")

    def disconnect(self):
        """ """
        self.rf = False
        self._errorcheck(DLL.fnLMS_CloseDevice(self._handle))
        self._handle = None

    def _errorcheck(self, errorcode: int) -> None:
        """Only if we get bad values during setting params"""
        if errorcode:  # non-zero return values indicate error
            message = f"Got {errorcode = } from {self}, please check the USB connection"
            raise ConnectionError(message)

    @rf.getter
    def rf(self) -> int:
        """The conditional is necessary for parameter value bounding..."""
        value = DLL.fnLMS_GetRF_On(self._handle)
        return bool(value) if value in (0, 1) else value

    @rf.setter
    def rf(self, value: bool) -> None:
        """ """
        self._errorcheck(DLL.fnLMS_SetRFOn(self._handle, value))

    @pll.getter
    def pll(self) -> bool:
        """ The hex code for PLL_LOCKED flag is 0x00000040 in vnx_LMS_api.h """
        return DLL.fnLMS_GetDeviceStatus(self._handle) == 64

    @property
    def min_frequency(self) -> float:
        """ """
        return _to_frequency(DLL.fnLMS_GetMinFreq(self._handle))

    @property
    def max_frequency(self) -> float:
        """ """
        return _to_frequency(DLL.fnLMS_GetMaxFreq(self._handle))

    @frequency.getter
    def frequency(self) -> float:
        """ """
        return _to_frequency(DLL.fnLMS_GetFrequency(self._handle))

    @frequency.setter
    def frequency(self, value: Real) -> None:
        """ """
        parsedvalue = _from_frequency(value)
        self._errorcheck(DLL.fnLMS_SetFrequency(self._handle, parsedvalue))

    @property
    def min_power(self) -> float:
        """ """
        return _to_power(DLL.fnLMS_GetMinPwr(self._handle))

    @property
    def max_power(self) -> float:
        """ """
        return _to_power(DLL.fnLMS_GetMaxPwr(self._handle))

    @power.getter
    def power(self) -> float:
        """ """
        return _to_power(DLL.fnLMS_GetAbsPowerLevel(self._handle))

    @power.setter
    def power(self, value: Real) -> None:
        """ """
        parsedvalue = _from_power(value)
        self._errorcheck(DLL.fnLMS_SetPowerLevel(self._handle, parsedvalue))
