# -*- coding: utf-8 -*-
"""Models for sensors and sensor readings."""

from sqlalchemy import (
    Column, String, Integer, DateTime
)

from . import Base
from .. import app
from ..database import scoped_session


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


class Reading(Base):
    __tablename__ = 'sensor_readings'

    # Sensor id, type and timestamp are the key
    sensor_id = Column(String(255), primary_key=True)
    sensor_type = Column(String(20), primary_key=True)
    timestamp = Column(DateTime(), primary_key=True)

    # Reading contents
    unit = Column(String(20))
    value = Column(String(255))

    # Methods
    def __repr__(self):
        """ Show sensor object info. """
        return '<Reading: {}@{}>'.format(self.id, self.timestamp)


def store_reading(myapp, sensor_id, sensor_type, timestamp, unit, value):
    with scoped_session(myapp.database) as session:
        reading = Reading()
        reading.sensor_id = sensor_id
        reading.sensor_type = sensor_type
        reading.timestamp = timestamp
        reading.unit = unit
        reading.value = value
        session.add(reading)
