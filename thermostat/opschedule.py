# -*- coding: utf-8 -*-
"""The operating schedule."""

import asyncio
import logging
import datetime
import hbmqtt.client as mqtt_client

from . import app, sensorman
from .behaviors import get_behavior_handler

# TEST loggers
log = logging.getLogger("root")


class OperatingSchedule(object):

    def __init__(self, sensors: sensorman.SensorManager, schedule: dict):
        self.sensors = sensors
        self.schedule = schedule
        # the currently running behavior (BaseBehavior instance)
        self.behavior = None
        self.broker = mqtt_client.MQTTClient()

    async def startup(self):
        """Starts scheduling operations."""
        await self.broker.connect(app.broker_url)
        log.debug("Operating schedule connected to broker")

    async def shutdown(self):
        await self.broker.disconnect()

    async def timer(self):
        """Called by the backend when the timer ticks."""
        now = datetime.datetime.now()
        now_min = self.get_time_minutes(now.weekday(), now.hour, now.minute)
        log.debug("Current minute: {}".format(now_min))
        behavior = self.find_current_behavior(now_min)
        log.debug("Found current behavior: {}".format(behavior))

        # no behavior running or different from previous one
        if behavior is None or (self.behavior is not None and self.behavior.id != behavior['id']):
            self.behavior.shutdown()
            self.behavior = None

        if self.behavior is None:
            # new behavior to start!
            if behavior is not None:
                self.behavior = self.start_behavior(behavior)
        else:
            # behavior already running, wake it up
            self.behavior.timer()

    def start_behavior(self, bev_def):
        bev = get_behavior_handler(bev_def['name'], bev_def['config'])
        asyncio.ensure_future(self.subscribe_for_behavior(bev))
        bev.startup()
        return bev

    async def subscribe_for_behavior(self, bev):
        # TODO subscribe to sensors
        # TODO subscribe to devices
        pass

    def find_current_behavior(self, offset):
        candidate = None
        for bev in self.schedule['behaviors']:
            if bev['start_time'] <= offset < bev['end_time'] and \
                    (candidate is None or candidate['order'] <= bev['order']):
                candidate = bev
        return candidate

    @staticmethod
    def get_time_minutes(weekday, hour, minute):
        return (weekday * 24 * 60) + \
               (hour * 60) + \
               minute
