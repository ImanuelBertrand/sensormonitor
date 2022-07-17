import errno
import json
import logging
import os
import statistics
import threading
import time

import requests
from paho.mqtt import client as mqtt_client
from paho.mqtt.client import MQTT_ERR_SUCCESS

from config import Config
from sensor import Sensor


class SensorMonitor:
    mqtt_client = None
    latest_data = None
    sensors = None

    lock = None

    sender_session: requests.Session = None

    @staticmethod
    def send_data(data, url=None) -> bool:
        if SensorMonitor.sender_session is None:
            SensorMonitor.sender_session = requests.Session()

        session = SensorMonitor.sender_session

        if url is None:
            url = Config.get("Server.Address")

        if url is None:
            return False

        auth = None

        if Config.get("Server.Username") is not None and Config.get("Server.Password") is not None:
            auth = (
                Config.get("Server.Username", None),
                Config.get("Server.Password", None)
            )

        headers = Config.get("Server.Headers")

        try:
            response = session.post(
                url=url,
                json=data,
                auth=auth,
                headers=headers
            )
        except requests.exceptions.RequestException as e:
            logging.error("Exception while trying to send data")
            logging.error(e)
            return False

        if response.status_code < 200 or response.status_code > 299:
            logging.error("Received status code " + str(response.status_code) + " with body: " + response.text)
            return False
        try:
            json.loads(response.text)
        except ValueError:
            logging.error("Response could not be decoded: " + response.text)
            return False

        return True

    @staticmethod
    def aggregate_data(data, decimals):
        value = round(statistics.mean(data), decimals)
        if decimals == 0:
            value = int(value)
        return value

    @staticmethod
    def send_aggregated_data_mqtt(entries):
        client = SensorMonitor.get_mqtt_client()
        if client is None:
            return False

        for key in entries:
            entry = entries[key]

            if "precision" in entry:
                precision = entry["precision"]
            else:
                precision = 0

            topic = entry["topic"]
            message = str(SensorMonitor.aggregate_data(entry["values"].values(), precision))
            if client is None:
                logging.error("MQTT client is none!")
            result = client.publish(topic, message)
            status = result[0]
            if status != 0:
                logging.error("Failed to send mqtt message for " + topic)
            result = client.loop()

            if result != MQTT_ERR_SUCCESS:
                logging.error("MQTT publishing error: " + str(result))
                SensorMonitor.mqtt_client = None

    @staticmethod
    def get_mqtt_client():
        client = SensorMonitor.mqtt_client

        if isinstance(client, mqtt_client.Client) and client.is_connected():
            can_loop = SensorMonitor.mqtt_client.loop()
            if can_loop != MQTT_ERR_SUCCESS:
                logging.error("MQTT looping error: " + str(can_loop))
                client = None

        if client is None:
            client_id = 'sensormonitor-mqtt-' + os.uname()[1] + '-'
            os.getpid()
            client = mqtt_client.Client(client_id)
            SensorMonitor.mqtt_client = client

        if isinstance(client, mqtt_client.Client) and not client.is_connected():
            broker = Config.get("MQTT.Broker")
            port = Config.get("MQTT.Port", 1883)
            username = Config.get("MQTT.Username")
            password = Config.get("MQTT.Password")
            client.username_pw_set(username, password)
            client.on_connect = SensorMonitor.on_mqtt_connect
            client.connect(broker, port)

        return SensorMonitor.mqtt_client

    # noinspection PyUnusedLocal
    @staticmethod
    def on_mqtt_connect(client, userdata, flags, rc):
        if rc == 0:
            logging.info("Connected to MQTT broker!")
        else:
            logging.error("Failed to connect to MQTT broker, return code %d\n", rc)
            SensorMonitor.mqtt_client = None

    @staticmethod
    def read_sensors():
        data = []
        for sensor in SensorMonitor.sensors:
            if not sensor.should_read_now():
                continue

            value = sensor.read()
            if value is None:
                continue

            data += value

        with SensorMonitor.lock:
            for entry in data:
                key = entry['group'] + '/' + entry['name']
                if key not in SensorMonitor.latest_data:
                    SensorMonitor.latest_data[key] = entry
                else:
                    for t in entry['values']:
                        SensorMonitor.latest_data[key]['values'][t] = entry['values'][t]

        return data

    @staticmethod
    def setup_sensors():
        SensorMonitor.sensors = []
        for data in Config.get("Sensors"):
            sensor = Sensor(data)
            if sensor.get_config('Active', True):
                SensorMonitor.sensors.append(sensor)

    @staticmethod
    def get_process_lock_file():
        return os.path.dirname(__file__) + '/.sensors.lock'

    @staticmethod
    def pid_exists(pid):
        if pid < 0:
            return False
        if pid == 0:
            raise ValueError('invalid PID 0')
        try:
            os.kill(pid, 0)
        except OSError as err:
            if err.errno == errno.ESRCH:
                return False
            elif err.errno == errno.EPERM:
                return True
            else:
                raise
        else:
            return True

    @staticmethod
    def is_already_running():
        filename = SensorMonitor.get_process_lock_file()
        if not os.path.exists(filename):
            return False

        file = open(filename, 'r')
        pid = file.read()
        file.close()

        result = pid.isnumeric() and SensorMonitor.pid_exists(int(pid))

        if not result:
            os.remove(filename)

        return result

    @staticmethod
    def save_process_lock():
        file = open(SensorMonitor.get_process_lock_file(), 'w')
        file.write(str(os.getpid()))
        file.close()

    @staticmethod
    def send_data_loop():
        interval = Config.get_interval()
        while True:
            loop_started = time.time()

            with SensorMonitor.lock:
                entries = SensorMonitor.latest_data.copy()
                SensorMonitor.latest_data = {}

            try:
                SensorMonitor.send_aggregated_data_mqtt(entries)
            except Exception as e:
                logging.error(e)
                pass

            sleep_time = max([0, interval - time.time() + loop_started])
            if sleep_time < 0.7:
                logging.info("Sleeping for " + str(sleep_time))
            time.sleep(sleep_time)

    @staticmethod
    def run():
        if SensorMonitor.is_already_running():
            logging.debug('Aborting startup due to existing process')
            return

        SensorMonitor.save_process_lock()
        SensorMonitor.latest_data = {}
        SensorMonitor.lock = threading.Lock()

        logging.info('Starting application')
        SensorMonitor.setup_sensors()

        logging.info('Starting sender thread')
        SensorMonitor.sender_thread = threading.Thread(target=SensorMonitor.send_data_loop)
        SensorMonitor.sender_thread.start()
        logging.info('Started sender thread, proceeding to main loop')

        while True:
            loop_started = time.time()
            SensorMonitor.read_sensors()
            sleep_time = max([0, 1 - time.time() + loop_started])
            if sleep_time < 0.7:
                logging.info("Sleeping for " + str(sleep_time))
            time.sleep(sleep_time)
