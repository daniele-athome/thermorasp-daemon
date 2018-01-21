# -*- coding: utf-8 -*-
"""Sensors communication protocols."""

import importlib


class BaseSensorHandler:
    """Base interface for sensor handlers."""

    def __init__(self, address):
        self.address = address

    def read(self, sensor_type):
        raise NotImplementedError()


def get_sensor_handler(protocol: str, address: str) -> BaseSensorHandler:
    """Returns an appropriate sensor handler for the given protocol and address."""
    module = importlib.import_module('.'+protocol, __name__)
    if module:
        schemes = getattr(module, 'schemes')
        if schemes:
            scheme_part, address_part = address.split(':', 1)
            if scheme_part in schemes:
                handler_class = schemes[scheme_part]
                return handler_class(address_part)
