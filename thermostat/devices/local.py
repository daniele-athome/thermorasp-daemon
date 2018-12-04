# -*- coding: utf-8 -*-
"""Protocols for local devices (e.g. GPIO)."""

import importlib.util
try:
    importlib.util.find_spec('RPi.GPIO')
    import RPi.GPIO as GPIO
except ImportError:
    from fake_rpi.RPi import GPIO as GPIO


from . import BaseDeviceHandler
from ..models import eventlog


class MemoryOnOffDeviceHandler(BaseDeviceHandler):
    """A device handler that manages an ON/OFF switch in memory."""

    SUPPORTED_TYPES = ('boiler_on_off', )

    def __init__(self, device_id, device_type, protocol, address, name):
        BaseDeviceHandler.__init__(self, device_id, device_type, protocol, address, name)
        self.enabled = False

    async def control(self, data):
        if 'enabled' in data and data['enabled']:
            self.enabled = True
        else:
            self.enabled = False

        # TODO eventlog.event(eventlog.LEVEL_INFO, self.get_name(), 'device:control', 'enabled:%d' % self.enabled)
        await self.publish_state({'enabled': self.enabled})


class GPIOSwitchDeviceHandler(BaseDeviceHandler):
    """Raspberry device handler that goes ON/OFF through a GPIO."""

    SUPPORTED_TYPES = ('boiler_on_off', )

    def __init__(self, device_id, device_type, protocol, address, name):
        BaseDeviceHandler.__init__(self, device_id, device_type, protocol, address, name)
        self.pin = int(self.address[1])
        self.enabled = False

    def set_switch(self, enabled):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, enabled)
        self.enabled = enabled

    def startup(self):
        self.set_switch(False)

    def shutdown(self):
        self.set_switch(False)

    def control(self, *args, **kwargs):
        enabled = 'enabled' in kwargs and kwargs['enabled']
        self.set_switch(enabled)
        eventlog.event(eventlog.LEVEL_INFO, self.get_name(), 'device:control', 'enabled:%d' % enabled)
        return True

    def status(self, *args, **kwargs):
        return {'enabled': self.enabled}


class GPIO2SwitchDeviceHandler(GPIOSwitchDeviceHandler):
    """Raspberry device handler that goes ON/OFF through a GPIO, completely turning off the pin on disable."""

    SUPPORTED_TYPES = ('boiler_on_off', )

    def __init__(self, device_id, device_type, protocol, address, name):
        GPIOSwitchDeviceHandler.__init__(self, device_id, device_type, protocol, address, name)
        # start from a consistent state
        self.set_switch(True)
        self.set_switch(False)

    def set_switch(self, enabled):
        GPIO.setmode(GPIO.BCM)
        if enabled:
            GPIO.setup(self.pin, GPIO.OUT)
            GPIO.output(self.pin, False)
        else:
            GPIO.cleanup(self.pin)
        self.enabled = enabled


schemes = {
    'GPIOSW': GPIOSwitchDeviceHandler,
    'GPIO2SW': GPIO2SwitchDeviceHandler,
    'MEMSW': MemoryOnOffDeviceHandler,
}
