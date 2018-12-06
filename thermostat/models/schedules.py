# -*- coding: utf-8 -*-
"""Models for schedules."""

from sqlalchemy import (
    Column, String, Integer, SmallInteger, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship, backref

from . import Base


class Schedule(Base):
    __tablename__ = 'schedules'

    # Schedule id. Must be unique so it's the primary key
    id = Column(Integer, autoincrement=True, primary_key=True)

    # Schedule information
    name = Column(String(100))
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean(), default=False, server_default='0')

    behaviors = relationship("Behavior", cascade="all, delete-orphan", order_by="Behavior.behavior_order")

    # Methods
    def __repr__(self):
        """ Show schedule object info. """
        return '<Schedule: {}>'.format(self.id)


class Behavior(Base):
    __tablename__ = 'schedule_behaviors'

    # Behavior id. Must be unique so it's the primary key
    id = Column(Integer, autoincrement=True, primary_key=True)

    schedule_id = Column(Integer(), ForeignKey('schedules.id'))
    behavior_name = Column(String(100))

    behavior_order = Column(SmallInteger(), default=1, server_default='1')
    start_time = Column(SmallInteger())
    end_time = Column(SmallInteger())
    config = Column(String(500), default='{}', server_default='{}')

    sensors = relationship("BehaviorSensor", cascade="all, delete-orphan")
    devices = relationship("BehaviorDevice", cascade="all, delete-orphan")

    # Methods
    def __repr__(self):
        """ Show behavior object info. """
        return '<Behavior: #{} {}/{}>'.format(self.id, self.schedule_id, self.behavior_name)


class BehaviorSensor(Base):
    __tablename__ = 'behavior_sensors'

    # primary key
    behavior_id = Column(Integer(), ForeignKey('schedule_behaviors.id'), primary_key=True)
    sensor_id = Column(String(255), primary_key=True)


class BehaviorDevice(Base):
    __tablename__ = 'behavior_devices'

    # primary key
    behavior_id = Column(Integer(), ForeignKey('schedule_behaviors.id'), primary_key=True)
    device_id = Column(String(100), primary_key=True)
