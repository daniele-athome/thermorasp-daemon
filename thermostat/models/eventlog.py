# -*- coding: utf-8 -*-
"""Models for logged events."""

import sys
import datetime

from sqlalchemy import (
    Column, String, Integer, DateTime
)

from . import Base
from .. import app
from ..database import scoped_session


# An information event.
LEVEL_INFO = 'info'
# Something that should get the user's attention.
LEVEL_WARNING = 'warning'
# An unexpected error occured.
LEVEL_ERROR = 'error'
# Something happen that might cause danger.
LEVEL_DANGER = 'danger'


class EventLog(Base):
    __tablename__ = 'event_log'

    # Event Id.
    id = Column(Integer(), autoincrement=True, primary_key=True)

    timestamp = Column(DateTime())
    level = Column(String(30))
    source = Column(String(100))
    name = Column(String(100))
    description = Column(String(300), nullable=True)

    # Methods
    def __repr__(self):
        """ Show event object info. """
        return '<EventLog: {}>'.format(self.id)


def event(level, source, name, description=None):
    with scoped_session(app.database) as session:
        vevent = EventLog()
        vevent.timestamp = datetime.datetime.now()
        vevent.level = level
        vevent.source = source
        vevent.name = name
        vevent.description = description
        session.add(vevent)


def event_exc(level, source, name):
    import traceback
    e_type, e_value, e_tb = sys.exc_info()
    strerr1 = traceback.format_exception_only(e_type, e_value)[0][:-1]
    strerr = ''.join(traceback.format_exception(e_type, e_value, e_tb))
    event(level, source, name, strerr1 + "\n" + strerr)
