# -*- coding: utf-8 -*-

from sanic import Sanic

app = Sanic(__name__)

from . import controllers
