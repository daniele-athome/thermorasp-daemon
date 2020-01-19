# -*- coding: utf-8 -*-
"""Utilities."""

import datetime


def is_past_then(dt, seconds: int):
    """Return true if the given datetime is older than seconds ago."""
    if type(dt) is str:
        try:
            dt = datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            dt = datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S')
    return (datetime.datetime.now() - dt).total_seconds() > seconds
