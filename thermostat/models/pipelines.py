# -*- coding: utf-8 -*-
"""Models for behavior pipelines."""

from sqlalchemy import (
    Column, String, Integer, SmallInteger, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship, backref

from . import Base


class Pipeline(Base):
    __tablename__ = 'pipelines'

    # Pipeline id. Must be unique so it's the primary key
    id = Column(Integer, autoincrement=True, primary_key=True)

    # Pipeline information
    name = Column(String(100))
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean(), default=False, server_default=False)

    behaviors = relationship("Behavior", cascade="all, delete-orphan", order_by="Behavior.behavior_order")

    # Methods
    def __repr__(self):
        """ Show pipeline object info. """
        return '<Pipeline: {}>'.format(self.id)


class Behavior(Base):
    __tablename__ = 'pipeline_behaviors'

    # primary key
    pipeline_id = Column(Integer(), ForeignKey('pipelines.id'), primary_key=True)
    behavior_order = Column(SmallInteger(), primary_key=True, default=1, server_default=1)

    behavior_id = Column(String(50))

    config = Column(String(500), default='{}', server_default='{}')

    pipeline = relationship("Pipeline", backref=backref("behavior", cascade="all, delete-orphan"))
