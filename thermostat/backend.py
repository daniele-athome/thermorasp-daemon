# -*- coding: utf-8 -*-
"""The backend process."""

import sys
import logging
import asyncio
import datetime
import sdnotify
import json

import homie

from sqlalchemy.orm.exc import NoResultFound

import paho.mqtt.client as paho_mqtt

from .database import scoped_session
from . import app, devices
from .models import Sensor, Pipeline, Reading, Device
from .models.sensors import store_reading, get_last_readings
from .models import eventlog
from .sensors import get_sensor_handler
from .behaviors import BehaviorContext, get_behavior_handler


# TEST loggers
log = logging.getLogger("root")


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

    def set_context(self, active_devices, last_reading):
        self.context = BehaviorContext(active_devices, last_reading)

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
        with scoped_session(app.database) as session:
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

    def __init__(self, myapp, loop):
        self.app = myapp
        self.loop = loop
        self.devices = DeviceManager(self.app.database)
        # the operating (active) pipeline
        self.pipeline = None
        self.pipeline_lock = asyncio.Lock()
        # sensor futures
        self.sensor_tasks = {}

        # connect to broker
        self.broker = paho_mqtt.Client('Homie-' + str(self.app.config['DEVICE_ID']) + '-backend')
        self.broker.on_connect = self._connected
        self.broker.on_message = self._message
        self.broker.connect_async(self.app.config['BROKER_HOST'], self.app.config['BROKER_PORT'])
        self.broker.loop_start()

    def _connected(self, client: paho_mqtt.Client, *args):
        log.debug("Backend is connected to broker")
        client.subscribe(self.app.timer.topic)

    def _message(self, client: paho_mqtt.Client, userdata, message: paho_mqtt.MQTTMessage):
        #log.debug("BROKER topic={}, payload={}".format(message.topic, message.payload))
        if message.topic == self.app.timer.topic:
            if message.payload == b'timer':
                log.debug("BACKEND RUNNING")
                try:
                    asyncio.run_coroutine_threadsafe(self.backend_ops(), self.loop)
                except:
                    log.error('Unexpected error:', exc_info=sys.exc_info())
                    eventlog.event_exc(eventlog.LEVEL_ERROR, 'backend', 'exception')

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

    async def backend_ops(self):
        """All backend cycle operations are here."""

        with await self.pipeline_lock:
            if self.pipeline is None:
                # read pipelines config (first run)
                pipelines = self.get_enabled_pipelines()
                if len(pipelines) > 0:
                    if len(pipelines) > 1:
                        eventlog.event(eventlog.LEVEL_WARNING, 'backend', 'configuration',
                                       "Multiple pipelines active. We'll take the first one")

                    # take only the first one
                    pipeline = pipelines[0]
                    log.debug("Activating pipeline #{} - {}".format(pipeline['id'], pipeline['name']))
                    self.pipeline = OperatingPipeline(pipeline)

            if self.pipeline:
                self.pipeline.set_context(self.devices, self.get_last_readings())
                self.pipeline.run()

    async def update_operating_pipeline(self, behaviors):
        """Updates the current operating pipeline instance with new behaviors. Used for temporary alterations."""
        with await self.pipeline_lock:
            if self.pipeline:
                self.pipeline.update(behaviors)
                self.pipeline.set_context(self.devices, self.get_last_readings())
                self.pipeline.run()

    async def update_operating_behavior(self, behavior_order, config):
        """Updates the configuration of a behavior in the current operating pipeline Used for temporary alterations."""
        with await self.pipeline_lock:
            if self.pipeline:
                self.pipeline.update_config(behavior_order, config)
                self.pipeline.set_context(self.devices, self.get_last_readings())
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
                    self.pipeline.set_context(self.devices, self.get_last_readings())
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
            eventlog.event_exc(eventlog.LEVEL_WARNING, 'sensor', 'exception')
        finally:
            del self.sensor_tasks[sensor_info['id']]


# noinspection PyUnusedLocal
@app.listener('before_server_start')
async def init_backend(sanic, loop):
    app.device = homie.Device({
        'HOST': app.config['BROKER_HOST'],
        'PORT': app.config['BROKER_PORT'],
        'TOPIC': app.config['BROKER_TOPIC'],
        'KEEPALIVE': 60,
        'DEVICE_ID': str(app.config['DEVICE_ID']),
        'DEVICE_NAME': app.config['DEVICE_NAME'],
    })

    # start the timer node
    from .nodes import misc
    app.timer = misc.TimerNode(app.device, 'timer', 'Timer', app.config['BACKEND_INTERVAL'])

    app.backend = Backend(app, loop)
    #asyncio.ensure_future(app.backend.sensors(), loop=loop)


# noinspection PyUnusedLocal
@app.listener('after_server_start')
async def notify_systemd(sanic, loop):
    app.device.setup()
    n = sdnotify.SystemdNotifier()
    n.notify("READY=1")
