# -*- coding: utf-8 -*-
"""The backend process."""

import sys
import asyncio
import sdnotify
import json

import hbmqtt.client as mqtt_client

from sanic.log import logger
from sqlalchemy.orm.exc import NoResultFound

from .database import scoped_session
from . import app, sensorman, deviceman, opschedule
from .models import Sensor, Schedule
from .models import eventlog


class TimerNode(object):
    """A simple timer node. Sends timing pings for the system to use."""

    def __init__(self, node_id, seconds):
        self.seconds = seconds
        self.topic = app.new_topic(node_id + '/_internal')

        self.broker = mqtt_client.MQTTClient(config={'auto_reconnect': False})
        asyncio.ensure_future(self._connect())

    async def _connect(self):
        while app.is_running:
            await self.broker.connect(app.broker_url)
            logger.debug("Timer connected to broker")
            await self._loop()

    async def _loop(self):
        while app.is_running:
            await asyncio.sleep(self.seconds)
            await self.trigger()

    async def trigger(self):
        await self.broker.publish(self.topic, b'timer', retain=False)


class Backend(object):
    """The backend operations thread."""

    def __init__(self, myapp):
        self.app = myapp
        self.sensors = sensorman.SensorManager(self.app.database)
        self.devices = deviceman.DeviceManager(self.app.database)
        self.broker = mqtt_client.MQTTClient(config={'auto_reconnect': False})
        # the operating (active) schedule
        self.schedule = None
        self.schedule_lock = asyncio.Lock()
        self.timer = None

        # start the timer node
        self.timer = TimerNode('timer', int(self.app.config['BACKEND_INTERVAL']))

        # connect to broker
        asyncio.ensure_future(self._connect())

    async def _connect(self):
        try:
            await self.broker.connect(self.app.broker_url)
            logger.info("Backend connected to broker")
            await self.broker.subscribe([(self.timer.topic, mqtt_client.QOS_0)])
            await self.backend()
            while self.app.is_running:
                message = await self.broker.deliver_message()
                logger.debug("BROKER topic={}, payload={}".format(message.topic, message.data))
                if message.topic == self.timer.topic:
                    if message.data == b'timer':
                        await self.backend()
        except mqtt_client.ClientException:
            logger.critical("Unable to connect to broker! Shutting down.")
            app.stop()

    async def backend(self):
        try:
            logger.debug("BACKEND RUNNING")
            await self.backend_ops()
        except:
            logger.error('Unexpected error:', exc_info=sys.exc_info())
            app.eventlog.event_exc(eventlog.LEVEL_ERROR, 'backend', 'exception')

    async def backend_ops(self):
        """All backend cycle operations are here."""

        with await self.schedule_lock:
            if self.schedule is None:
                # read schedules config (first run)
                schedules = self.get_enabled_schedules()
                if len(schedules) > 0:
                    if len(schedules) > 1:
                        app.eventlog.event(eventlog.LEVEL_WARNING, 'backend', 'configuration',
                                           "Multiple schedules active. We'll take the first one")

                    # take only the first one
                    schedule = schedules[0]
                    logger.info("Activating schedule #{} - {}".format(schedule['id'], schedule['name']))
                    self.schedule = opschedule.OperatingSchedule(self.sensors, self.devices, schedule)
                    await self.schedule.startup()

            if self.schedule:
                await self.schedule.timer()

    async def update_operating_schedule(self, schedule):
        """Updates the current operating schedule instance with new behaviors. Used for temporary alterations."""
        with await self.schedule_lock:
            if self.schedule:
                if await self.schedule.update(schedule):
                    await self.timer.trigger()

    async def update_operating_behavior(self, behavior_id, config):
        """Updates the configuration of a behavior in the current operating schedule. Used for temporary alterations."""
        with await self.schedule_lock:
            if self.schedule:
                if await self.schedule.update_behavior(behavior_id, config):
                    await self.timer.trigger()

    async def set_operating_schedule(self, schedule_id):
        with await self.schedule_lock:
            await self.cancel_current_schedule()
            if schedule_id is not None:
                schedule = self.get_schedule(schedule_id)
                if schedule:
                    logger.info("Activating schedule #{} - {}".format(schedule['id'], schedule['name']))
                    self.schedule = opschedule.OperatingSchedule(self.sensors, self.devices, schedule)
                    await self.schedule.startup()

    async def set_volatile_behavior(self, behavior_def):
        with await self.schedule_lock:
            # special id for temporary behavior
            behavior_def['id'] = 0

            logger.debug("Setting volatile behavior: {}".format(behavior_def))
            if not self.schedule:
                logger.debug("Creating volatile schedule")
                self.schedule = opschedule.OperatingSchedule(self.sensors, self.devices,
                                                             self.create_temp_schedule(behavior_def))
                await self.schedule.startup()
            else:
                # update current volatile behavior or add one
                logger.debug("Updating current schedule")
                await self.schedule.update_behavior(0, behavior_def)
                await self.timer.trigger()
            logger.debug("Schedule: {}".format(self.schedule.schedule))

    async def cancel_current_schedule(self):
        if self.schedule:
            await self.schedule.shutdown()
            self.schedule = None

    def get_enabled_schedules(self):
        with scoped_session(self.app.database) as session:
            return [self._schedule_model(s) for s in session.query(Schedule)
                    .filter(Schedule.enabled == 1)
                    .order_by(Schedule.id)
                    .all()]

    def create_temp_schedule(self, behavior_def):
        # special id for temporary behaviors
        behavior_def['id'] = 0
        return {
            'id': -1,
            'name': 'Temporary schedule',
            'description': 'Temporary schedule',
            'behaviors': [behavior_def],
            'enabled': True
        }

    def get_schedule(self, schedule_id):
        with scoped_session(self.app.database) as session:
            try:
                return self._schedule_model(session.query(Schedule)
                                            .filter(Schedule.id == schedule_id)
                                            .one())
            except NoResultFound:
                return None

    @staticmethod
    def _schedule_model(s: Schedule):
        return {
            'id': s.id,
            'name': s.name,
            'description': s.description,
            'behaviors': [{
                'id': b.id,
                'name': b.behavior_name,
                'order': b.behavior_order,
                'start_time': b.start_time,
                'end_time': b.end_time,
                'config': json.loads(b.config),
                'sensors': [sens.sensor_id for sens in b.sensors],
                'devices': [dev.device_id for dev in b.devices],
            } for b in s.behaviors]
        }

    def get_enabled_sensors(self):
        with scoped_session(self.app.database) as session:
            stmt = Sensor.__table__.select()
            return [dict(s) for s in session.execute(stmt)]


# noinspection PyUnusedLocal
@app.listener('before_server_start')
async def init_backend(sanic, loop):
    try:
        app.backend = Backend(app)
        n = sdnotify.SystemdNotifier()
        n.notify("READY=1")
    except:
        logger.critical('Unexpected error:', exc_info=1)
        sanic.stop()
