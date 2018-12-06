# -*- coding: utf-8 -*-
"""The Sensor Manager."""

import logging
import asyncio
import json
import sqlalchemy.exc

from sqlalchemy.orm.exc import NoResultFound

import hbmqtt.client as mqtt_client
from dateutil.parser import parse as parse_date

from .database import scoped_session
from . import app
from .models import Sensor, Reading
from .sensors import get_sensor_handler


# TEST loggers
log = logging.getLogger("root")


class SensorManager(object):

    def __init__(self, database):
        self.database = database
        self.broker = mqtt_client.MQTTClient(config={'auto_reconnect': False})
        self.connected = False
        # sensor_id: {...}
        self.readings = {}
        self.sensors = {}
        # subscription futures
        self.sensors_subs = {}
        self._init()
        # connect to broker
        asyncio.ensure_future(self._connect())

    def __getitem__(self, item):
        return self.sensors[item]

    def values(self):
        return self.sensors.values()

    async def _connect(self):
        await self.broker.connect(app.broker_url)
        log.debug("Sensor Manager connected to broker")
        self.connected = True
        for sensor_instance in self.sensors.values():
            self.sensors_subs[sensor_instance.id] = \
                asyncio.ensure_future(self._subscribe_and_startup_sensor(sensor_instance))
        await asyncio.gather(*self.sensors_subs.values())

    def _init(self):
        with scoped_session(self.database) as session:
            stmt = Sensor.__table__.select()
            for d in session.execute(stmt):
                self._register(d['id'], d['protocol'], d['address'], d['sensor_type'])

    def _register(self, sensor_id, protocol, address, sensor_type):
        """Creates a new sensor and stores the instance in the internal collection."""
        if sensor_id in self.sensors:
            self._unregister(sensor_id)

        sensor_instance = get_sensor_handler(sensor_id, protocol, address, sensor_type)
        self.sensors[sensor_id] = sensor_instance
        if self.connected:
            self.sensors_subs[sensor_id] = asyncio.ensure_future(self._subscribe_and_startup_sensor(sensor_instance))

    def _unregister(self, sensor_id):
        self.sensors[sensor_id].shutdown()
        if sensor_id in self.sensors_subs:
            self.sensors_subs[sensor_id].cancel()
            del self.sensors_subs[sensor_id]
        del self.sensors[sensor_id]

    async def _subscribe_and_startup_sensor(self, sensor_instance):
        await self.broker.subscribe([(sensor_instance.topic + '/+', mqtt_client.QOS_0)])
        log.debug("SENSORMANAGER subscribed to " + sensor_instance.topic + '/+')
        sensor_instance.startup()
        await self._listen_sensor(sensor_instance)

    async def _listen_sensor(self, sensor_instance):
        while app.is_running and sensor_instance.is_running:
            message = await self.broker.deliver_message()
            log.debug("SENSORMANAGER topic={}, payload={}".format(message.topic, message.data))
            if message.topic.startswith(sensor_instance.topic):
                topic = message.topic.split('/')
                sensor_type = topic[-1]
                if sensor_type == 'control':
                    # someone trying to control the sensor
                    continue

                data = json.loads(message.data.decode())
                log.debug(data)
                reading_timestamp = parse_date(data['timestamp'])
                # store reading in database
                try:
                    self.store_reading(sensor_instance.id, sensor_type,
                                       reading_timestamp, data['unit'], data['value'])
                except sqlalchemy.exc.IntegrityError:
                    # we are trying to store our own last will
                    pass

                # store reading in cache
                cache = self._reading_cache(sensor_instance.id)
                cache['type'] = sensor_type
                cache['timestamp'] = reading_timestamp
                cache['unit'] = data['unit']
                cache['value'] = float(data['value'])

    def _reading_cache(self, sensor_id):
        if sensor_id not in self.readings:
            self.readings[sensor_id] = {}
        return self.readings[sensor_id]

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
            self._register(sensor.id, sensor.protocol, sensor.address, sensor.sensor_type)

    def unregister(self, sensor_id):
        try:
            self._unregister(sensor_id)
            with scoped_session(self.database) as session:
                device = session.query(Sensor).filter(Sensor.id == sensor_id).one()
                session.delete(device)
            return True
        except (NoResultFound, KeyError):
            return False

    def get_last_reading(self, sensor_id):
        return self._reading_cache(sensor_id)

    def get_last_readings(self, sensor_type=None):
        return {k: v for k, v in self.readings.items() if sensor_type is None or v['type'] == sensor_type}

    def get_last_readings_summary(self, sensor_type=None):
        """Returns a dict with the last readings from all sensors."""
        last = {}
        for sensor_id, reading in self.readings.items():
            log.debug("sensor_id: " + sensor_id + ", reading: " + str(reading))
            if sensor_type is not None and sensor_type != reading['type']:
                continue

            if reading['type'] not in last:
                last[reading['type']] = {}
            last[reading['type']][sensor_id] = reading

        # compute averages for temperature
        # TODO account for different units
        for s_type, values in last.items():
            if s_type == 'temperature':
                all_values = [v['value'] for k, v in values.items()]
                values['_avg'] = {'value': sum(all_values) / len(all_values), 'unit': None}

        return last
