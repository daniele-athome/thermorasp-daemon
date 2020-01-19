# -*- coding: utf-8 -*-
"""Models for logged events."""

from sqlalchemy import (
    Column, String, Integer, DateTime
)

from . import Base


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
