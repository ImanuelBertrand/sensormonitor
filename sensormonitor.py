import datetime
import json
import logging
import requests
import sqlite3
import time
from config import Config
from sensor import Sensor


class SensorMonitor:
    sensors = None
    db: sqlite3.Connection = None

    @staticmethod
    def send_data(data) -> bool:
        url = Config.get("Server.Address")
        if url is None:
            return False

        try:
            response = requests.post(
                url=url,
                json=data,
                auth=(
                    Config.get("Server.Username"),
                    Config.get("Server.Password")
                )
            )
        except requests.exceptions.RequestException as e:
            logging.error("Exception while trying to send data")
            return False

        if response.status_code != 200:
            logging.error("Received status code " + str(response.status_code) + " with body: " + response.text)
            return False
        try:
            result = json.loads(response.text)
        except ValueError:
            logging.error("Response could not be decoded: " + response.text)
            return False

        if "result" in result and result["result"] == "good":
            return True

        logging.error("Unsuccessful call: " + str(result))

    @staticmethod
    def send_all_data():
        db = SensorMonitor.db
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT * FROM readings").fetchall()

        if len(rows) == 0:
            print("No data to send")
            return

        data = []
        ids = []
        for row in rows:
            ids.append(str(int(row["id"])))
            _row = dict(zip(row.keys(), row))
            del _row["id"]
            data.append(_row)

        if SensorMonitor.send_data(data):
            db.execute("DELETE FROM readings WHERE id IN (" + ",".join(ids) + ")")
            db.commit()
            print("Sent and deleted data")
        else:
            logging.error("Failed to send data")

    @staticmethod
    def read_sensors():
        data = []
        for sensor in SensorMonitor.sensors:
            value = sensor.read()
            if value is None:
                continue

            if isinstance(value, list):
                data += value
                continue

            if not isinstance(value, dict):
                value = {time.time(): value}

            if len(value) == 0:
                continue
            for t in value:
                data.append({
                    "name": sensor.name,
                    "group": sensor.group,
                    "value": value[t],
                    "time": datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S%z"),
                })
        return data

    @staticmethod
    def save_data(entries):
        if len(entries) == 0:
            return

        sql = "INSERT INTO readings (sensor, `group`, time, value) VALUES (:name, :group, :value, :time)"
        for entry in entries:
            SensorMonitor.db.execute(sql, entry)
        SensorMonitor.db.commit()

    @staticmethod
    def setup_sensors():
        SensorMonitor.sensors = []
        for data in Config.get("Sensors"):
            sensor = Sensor(data)
            SensorMonitor.sensors.append(sensor)

    @staticmethod
    def setup_database():
        db = sqlite3.connect("data.db")
        db.execute("CREATE TABLE IF NOT EXISTS readings ("
                   "id INTEGER PRIMARY KEY, "
                   "sensor TEXT, "
                   "`group` TEXT, "
                   "time TEXT, "
                   "value FLOAT)")
        SensorMonitor.db = db

    @staticmethod
    def run():
        logging.info('Starting application')
        SensorMonitor.setup_sensors()
        SensorMonitor.setup_database()
        while True:
            loop_started = time.time()
            data = SensorMonitor.read_sensors()
            SensorMonitor.save_data(data)
            SensorMonitor.send_all_data()
            time.sleep(max([0, 1 - time.time() + loop_started]))
