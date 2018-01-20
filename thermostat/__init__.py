# -*- coding: utf-8 -*-
"""Application creator."""

from sanic import Sanic

app = Sanic(__name__)

from . import backend
from . import controllers
