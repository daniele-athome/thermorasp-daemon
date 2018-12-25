# -*- coding: utf-8 -*-
"""Models for sensors and sensor readings."""

from sqlalchemy import (
    Column, String, Integer, DateTime, text, column
)
from sqlalchemy.orm.exc import NoResultFound

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
    data_mode = Column(Integer(), default=DATA_MODE_ACTIVE)  # deprecated?
    icon = Column(String(50), nullable=True)

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
        return '<Reading: {}@{}>'.format(self.sensor_id, self.timestamp)


def get_last_readings(session, modifier='-10 minutes', sensor_type=None):
    # FIXME use SQLAlchemy
    params = {'modifier': modifier}
    if sensor_type:
        add_query = 'sensor_type = :sensor_type and'
        params['sensor_type'] = sensor_type
    else:
        add_query = ''

    return session.query(Reading).from_statement(text("select r.sensor_id sensor_id, r.sensor_type sensor_type, \
        r.timestamp timestamp, r.unit unit, r.value value \
        from sensor_readings r join \
        (select sensor_id, sensor_type, max(timestamp) timestamp from sensor_readings \
        where "+add_query+" timestamp > datetime('now', :modifier) \
        group by sensor_id, sensor_type) as rmax \
        on r.sensor_id = rmax.sensor_id and r.sensor_type = rmax.sensor_type and r.timestamp = rmax.timestamp \
        order by timestamp desc").bindparams(**params).columns(
        column('sensor_id', Integer),
        column('sensor_type', String),
        column('timestamp', DateTime),
        column('unit', String),
        column('value', String)
        )).all()


def is_active_sensor(session, sensor_id):
    """Return true if the given sensor is registered as an active sensor."""
    return session.query(Sensor).filter(Sensor.id == sensor_id).count() == 1
