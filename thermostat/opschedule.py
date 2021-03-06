# -*- coding: utf-8 -*-
"""The operating schedule."""

import json
import asyncio
import datetime
import functools
import hbmqtt.client as mqtt_client

from sanic.log import logger

from . import app
from .sensorman import SensorManager
from .deviceman import DeviceManager
from .behaviors import SelfDestructError, BaseBehavior, get_behavior_handler


class OperatingSchedule(object):

    def __init__(self, sensors: SensorManager, devices: DeviceManager, schedule: dict):
        self.sensors = sensors
        self.devices = devices
        self.schedule = schedule
        # ensure lock between start and stop behavior methods
        self.behavior_lock = asyncio.Lock()
        # the currently running behavior (BaseBehavior instance)
        self.behavior = None
        # definition of the currently running behavior (dict)
        self.behavior_def = None
        # the currently operating behavior subscription task
        self.behavior_sub = None
        self.behavior_topic = app.new_topic('behavior/active')
        self.broker = mqtt_client.MQTTClient(config={'auto_reconnect': False})
        self.is_running = False

    async def startup(self):
        """Starts scheduling operations."""
        self.is_running = True
        await self.broker.connect(app.broker_url)
        logger.info("Operating schedule connected to broker")

    async def shutdown(self):
        self.is_running = False
        if self.behavior:
            await self.stop_behavior()
        await self.broker.disconnect()

    async def update(self, schedule):
        """Return true if something has changed in a currently running behavior."""
        if self.behavior:
            await self.stop_behavior()

        # assign indexes to behaviors
        index = 0
        for bev in schedule['behaviors']:
            index += 1
            bev['id'] = index

        self.schedule['name'] = schedule['name']
        self.schedule['description'] = schedule['description']
        self.schedule['behaviors'] = schedule['behaviors']
        return True

    async def update_behavior(self, behavior_id: int, config: dict):
        """Return true if something has changed in a currently running behavior."""
        logger.info("Updating behavior with config: {}".format(config))
        restart = False
        if self.behavior and self.behavior.id == behavior_id:
            restart = True
            # we are modifying the current behavior
            await self.stop_behavior()

        behavior_def = self.get_behavior(behavior_id)
        if not behavior_def and not behavior_id:
            behavior_def = config
            behavior_def['id'] = 0
            self.schedule['behaviors'].append(behavior_def)
        else:
            if 'order' in config:
                behavior_def['order'] = config['order']
            if 'start_time' in config:
                behavior_def['start_time'] = config['start_time']
            if 'end_time' in config:
                behavior_def['end_time'] = config['end_time']
            if 'config' in config:
                behavior_def['config'] = config['config']
            if 'sensors' in config:
                behavior_def['sensors'] = config['sensors']
            if 'devices' in config:
                behavior_def['devices'] = config['devices']

        return restart or not behavior_id

    async def timer(self):
        """Called by the backend when the timer ticks."""
        now = datetime.datetime.now()
        now_min = self.get_time_minutes(now.weekday(), now.hour, now.minute)
        behavior_def = self.find_current_behavior(now_min)
        logger.debug("Current behavior for minute {}: {}".format(now_min, behavior_def))

        # no behavior running or different from previous one
        if self.behavior is not None and (behavior_def is None or self.behavior.id != behavior_def['id']):
            logger.debug("Shutting down old behavior")
            await self.stop_behavior()

        if self.behavior is None:
            # new behavior to start!
            if behavior_def is not None:
                logger.debug("Generating new behavior")
                await self.start_behavior(behavior_def)
            else:
                logger.debug("No behavior found!")
                await self.total_shutdown()
        else:
            # behavior already running, wake it up
            logger.debug("Pinging behavior")
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
                # publish active behavior
                await self.broker.publish(self.behavior_topic, json.dumps(self.behavior_def).encode(), retain=True)
            except SelfDestructError:
                logger.debug("Behavior self-destructed during startup")
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
                await self.broker.unsubscribe([topic + '/+' for topic in sensor_topics])

            device_topics = self.get_device_topics()
            if device_topics:
                await self.broker.unsubscribe([topic + '/+' for topic in device_topics])

            try:
                await self.behavior.shutdown()
                if self.behavior_def['order'] == 0:
                    logger.info("Volatile behavior expired")
                    raise SelfDestructError()
            except SelfDestructError:
                logger.debug("Behavior self-destructed during shutdown")
                self.delete_behavior(self.behavior_def)

            # publish null behavior
            await self.broker.publish(self.behavior_topic, ''.encode(), retain=True)
            self.behavior = None
            self.behavior_def = None
            self.behavior_sub = None

    async def subscribe_for_behavior(self, behavior: BaseBehavior):
        # subscribe to required sensors
        for sensor_id in self.behavior_def['sensors']:
            sensor = self.sensors[sensor_id]
            logger.debug("SCHEDULE subscribing to sensor {}".format(sensor.topic))
            await self.broker.subscribe([(sensor.topic + '/+', mqtt_client.QOS_0)])
            # subscribe twice - hbmqtt bug or our own bug
            await self.broker.subscribe([(sensor.topic + '/+', mqtt_client.QOS_0)])

        # subscribe to required devices
        for device_id in self.behavior_def['devices']:
            device = self.devices[device_id]
            logger.debug("SCHEDULE subscribing to device {}".format(device.topic))
            await self.broker.subscribe([(device.topic + '/+', mqtt_client.QOS_0)])

        while self.is_running and self.behavior_def:
            message = await self.broker.deliver_message()
            logger.debug("SCHEDULE topic={}, payload={}".format(message.topic, message.data))

            # callback calls must be detached from our flow

            if any(message.topic.startswith(self.sensors[sensor_id].topic)
                   for sensor_id in self.behavior_def['sensors']):
                # noinspection PyAsyncCall
                asyncio.ensure_future(behavior.sensor_data(message.topic, json.loads(message.data.decode()))) \
                       .add_done_callback(self._future_result)
            elif any(message.topic.startswith(self.devices[device_id].topic)
                     for device_id in self.behavior_def['devices']):
                # noinspection PyAsyncCall
                asyncio.ensure_future(behavior.device_state(message.topic, json.loads(message.data.decode()))) \
                       .add_done_callback(self._future_result)

    def _future_result(self, task: asyncio.Future):
        try:
            task.result()
        except SelfDestructError:
            logger.debug("Behavior self-destructed")
            task.exception()
            asyncio.ensure_future(self.stop_behavior()) \
                .add_done_callback(functools.partial(self._delete_behavior, behavior_def=self.behavior_def))

    async def total_shutdown(self):
        for device in self.devices.values():
            await self.control_device(device.topic, {'enabled': False})

    async def control_device(self, topic, data):
        await self.broker.publish(topic + '/control', json.dumps(data).encode(), retain=False)

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
                    (candidate is None or bev['order'] <= candidate['order']):
                candidate = bev
        return candidate

    # noinspection PyUnusedLocal
    def _delete_behavior(self, task: asyncio.Future, behavior_def):
        """Remove the given behavior from our schedule."""
        self.delete_behavior(behavior_def)

    def delete_behavior(self, behavior_def):
        """Remove the given behavior from our schedule."""
        self.schedule['behaviors'].remove(behavior_def)

    def get_behavior(self, behavior_id):
        return next((b for b in self.schedule['behaviors'] if b['id'] == behavior_id), None)

    @staticmethod
    def get_time_minutes(weekday, hour, minute):
        return (weekday * 24 * 60) + \
               (hour * 60) + \
               minute
