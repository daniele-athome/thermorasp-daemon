# -*- coding: utf-8 -*-
"""The backend process."""

import sys
import logging
import asyncio
import datetime
import sdnotify
import json

from sqlalchemy.orm.exc import NoResultFound

import hbmqtt.client as mqtt_client

from .database import scoped_session
from . import app, devices
from .models import Sensor, Pipeline, Device, EventLog
from .models.sensors import store_reading, get_last_readings
from .models import eventlog
from .sensors import get_sensor_handler
from .behaviors import BehaviorContext, get_behavior_handler


# TEST loggers
log = logging.getLogger("root")


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


class OperatingPipeline(object):
    """Manages a pipeline lifecycle."""

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.context = None
        self.chain = None
        self._reload_chain()

    def __getattr__(self, item):
        if item in self.pipeline:
            return self.pipeline[item]
        else:
            return object.__getattribute__(self, item)

    def update(self, behaviors):
        self.pipeline['behaviors'] = behaviors
        self._reload_chain()

    def update_config(self, behavior_order, config):
        for behavior in self.pipeline['behaviors']:
            if behavior['order'] == behavior_order:
                behavior['config'] = config
                self._reload_chain()
                break

    def _reload_chain(self):
        self.chain = [get_behavior_handler(behavior['id'], behavior['config'])
                      for behavior in self.pipeline['behaviors']]

    def set_context(self, event_logger, active_devices, last_reading):
        self.context = BehaviorContext(event_logger, active_devices, last_reading)

    def run(self):
        for idx, behavior in enumerate(list(self.chain)):
            ret = behavior.execute(self.context)
            if self.context.delete:
                # behavior requested to be removed
                del self.pipeline['behaviors'][idx]
                self._reload_chain()
                self.context.delete = False
            if not ret:
                break


class DeviceManager(object):

    def __init__(self, database):
        self.database = database
        self.devices = {}
        self._init()

    def __getitem__(self, item):
        return self.devices[item]

    def values(self):
        return self.devices.values()

    def _init(self):
        with scoped_session(self.database) as session:
            stmt = Device.__table__.select()
            for d in session.execute(stmt):
                self._register(d['id'], d['device_type'], d['protocol'], d['address'], d['name'])

    def _register(self, device_id, device_type, protocol, address, name):
        """Creates a new device and stores the instance in the internal collection."""
        if device_id in self.devices:
            self._unregister(device_id)

        dev_instance = devices.get_device_handler(device_id, device_type, protocol, address, name)
        self.devices[device_id] = dev_instance
        dev_instance.startup()

    def _unregister(self, device_id):
        self.devices[device_id].shutdown()
        del self.devices[device_id]

    def register(self, device_id, protocol, address, device_type, name):
        with scoped_session(self.database) as session:
            device = Device()
            device.id = device_id
            device.name = name
            device.protocol = protocol
            device.address = address
            device.device_type = device_type
            device = session.merge(device)
            # will also unregister old device if any
            self._register(device.id, device.device_type, device.protocol, device.address, device.name)

    def unregister(self, device_id):
        try:
            self._unregister(device_id)
            with scoped_session(self.database) as session:
                device = session.query(Device).filter(Device.id == device_id).one()
                session.delete(device)
            return True
        except (NoResultFound, KeyError):
            return False


