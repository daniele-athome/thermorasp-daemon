# -*- coding: utf-8 -*-
"""Devices communication protocols."""

import importlib

from ..errors import NotSupportedError


class BaseDeviceHandler(object):
    """Base interface for device handlers."""

    # subclasses must define SUPPORTED_TYPES with the list of supported device types
    SUPPORTED_TYPES = ()

    def __init__(self, device_id, device_type, protocol, address):
        self.id = device_id
        self.type = device_type
        self.protocol = protocol
        self.address = address.split(':', 1)
        if self.type not in self.SUPPORTED_TYPES:
            raise NotSupportedError('Device type not supported.')

    def startup(self):
        """Called on startup/registration."""
        raise NotImplementedError()

    def shutdown(self):
        """Called on shutdown/unregistration."""
        raise NotImplementedError()

    def control(self, *args, **kwargs):
        """Generic control interface. Implementation-dependent."""
        raise NotImplementedError()

    def status(self, *args, **kwargs):
        """Generic status reading interface. Implementation-dependent."""
        raise NotImplementedError()

    def is_supported(self, device_type):
        return device_type in self.SUPPORTED_TYPES

    def get_name(self):
        return 'device:' + self.id


def get_device_handler(device_id: str, device_type: str, protocol: str, address: str) -> BaseDeviceHandler:
    """Returns an appropriate device handler for the given protocol and address."""
    module = importlib.import_module('.'+protocol, __name__)
    if module:
        schemes = getattr(module, 'schemes')
        if schemes:
            scheme_part, address_part = address.split(':', 1)
            if scheme_part in schemes:
                handler_class = schemes[scheme_part]
                return handler_class(device_id, device_type, protocol, address)
