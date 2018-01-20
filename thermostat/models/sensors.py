# -*- coding: utf-8 -*-
"""Model for a sensor."""

from sqlalchemy import (
    Column, String, Integer
)

from . import Base


class Sensor(Base):
    __tablename__ = 'sensors'

    # Sensor data mode
    # Active: sensor sends to server
    DATA_MODE_ACTIVE = 0
    # Passive: server polls the sensor
    DATA_MODE_PASSIVE = 1

    # Sensor status
    STATUS_UNKNOWN = 0
    STATUS_REGISTERED = 1
    STATUS_ACTIVE = 2
    STATUS_INACTIVE = 3

    # Sensor id. Must be unique so it's the primary key
    id = Column(String(255), primary_key=True)

    # Sensor contact information
    protocol = Column(String(20), default='local')
    address = Column(String(255), nullable=True)

    # Sensor attributes
    sensor_type = Column(String(20))
    data_mode = Column(Integer(), default=DATA_MODE_ACTIVE)

    # Sensor status
    status = Column(Integer(), default=STATUS_UNKNOWN)

    # Methods
    def __repr__(self):
        """ Show sensor object info. """
        return '<Sensor: {}>'.format(self.id)
