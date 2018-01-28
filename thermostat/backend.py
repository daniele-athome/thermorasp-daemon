# -*- coding: utf-8 -*-
"""The backend process."""

import sys
import logging
import asyncio
import datetime
import sdnotify
import json

from sqlalchemy import text

from .database import scoped_session
from . import app, devices
from .models import Sensor, Pipeline, Reading
from .models.sensors import store_reading
from .models import eventlog
from .sensors import get_sensor_handler
from .devices import device_instances
from .behaviors import BehaviorContext, get_behavior_handler


# TEST loggers
log = logging.getLogger("root")


class OperatingPipeline(object):
    """Manages a pipeline lifecycle."""

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.context = None
        self.chain = []
        for behavior in self.pipeline['behaviors']:
            behavior_instance = get_behavior_handler(behavior['id'], behavior['config'])
            self.chain.append(behavior_instance)

    def set_context(self, active_devices, last_reading):
        self.context = BehaviorContext(active_devices, last_reading)

    def run(self):
        for behavior in self.chain:
            ret = behavior.execute(self.context)
            if ret:
                break


class Backend(object):
    """The backend operations thread."""

    def __init__(self, myapp):
        self.app = myapp
        self.pipeline = None

    async def run(self):
        while self.app.is_running:
            log.debug("BACKEND RUNNING")

            try:
                self.backend_ops()
            except:
                log.error('Unexpected error:', exc_info=sys.exc_info())
                eventlog.event_exc(eventlog.LEVEL_ERROR, 'backend', 'exception')

            await asyncio.sleep(self.app.config['BACKEND_INTERVAL'])

    async def sensors(self):
        while self.app.is_running:
            log.debug("SENSORS RUNNING")

            try:
                self.sensors_ops()
            except:
                log.error('Unexpected error:', exc_info=sys.exc_info())
                eventlog.event_exc(eventlog.LEVEL_ERROR, 'backend', 'exception')

            await asyncio.sleep(self.app.config['SENSORS_INTERVAL'])

    def sensors_ops(self):
        """Passive sensors reading are here."""

        # read temperatures
        self.read_passive_sensors('temperature')

    def backend_ops(self):
        """All backend cycle operations are here."""

        # read pipelines config
        pipelines = self.get_enabled_pipelines()
        if len(pipelines) == 0:
            self.pipeline = None
        elif len(pipelines) > 0:
            if len(pipelines) > 1:
                eventlog.event(eventlog.LEVEL_WARNING, 'backend', 'configuration',
                               "Multiple pipelines active. We'll take the first one")

            # take only the first one
            pipeline = pipelines[0]
            if not self.pipeline or self.pipeline.pipeline['id'] != pipeline['id']:
                # active pipeline changed!
                self.pipeline = OperatingPipeline(pipeline)

            self.pipeline.set_context(device_instances, self.get_last_readings())
            self.pipeline.run()

    def get_last_readings(self, modifier='-10 minutes'):
        """Returns a dict with the last readings from all sensors."""
        with scoped_session(self.app.database) as session:
            rds = session.query(Reading).from_statement(text("select * \
            from sensor_readings r join \
            (select sensor_id, sensor_type, max(timestamp) timestamp from sensor_readings \
            where timestamp > datetime('now', '"+modifier+"') \
            group by sensor_id, sensor_type) as rmax \
            on r.sensor_id = rmax.sensor_id and r.sensor_type = rmax.sensor_type and r.timestamp = rmax.timestamp \
            order by timestamp desc")).all()

            last = {}
            for reading in rds:
                if reading.sensor_type not in last:
                    last[reading.sensor_type] = {}
                last[reading.sensor_type][reading.sensor_id] = {
                    'timestamp': reading.timestamp,
                    'unit': reading.unit,
                    'value': float(reading.value),
                }

            # compute averages
            # TODO account for different units
            for sensor_type, values in last.items():
                all_values = [v['value'] for k, v in values.items()]
                values['_avg'] = {'value': sum(all_values) / len(all_values)}

            return last

    def get_passive_sensors(self):
        with scoped_session(self.app.database) as session:
            stmt = Sensor.__table__.select().where(Sensor.data_mode == Sensor.DATA_MODE_PASSIVE)
            return [dict(s) for s in session.execute(stmt)]

    def get_enabled_pipelines(self):
        with scoped_session(self.app.database) as session:
            ppls = []
            for p in session.query(Pipeline).filter(Pipeline.enabled == 1).all():
                model = {
                    'id': p.id,
                    'name': p.name,
                    'description': p.description,
                    'behaviors': [{
                        'id': b.behavior_id,
                        'config': json.loads(b.config),
                    } for b in p.behaviors]
                }
                ppls.append(model)
            return ppls

    def get_enabled_sensors(self):
        with scoped_session(self.app.database) as session:
            stmt = Sensor.__table__.select()
            return [dict(s) for s in session.execute(stmt)]

    def read_passive_sensors(self, sensor_type):
        pasv_sensors = self.get_passive_sensors()
        for sensor_info in pasv_sensors:
            handler = get_sensor_handler(sensor_info['protocol'], sensor_info['address'])
            reading = handler.read(sensor_type)
            log.debug("%s: %s", sensor_info['id'], reading)
            # store reading in database
            store_reading(self.app, sensor_info['id'], sensor_type,
                          datetime.datetime.now(), reading['unit'], reading['value'])


# noinspection PyUnusedLocal
@app.listener('before_server_start')
async def init_backend(sanic, loop):
    devices.init()
    app.backend = Backend(app)
    asyncio.ensure_future(app.backend.run(), loop=loop)
    asyncio.ensure_future(app.backend.sensors(), loop=loop)


# noinspection PyUnusedLocal
@app.listener('after_server_start')
async def notify_systemd(sanic, loop):
    n = sdnotify.SystemdNotifier()
    n.notify("READY=1")
