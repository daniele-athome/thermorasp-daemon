# -*- coding: utf-8 -*-
"""Models for managed devices."""

from sqlalchemy import (
    Column, String
)

from . import Base


class Device(Base):
    __tablename__ = 'devices'

    # Device id. Must be unique so it's the primary key
    id = Column(String(100), primary_key=True)
    name = Column(String(255))

    # Device contact information
    protocol = Column(String(20), default='local')
    address = Column(String(255), nullable=True)

    # Device attributes
    device_type = Column(String(20))

    # Methods
    def __repr__(self):
        """ Show device object info. """
        return '<Device: {}>'.format(self.id)
