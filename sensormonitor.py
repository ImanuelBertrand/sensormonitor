import json
import logging
import requests
import time
from config import Config
from sensor import Sensor


class SensorMonitor:
    sensors = None

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
    def read_sensors():
        data = []
        for sensor in SensorMonitor.sensors:
            data.append({
                "name": sensor.name,
                "group": sensor.group,
                "value": sensor.read(),
                "time": round(time.time()),
            })
        return data

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
    def run():
        SensorMonitor.setup_sensors()
        interval = Config.get_interval()
        while True:
            data = SensorMonitor.read_sensors()
            SensorMonitor.send_data(data)
            time.sleep(interval)
