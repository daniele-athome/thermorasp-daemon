# -*- coding: utf-8 -*-
"""The Sensor Manager."""

from sqlalchemy.orm.exc import NoResultFound

from . import devices
from .database import scoped_session
from .models import Device


class DeviceManager(object):

    def __init__(self, database):
        self.database = database
        self.devices = {}
        self._init()

    def __getitem__(self, item):
        return self.devices[item]

    def values(self):
        return self.devices.values()

    def _init(self):
        with scoped_session(self.database) as session:
            stmt = Device.__table__.select()
            for d in session.execute(stmt):
                self._register(d['id'], d['device_type'], d['protocol'], d['address'], d['name'])

    def _register(self, device_id, device_type, protocol, address, name):
        """Creates a new device and stores the instance in the internal collection."""
        if device_id in self.devices:
            self._unregister(device_id)

        dev_instance = devices.get_device_handler(device_id, device_type, protocol, address, name)
        self.devices[device_id] = dev_instance
        dev_instance.startup()

    def _unregister(self, device_id):
        self.devices[device_id].shutdown()
        del self.devices[device_id]

    def register(self, device_id, protocol, address, device_type, name):
        with scoped_session(self.database) as session:
            device = Device()
            device.id = device_id
            device.name = name
            device.protocol = protocol
            device.address = address
            device.device_type = device_type
            device = session.merge(device)
            # will also unregister old device if any
            self._register(device.id, device.device_type, device.protocol, device.address, device.name)

    def unregister(self, device_id):
        try:
            self._unregister(device_id)
            with scoped_session(self.database) as session:
                device = session.query(Device).filter(Device.id == device_id).one()
                session.delete(device)
            return True
        except (NoResultFound, KeyError):
            return False
