# -*- coding: utf-8 -*-
""" Module for handling all database models.

Notes:
    The models created with the inherited `Base` constant
    must be imported below the declaration for `Alembic`
    autogenerate to work.
"""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

from .sensors import Sensor, Reading
from .devices import Device
from .eventlog import EventLog
