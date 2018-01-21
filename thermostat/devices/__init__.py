# -*- coding: utf-8 -*-
"""Devices communication protocols."""

import importlib

from .. import app
from ..database import scoped_session
from ..models.devices import Device


# the singleton device instances are here (device_id: instance)
device_instances = {}


class BaseDeviceHandler:
    """Base interface for device handlers."""

    # subclasses must define SUPPORTED_TYPES with the list of supported device types
    SUPPORTED_TYPES = ()

    def __init__(self, device_id, address):
        self.device_id = device_id

    def control(self, device_type, *args, **kwargs):
        """Generic control interface. Implementation-dependent."""
        raise NotImplementedError()

    def status(self, device_type, *args, **kwargs):
        """Generic status reading interface. Implementation-dependent."""
        raise NotImplementedError()

    def is_supported(self, device_type):
        return device_type in self.SUPPORTED_TYPES


def init():
    """Initializes device instances from registered devices storage."""
    with scoped_session(app.database) as session:
        stmt = Device.__table__.select()
        for d in session.execute(stmt):
            register_device(d['id'], d['protocol'], d['address'])


def register_device(device_id, protocol, address):
    """Creates a new device and stores the instance in the internal collection."""
    dev_instance = _get_device_handler(device_id, protocol, address)
    device_instances[device_id] = dev_instance


def unregister_device(device_id):
    """Removes a registered device from the internal collection."""
    try:
        del device_instances[device_id]
    except KeyError:
        pass


def _get_device_handler(device_id: str, protocol: str, address: str) -> BaseDeviceHandler:
    """Returns an appropriate device handler for the given protocol and address."""
    module = importlib.import_module('.'+protocol, __name__)
    if module:
        schemes = getattr(module, 'schemes')
        if schemes:
            scheme_part, address_part = address.split(':', 1)
            if scheme_part in schemes:
                handler_class = schemes[scheme_part]
                return handler_class(device_id, address_part)


def get_device(device_id: str) -> BaseDeviceHandler:
    """Returns the device handler for the given device ID."""
    return device_instances[device_id]
