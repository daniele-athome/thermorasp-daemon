# -*- coding: utf-8 -*-
"""Models for behavior pipelines."""

from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship

from . import Base


class Pipeline(Base):
    __tablename__ = 'pipelines'

    # Pipeline id. Must be unique so it's the primary key
    id = Column(Integer, autoincrement=True, primary_key=True)

    # Pipeline information
    name = Column(String(100))
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean(), default=False)

    behaviors = relationship("Behavior")

    # Methods
    def __repr__(self):
        """ Show pipeline object info. """
        return '<Pipeline: {}>'.format(self.id)


class Behavior(Base):
    __tablename__ = 'pipeline_behaviors'

    # primary key
    pipeline_id = Column(Integer(), ForeignKey('pipelines.id'), primary_key=True)
    behavior_id = Column(String(50), primary_key=True)

    config = Column(String(500), default='{}')
