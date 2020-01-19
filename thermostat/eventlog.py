# -*- coding: utf-8 -*-
"""The Sensor Manager."""

import sys
import datetime

from .database import scoped_session
from .models import EventLog


def init(database):
    return EventLogger(database)


class EventLogger(object):
    def __init__(self, database):
        self.database = database

    def event(self, level: str, source: str, name: str, description: str = None):
        with scoped_session(self.database) as session:
            vevent = EventLog()
            vevent.timestamp = datetime.datetime.now()
            vevent.level = level
            vevent.source = source
            vevent.name = name
            vevent.description = description
            session.add(vevent)

    def event_exc(self, level: str, source: str, name: str):
        import traceback
        e_type, e_value, e_tb = sys.exc_info()
        strerr1 = traceback.format_exception_only(e_type, e_value)[0][:-1]
        strerr = ''.join(traceback.format_exception(e_type, e_value, e_tb))
        self.event(level, source, name, strerr1 + "\n" + strerr)
