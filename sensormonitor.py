import datetime
import json
import logging
import requests
import sqlite3
import time
from config import Config
from i2c import I2C
from sensor import Sensor


class SensorMonitor:
    sensors = None
    db: sqlite3.Connection = None

    @staticmethod
    def send_data(data) -> bool:
        response = requests.post(
            url=Config.get("Server.Address"),
            json=data,
            auth=(
                Config.get("Server.Username"),
                Config.get("Server.Password")
            )
        )
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
            print("Failed to send")

    @staticmethod
    def read_sensors():
        data = []
        for sensor in SensorMonitor.sensors:
            data.append({
                "name": sensor.name,
                "group": sensor.group,
                "value": sensor.read(),
                "time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z"),
            })
        I2C.close_all()
        return data

    @staticmethod
    def save_data(entries):
        sql = "INSERT INTO readings (sensor, `group`, time, value) VALUES (:name, :group, :value, :time)"
        for entry in entries:
            SensorMonitor.db.execute(sql, entry)
        SensorMonitor.db.commit()

    @staticmethod
    def setup_sensors():
        SensorMonitor.sensors = []
        idents = {}
        for data in Config.get("Sensors"):
            sensor = Sensor(data)
            ident = sensor.name + "///" + sensor.group
            if ident in idents:
                raise Exception("There can not be multiple sensors with the same group and name!")
            idents[ident] = ident
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
        SensorMonitor.setup_sensors()
        SensorMonitor.setup_database()
        interval = Config.get_interval()
        while True:
            loop_started = time.time()
            data = SensorMonitor.read_sensors()
            SensorMonitor.save_data(data)
            SensorMonitor.send_all_data()
            time.sleep(interval - time.time() + loop_started)
