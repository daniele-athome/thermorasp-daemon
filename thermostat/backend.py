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
from dateutil.parser import parse as parse_date

from .database import scoped_session
from . import app, devices
from .models import Sensor, Pipeline, Device, Reading, EventLog
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


class SensorManager(object):

    def __init__(self, database, broker: mqtt_client.MQTTClient):
        self.database = database
        self.broker = None
        # sensor_type: {_avg: {...}, sensor_id: {...}, sensor_id: {...}}
        self.readings = {}
        self.sensors = {}
        # subscription futures
        self.sensors_subs = {}
        self._init()
        # _init must see a null broker
        self.broker = broker

    def __getitem__(self, item):
        return self.sensors[item]

    def values(self):
        return self.sensors.values()

    def subscribe_all(self):
        for sensor_instance in self.sensors.values():
            self.sensors_subs[sensor_instance.id] = asyncio.ensure_future(self._subscribe_sensor(sensor_instance))
            sensor_instance.startup()

    def _init(self):
        with scoped_session(self.database) as session:
            stmt = Sensor.__table__.select()
            for d in session.execute(stmt):
                self._register(d['id'], d['protocol'], d['address'])

    def _register(self, sensor_id, protocol, address):
        """Creates a new sensor and stores the instance in the internal collection."""
        if sensor_id in self.sensors:
            self._unregister(sensor_id)

        sensor_instance = get_sensor_handler(sensor_id, protocol, address)
        self.sensors[sensor_id] = sensor_instance
        if self.broker:
            sensor_instance.startup()
            self.sensors_subs[sensor_id] = asyncio.ensure_future(self._subscribe_sensor(sensor_instance))

    def _unregister(self, sensor_id):
        self.sensors[sensor_id].shutdown()
        self.sensors_subs[sensor_id].cancel()
        del self.sensors[sensor_id]
        del self.sensors_subs[sensor_id]

    async def _subscribe_sensor(self, sensor_instance):
        await self.broker.subscribe([(sensor_instance.topic + '/+', mqtt_client.QOS_0)])
        while app.is_running and sensor_instance.is_running:
            message = await self.broker.deliver_message()
            log.debug("SENSORMANAGER topic={}, payload={}".format(message.topic, message.data))
            if message.topic.startswith(sensor_instance.topic):
                topic = message.topic.split('/')
                sensor_type = topic[-1]
                data = json.loads(message.data.decode('utf-8'))
                reading_timestamp = parse_date(data['timestamp'])
                # store reading in database
                self.store_reading(sensor_instance.id, sensor_type,
                                   reading_timestamp, data['unit'], data['value'])
                # store reading in cache
                cache = self._reading_cache(sensor_type)
                cache[sensor_instance.id] = {
                    'timestamp': reading_timestamp,
                    'unit': data['unit'],
                    'value': float(data['value']),
                }
                # recalculate average
                all_values = [v['value'] if k != '_avg' else 0 for k, v in cache.items()]
                cache['_avg'] = {'value': sum(all_values) / len(all_values)}

    def _reading_cache(self, sensor_type):
        if sensor_type not in self.readings:
            self.readings[sensor_type] = {}
        return self.readings[sensor_type]

    def store_reading(self, sensor_id, sensor_type, timestamp, unit, value):
        with scoped_session(self.database) as session:
            reading = Reading()
            reading.sensor_id = sensor_id
            reading.sensor_type = sensor_type
            reading.timestamp = timestamp
            reading.unit = unit
            reading.value = value
            session.add(reading)

    def register(self, sensor_id, protocol, address, sensor_type):
        with scoped_session(self.database) as session:
            sensor = Sensor()
            sensor.id = sensor_id
            sensor.protocol = protocol
            sensor.address = address
            sensor.sensor_type = sensor_type
            sensor = session.merge(sensor)
            # will also unregister old device if any
            self._register(sensor.id, sensor.protocol, sensor.address)

    def unregister(self, sensor_id):
        try:
            self._unregister(sensor_id)
            with scoped_session(self.database) as session:
                device = session.query(Sensor).filter(Sensor.id == sensor_id).one()
                session.delete(device)
            return True
        except (NoResultFound, KeyError):
            return False

    def get_last_readings(self, sensor_type='temperature'):
        """Returns a dict with the last readings from all sensors."""
        return self._reading_cache(sensor_type)


class Backend(object):
    """The backend operations thread."""

    def __init__(self, myapp):
        self.app = myapp
        self.broker = mqtt_client.MQTTClient()
        self.sensors = SensorManager(self.app.database, self.broker)
        self.devices = DeviceManager(self.app.database)
        self.event_logger = EventLogger(self.app.database)
        # the operating (active) pipeline
        self.pipeline = None
        self.pipeline_lock = asyncio.Lock()
        self.timer = None

        # start the timer node
        from .nodes import misc
        self.timer = misc.TimerNode('timer', int(self.app.config['BACKEND_INTERVAL']))

        # connect to broker
        asyncio.ensure_future(self._connect())

    async def _connect(self):
        await self.broker.connect(self.app.broker_url)
        log.debug("Backend connected to broker")
        await self.broker.subscribe([(self.timer.topic, mqtt_client.QOS_0)])
        self.sensors.subscribe_all()
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
                self.pipeline.set_context(self.event_logger, self.devices, self.sensors.get_last_readings())
                self.pipeline.run()

    async def update_operating_pipeline(self, behaviors):
        """Updates the current operating pipeline instance with new behaviors. Used for temporary alterations."""
        with await self.pipeline_lock:
            if self.pipeline:
                self.pipeline.update(behaviors)
                self.pipeline.set_context(self.event_logger, self.devices, self.sensors.get_last_readings())
                self.pipeline.run()

    async def update_operating_behavior(self, behavior_order, config):
        """Updates the configuration of a behavior in the current operating pipeline Used for temporary alterations."""
        with await self.pipeline_lock:
            if self.pipeline:
                self.pipeline.update_config(behavior_order, config)
                self.pipeline.set_context(self.event_logger, self.devices, self.sensors.get_last_readings())
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
                    self.pipeline.set_context(self.event_logger, self.devices, self.sensors.get_last_readings())
                    self.pipeline.run()

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
