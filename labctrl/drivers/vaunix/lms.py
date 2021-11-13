""" """

from typing import Any

from labctrl.instrument import Instrument, InstrumentConnectionError
from labctrl.parametrizer import Param

FREQ_UNIT = 10.0  # LMS encodes frequency as an integer of 10Hz steps
POW_UNIT = 0.25  # LMS encodes power level as an integer of 0.25dB steps


class LMSSignalGenerator(Instrument):
    """ """

    frequency = Parameter(
        bounds=lambda handle, value: VNX.fnLMS_GetMinFreq(handle) * FREQ_UNIT
        <= value
        <= VNX.fnLMS_GetMaxFreq(handle) * FREQ_UNIT,
        getter=None,
        setter=None,
        parser=float,
    )

    # power = Parameter(bounds=, getter=, setter=, parser=float)

    rf = Parameter(
        bounds={True, False},
        getter=VNX.fnLMS_GetRF_On,
        setter=VNX.fnLMS_SetRFOn,
        parser=bool,
    )

    def __init__(self, name: str, id: Any, **parameters) -> None:
        """ """
        super().__init__(name, id ** parameters)
        VNX.fnLMS_SetTestMode(False)  # we are using actual hardware
        VNX.fnLMS_SetUseInternalRef(self._handle, False)  # use external 10MHz reference

    def connect(self) -> int:
        """ """
        num_devices = VNX.fnLMS_GetNumDevices()
        device_info = VNX.fnLMS_GetDevInfo((ctypes.c_int * num_devices)())
        ids = [VNX.fnLMS_GetSerialNumber(device_info[i]) for i in range(num_devices)]
        if self.id in ids:
            device_handle = device_info[ids.index(self.id)]
            status_code = VNX.fnLMS_InitDevice(device_handle)
            if status_code == 0:  # 0 indicates successful device initialization
                return device_handle
            raise InstrumentConnectionError(f"Failed to open {self}")
        raise InstrumentConnectionError(f"Could not find {self}")

    def disconnect(self):
        """ """
        self.rf = False  # turn off RF
        status_code = VNX.fnLMS_CloseDevice(self._handle)
        if status_code != 0:  # non-zero return values indicate disconnection error
            raise InstrumentConnectionError(f"Failed to close {self}")
