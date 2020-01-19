# -*- coding: utf-8 -*-
"""Application creator."""

from sanic import Sanic


class Application(Sanic):
    def __init__(self, name):
        Sanic.__init__(self, name)

    def new_topic(self, node_id):
        return '/'.join([
            self.config['BROKER_TOPIC'],
            self.config['DEVICE_ID'],
            node_id])


app = Application(__name__)

from . import controllers
from . import backend