class Backend(object):
    """The backend operations thread."""

    def __init__(self, myapp):
        self.app = myapp
        self.devices = DeviceManager(self.app.database)
        self.event_logger = EventLogger(self.app.database)
        # the operating (active) pipeline
        self.pipeline = None
        self.pipeline_lock = asyncio.Lock()
        # sensor futures
        self.sensor_tasks = {}
        self.broker = mqtt_client.MQTTClient(str(self.app.config['DEVICE_ID']) + '-backend')
        self.timer = None

        # start the timer node
        from .nodes import misc
        self.timer = misc.TimerNode(self.app.config['BROKER_TOPIC'], self.app.config['DEVICE_ID'],
                                    'timer', int(self.app.config['BACKEND_INTERVAL']))

        # connect to broker
        asyncio.ensure_future(self._connect())

    async def _connect(self):
        await self.broker.connect(self.app.broker_url)
        log.debug("Backend is connected to broker")
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

    async def sensors(self):
        while self.app.is_running:
            log.debug("SENSORS RUNNING")

            try:
                self.sensors_ops()
            except:
                log.error('Unexpected error:', exc_info=sys.exc_info())
                self.event_logger.event_exc(eventlog.LEVEL_ERROR, 'backend', 'exception')

            await asyncio.sleep(self.app.config['SENSORS_INTERVAL'])

    def sensors_ops(self):
        """Passive sensors reading are here."""

        # read temperatures
        self.read_passive_sensors('temperature')

    async def backend_ops(self):
        """All backend cycle operations are here."""

        with await self.pipeline_lock:
            if self.pipeline is None:
                # read pipelines config (first run)
                pipelines = self.get_enabled_pipelines()
                if len(pipelines) > 0:
                    if len(pipelines) > 1:
                        self.event_logger.event(eventlog.LEVEL_WARNING, 'backend', 'configuration',
                                       "Multiple pipelines active. We'll take the first one")

                    # take only the first one
                    pipeline = pipelines[0]
                    log.debug("Activating pipeline #{} - {}".format(pipeline['id'], pipeline['name']))
                    self.pipeline = OperatingPipeline(pipeline)

            if self.pipeline:
                self.pipeline.set_context(self.event_logger, self.devices, self.get_last_readings())
                self.pipeline.run()

    async def update_operating_pipeline(self, behaviors):
        """Updates the current operating pipeline instance with new behaviors. Used for temporary alterations."""
        with await self.pipeline_lock:
            if self.pipeline:
                self.pipeline.update(behaviors)
                self.pipeline.set_context(self.event_logger, self.devices, self.get_last_readings())
                self.pipeline.run()

    async def update_operating_behavior(self, behavior_order, config):
        """Updates the configuration of a behavior in the current operating pipeline Used for temporary alterations."""
        with await self.pipeline_lock:
            if self.pipeline:
                self.pipeline.update_config(behavior_order, config)
                self.pipeline.set_context(self.event_logger, self.devices, self.get_last_readings())
                self.pipeline.run()

    async def set_operating_pipeline(self, pipeline_id):
        with await self.pipeline_lock:
            if pipeline_id is None:
                self.pipeline = None
            else:
                pipeline = self.get_pipeline(pipeline_id)
                if pipeline:
                    log.debug("Activating pipeline #{} - {}".format(pipeline['id'], pipeline['name']))
                    self.pipeline = OperatingPipeline(pipeline)
                    self.pipeline.set_context(self.event_logger, self.devices, self.get_last_readings())
                    self.pipeline.run()

    def get_last_readings(self, modifier='-10 minutes'):
        """Returns a dict with the last readings from all sensors."""
        with scoped_session(self.app.database) as session:
            rds = get_last_readings(session, modifier)

            last = {}
            for reading in rds:
                if reading.sensor_type not in last:
                    last[reading.sensor_type] = {}
                last[reading.sensor_type][reading.sensor_id] = {
                    'timestamp': reading.timestamp,
                    'unit': reading.unit,
                    'value': float(reading.value),
                }

            # compute averages for temperature
            # TODO account for different units
            for sensor_type, values in last.items():
                if sensor_type == 'temperature':
                    all_values = [v['value'] for k, v in values.items()]
                    values['_avg'] = {'value': sum(all_values) / len(all_values)}

            return last

    def get_passive_sensors(self):
        with scoped_session(self.app.database) as session:
            stmt = Sensor.__table__.select().where(Sensor.data_mode == Sensor.DATA_MODE_PASSIVE)
            return [dict(s) for s in session.execute(stmt)]

    def get_enabled_pipelines(self):
        with scoped_session(self.app.database) as session:
            return [self._pipeline_model(p) for p in session.query(Pipeline)
                    .filter(Pipeline.enabled == 1)
                    .order_by(Pipeline.id)
                    .all()]

    def get_pipeline(self, pipeline_id):
        with scoped_session(self.app.database) as session:
            return self._pipeline_model(session.query(Pipeline)
                                        .filter(Pipeline.id == pipeline_id)
                                        .one())

    @staticmethod
    def _pipeline_model(p):
        return {
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'behaviors': [{
                'id': b.behavior_id,
                'order': b.behavior_order,
                'config': json.loads(b.config),
            } for b in p.behaviors]
        }

    def get_enabled_sensors(self):
        with scoped_session(self.app.database) as session:
            stmt = Sensor.__table__.select()
            return [dict(s) for s in session.execute(stmt)]

    def read_passive_sensors(self, sensor_type):
        loop = asyncio.get_event_loop()
        pasv_sensors = self.get_passive_sensors()
        for sensor_info in pasv_sensors:
            if sensor_info['id'] not in self.sensor_tasks:
                handler = get_sensor_handler(sensor_info['protocol'], sensor_info['address'])
                self.sensor_tasks[sensor_info['id']] = loop.run_in_executor(None, self.do_read_passive_sensor,
                                                                            sensor_type, sensor_info, handler)

    def do_read_passive_sensor(self, sensor_type, sensor_info, handler):
        try:
            reading = handler.read(sensor_type)
            log.debug("%s: %s", sensor_info['id'], reading)
            # store reading in database
            store_reading(self.app, sensor_info['id'], sensor_type,
                          datetime.datetime.now(), reading['unit'], reading['value'])
        except ValueError:
            self.event_logger.event_exc(eventlog.LEVEL_WARNING, 'sensor', 'exception')
        finally:
            del self.sensor_tasks[sensor_info['id']]


# noinspection PyUnusedLocal
@app.listener('before_server_start')
async def init_backend(sanic, loop):
    app.backend = Backend(app)
    n = sdnotify.SystemdNotifier()
    n.notify("READY=1")
