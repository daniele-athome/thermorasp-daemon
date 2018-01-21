# -*- coding: utf-8 -*-
"""Protocols for local devices (e.g. GPIO)."""

import importlib.util
try:
    importlib.util.find_spec('RPi.GPIO')
    import RPi.GPIO as GPIO
except ImportError:
    from fake_rpi.RPi import GPIO as GPIO


from . import BaseDeviceHandler
from ..errors import NotSupportedError


class MemoryOnOffDeviceHandler(BaseDeviceHandler):
    """A device handler that manages an ON/OFF switch in memory."""

    SUPPORTED_TYPES = ('boiler_on_off', )

    def __init__(self, device_id, address):
        BaseDeviceHandler.__init__(self, device_id, address)
        self.enabled = False

    def control(self, device_type, *args, **kwargs):
        if device_type not in self.SUPPORTED_TYPES:
            raise NotSupportedError('Device type not supported.')

        print(kwargs)
        if 'enabled' in kwargs and kwargs['enabled']:
            self.enabled = True
        else:
            self.enabled = False
        return True

    def status(self, device_type, *args, **kwargs):
        if not device_type:
            device_type = 'boiler_on_off'
        elif device_type not in self.SUPPORTED_TYPES:
            raise NotSupportedError('Device type not supported.')

        if self.enabled:
            return {device_type: 'ON'}
        else:
            return {device_type: 'OFF'}


class GPIOSwitchDeviceHandler(BaseDeviceHandler):
    """Raspberry device handler that goes ON/OFF through a GPIO."""

    SUPPORTED_TYPES = ('boiler_on_off', )

    def __init__(self, device_id, address):
        BaseDeviceHandler.__init__(self, device_id, address)
        self.pin = int(address)
        self.enabled = False
        self.set_switch(False)

    def set_switch(self, enabled):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, enabled)
        self.enabled = enabled

    def control(self, device_type, *args, **kwargs):
        if device_type not in self.SUPPORTED_TYPES:
            raise NotSupportedError('Device type not supported.')

        enabled = 'enabled' in kwargs and kwargs['enabled']
        self.set_switch(enabled)
        return True

    def status(self, device_type, *args, **kwargs):
        if not device_type:
            device_type = 'boiler_on_off'
        elif device_type not in self.SUPPORTED_TYPES:
            raise NotSupportedError('Device type not supported.')

        if self.enabled:
            return {device_type: 'ON'}
        else:
            return {device_type: 'OFF'}


schemes = {
    'GPIOSW': GPIOSwitchDeviceHandler,
    'MEMSW': MemoryOnOffDeviceHandler,
}
