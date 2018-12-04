# -*- coding: utf-8 -*-
"""The backend process."""

import sys
import logging
import asyncio
import datetime
import sdnotify
import json

import hbmqtt.client as mqtt_client

from .database import scoped_session
from . import app, sensorman, deviceman, opschedule
from .models import Sensor, EventLog, Schedule
from .models import eventlog


# TEST loggers
log = logging.getLogger("root")


class TimerNode(object):
    """A simple timer node. Sends timing pings for the system to use."""

    def __init__(self, node_id, seconds):
        self.seconds = seconds
        self.topic = app.new_topic(node_id + '/_internal')

        self.broker = mqtt_client.MQTTClient()
        asyncio.ensure_future(self._connect())

    async def _connect(self):
        await self.broker.connect(app.broker_url)
        await asyncio.ensure_future(self._loop())

    async def _loop(self):
        while app.is_running:
            await asyncio.sleep(self.seconds)
            await self.broker.publish(self.topic, b'timer', retain=False)


class EventLogger(object):
    def __init__(self, database):
        self.database = database

    def event(self, level, source, name, description=None):
        with scoped_session(self.database) as session:
            vevent = EventLog()
            vevent.timestamp = datetime.datetime.now()
            vevent.level = level
            vevent.source = source
            vevent.name = name
            vevent.description = description
            session.add(vevent)

    def event_exc(self, level, source, name):
        import traceback
        e_type, e_value, e_tb = sys.exc_info()
        strerr1 = traceback.format_exception_only(e_type, e_value)[0][:-1]
        strerr = ''.join(traceback.format_exception(e_type, e_value, e_tb))
        self.event(level, source, name, strerr1 + "\n" + strerr)


class Backend(object):
    """The backend operations thread."""

    def __init__(self, myapp):
        self.app = myapp
        self.sensors = sensorman.SensorManager(self.app.database)
        self.devices = deviceman.DeviceManager(self.app.database)
        self.event_logger = EventLogger(self.app.database)
        self.broker = mqtt_client.MQTTClient()
        # the operating (active) schedule
        self.schedule = None
        self.schedule_lock = asyncio.Lock()
        self.timer = None

        # start the timer node
        self.timer = TimerNode('timer', int(self.app.config['BACKEND_INTERVAL']))

        # connect to broker
        asyncio.ensure_future(self._connect())

    async def _connect(self):
        await self.broker.connect(self.app.broker_url)
        log.debug("Backend connected to broker")
        await self.broker.subscribe([(self.timer.topic, mqtt_client.QOS_0)])
        await self.backend()
        while self.app.is_running:
            message = await self.broker.deliver_message()
            log.debug("BROKER topic={}, payload={}".format(message.topic, message.data))
            if message.topic == self.timer.topic:
                if message.data == b'timer':
                    await self.backend()

    async def backend(self):
        try:
            log.debug("BACKEND RUNNING")
            await self.backend_ops()
        except:
            log.error('Unexpected error:', exc_info=sys.exc_info())
            self.event_logger.event_exc(eventlog.LEVEL_ERROR, 'backend', 'exception')

    async def backend_ops(self):
        """All backend cycle operations are here."""

        with await self.schedule_lock:
            if self.schedule is None:
                # read schedules config (first run)
                schedules = self.get_enabled_schedules()
                if len(schedules) > 0:
                    if len(schedules) > 1:
                        self.event_logger.event(eventlog.LEVEL_WARNING, 'backend', 'configuration',
                                                "Multiple schedules active. We'll take the first one")

                    # take only the first one
                    schedule = schedules[0]
                    log.debug("Activating schedule #{} - {}".format(schedule['id'], schedule['name']))
                    self.schedule = opschedule.OperatingSchedule(self.sensors, self.devices, schedule)
                    await self.schedule.startup()

            if self.schedule:
                await self.schedule.timer()

    # TODO
    async def update_operating_pipeline(self, behaviors):
        """Updates the current operating pipeline instance with new behaviors. Used for temporary alterations."""
        with await self.pipeline_lock:
            if self.pipeline:
                self.pipeline.update(behaviors)
                self.pipeline.set_context(self.event_logger, self.devices, self.sensors.get_last_readings_summary())
                self.pipeline.run()

    # TODO
    async def update_operating_behavior(self, behavior_order, config):
        """Updates the configuration of a behavior in the current operating pipeline Used for temporary alterations."""
        with await self.pipeline_lock:
            if self.pipeline:
                self.pipeline.update_config(behavior_order, config)
                self.pipeline.set_context(self.event_logger, self.devices, self.sensors.get_last_readings_summary())
                self.pipeline.run()

    async def set_operating_schedule(self, schedule_id):
        with await self.schedule_lock:
            if schedule_id is None:
                self.cancel_current_schedule()
            else:
                schedule = self.get_schedule(schedule_id)
                if schedule:
                    log.debug("Activating schedule #{} - {}".format(schedule['id'], schedule['name']))
                    self.schedule = opschedule.OperatingSchedule(self.sensors, self.devices, schedule)
                    await self.schedule.startup()

    def cancel_current_schedule(self):
        if self.schedule:
            self.schedule.shutdown()
            self.schedule = None

    def get_passive_sensors(self):
        with scoped_session(self.app.database) as session:
            stmt = Sensor.__table__.select().where(Sensor.data_mode == Sensor.DATA_MODE_PASSIVE)
            return [dict(s) for s in session.execute(stmt)]

    def get_enabled_schedules(self):
        with scoped_session(self.app.database) as session:
            return [self._schedule_model(s) for s in session.query(Schedule)
                    .filter(Schedule.enabled == 1)
                    .order_by(Schedule.id)
                    .all()]

    def get_schedule(self, schedule_id):
        with scoped_session(self.app.database) as session:
            return self._schedule_model(session.query(Schedule)
                                        .filter(Schedule.id == schedule_id)
                                        .one())

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
        log.error('Unexpected error:', exc_info=sys.exc_info())
        sanic.stop()
