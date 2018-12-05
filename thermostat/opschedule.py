# -*- coding: utf-8 -*-
"""The operating schedule."""

import json
import asyncio
import logging
import datetime
import functools
import hbmqtt.client as mqtt_client

from asyncio import Task

from . import app
from .sensorman import SensorManager
from .deviceman import DeviceManager
from .behaviors import SelfDestructError, BaseBehavior, get_behavior_handler

# TEST loggers
log = logging.getLogger("root")


class OperatingSchedule(object):

    def __init__(self, sensors: SensorManager, devices: DeviceManager, schedule: dict):
        self.sensors = sensors
        self.devices = devices
        self.schedule = schedule
        self.behavior_lock = asyncio.Lock()
        # the currently running behavior (BaseBehavior instance)
        self.behavior = None
        # definition of the currently running behavior (dict)
        self.behavior_def = None
        # the currently operating behavior subscription task
        self.behavior_sub = None
        self.broker = mqtt_client.MQTTClient(config={'auto_reconnect': False})
        self.is_running = False

    async def startup(self):
        """Starts scheduling operations."""
        self.is_running = True
        await self.broker.connect(app.broker_url)
        log.debug("Operating schedule connected to broker")

    async def shutdown(self):
        self.is_running = False
        if self.behavior:
            await self.stop_behavior()
        await self.broker.disconnect()

    async def timer(self):
        """Called by the backend when the timer ticks."""
        now = datetime.datetime.now()
        now_min = self.get_time_minutes(now.weekday(), now.hour, now.minute)
        behavior_def = self.find_current_behavior(now_min)
        log.debug("Current behavior for minute {}: {}".format(now_min, behavior_def))

        # no behavior running or different from previous one
        if self.behavior is not None and (behavior_def is None or self.behavior.id != behavior_def['id']):
            log.debug("Shutting down old behavior")
            await self.stop_behavior()

        if self.behavior is None:
            # new behavior to start!
            if behavior_def is not None:
                log.debug("Generating new behavior")
                await self.start_behavior(behavior_def)
            else:
                log.debug("No behavior found!")
        else:
            # behavior already running, wake it up
            log.debug("Pinging behavior")
            # noinspection PyAsyncCall
            asyncio.ensure_future(self.behavior.timer()).add_done_callback(self._future_result)

    async def start_behavior(self, behavior_def: dict):
        """Start a behavior and assign it to the current status."""
        with await self.behavior_lock:
            sensor_topics = self.get_sensor_topics(behavior_def)
            device_topics = self.get_device_topics(behavior_def)
            behavior = get_behavior_handler(behavior_def['id'], behavior_def['name'], sensor_topics, device_topics, self.broker)
            # the subscribe method will also listen for messages so we'll just fire it off
            # noinspection PyAsyncCall
            try:
                await behavior.startup(behavior_def['config'])
                self.behavior_def = behavior_def
                self.behavior = behavior
                self.behavior_sub = asyncio.ensure_future(self.subscribe_for_behavior(behavior))
            except SelfDestructError:
                log.debug("Behavior self-destructed during startup")
                self.delete_behavior(behavior_def)

    async def stop_behavior(self):
        """Stop the currently running behavior."""
        with await self.behavior_lock:
            # cancel immediately
            self.behavior_sub.cancel()
            try:
                await self.behavior_sub
            except asyncio.CancelledError:
                pass

            sensor_topics = self.get_sensor_topics()
            if sensor_topics:
                await self.broker.unsubscribe(sensor_topics)

            device_topics = self.get_device_topics()
            if device_topics:
                await self.broker.unsubscribe(device_topics)

            try:
                await self.behavior.shutdown()
            except SelfDestructError:
                log.debug("Behavior self-destructed during shutdown")
                self.delete_behavior(self.behavior_def)
            self.behavior = None
            self.behavior_def = None
            self.behavior_sub = None

    async def subscribe_for_behavior(self, behavior: BaseBehavior):
        # subscribe to required sensors
        for sensor_id in self.behavior_def['sensors']:
            sensor = self.sensors[sensor_id]
            log.debug("SCHEDULE subscribing to sensor {}".format(sensor.topic))
            await self.broker.subscribe([(sensor.topic + '/+', mqtt_client.QOS_0)])

        # subscribe to required devices
        for device_id in self.behavior_def['devices']:
            device = self.devices[device_id]
            log.debug("SCHEDULE subscribing to device {}".format(device.topic))
            await self.broker.subscribe([(device.topic + '/+', mqtt_client.QOS_0)])

        while self.is_running and self.behavior_def:
            message = await self.broker.deliver_message()
            log.debug("SCHEDULE topic={}, payload={}".format(message.topic, message.data))

            # callback calls must be detached from our flow

            if any(message.topic.startswith(self.sensors[sensor_id].topic)
                   for sensor_id in self.behavior_def['sensors']):
                # noinspection PyAsyncCall
                asyncio.ensure_future(behavior.sensor_data(message.topic, json.loads(message.data))) \
                       .add_done_callback(self._future_result)
            elif any(message.topic.startswith(self.devices[device_id].topic)
                     for device_id in self.behavior_def['devices']):
                # noinspection PyAsyncCall
                asyncio.ensure_future(behavior.device_state(message.topic, json.loads(message.data))) \
                       .add_done_callback(self._future_result)

    def _future_result(self, task: Task):
        try:
            task.result()
        except SelfDestructError:
            log.debug("Behavior self-destructed")
            asyncio.ensure_future(self.stop_behavior()) \
                .add_done_callback(functools.partial(self._delete_behavior, behavior_def=self.behavior_def))

    def get_sensor_topics(self, behavior_def=None):
        if behavior_def is None:
            behavior_def = self.behavior_def
        return [self.sensors[sensor_id].topic for sensor_id in behavior_def['sensors']]

    def get_device_topics(self, behavior_def=None):
        if behavior_def is None:
            behavior_def = self.behavior_def
        return [self.devices[device_id].topic for device_id in behavior_def['devices']]

    def find_current_behavior(self, offset):
        candidate = None
        for bev in self.schedule['behaviors']:
            if bev['start_time'] <= offset < bev['end_time'] and \
                    (candidate is None or candidate['order'] <= bev['order']):
                candidate = bev
        return candidate

    # noinspection PyUnusedLocal
    def _delete_behavior(self, task: Task, behavior_def):
        """Remove the given behavior from our schedule."""
        self.delete_behavior(behavior_def)

    def delete_behavior(self, behavior_def):
        """Remove the given behavior from our schedule."""
        self.schedule['behaviors'].remove(behavior_def)

    @staticmethod
    def get_time_minutes(weekday, hour, minute):
        return (weekday * 24 * 60) + \
               (hour * 60) + \
               minute
