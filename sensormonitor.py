import json
import logging

import requests

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
        except ValueError as err:
            logging.error("Response could not be decoded: " + response.text)
            return False

        if "result" in result and result["result"] == "good":
            return True

        logging.error("Unsuccessful call: " + str(result))

    @staticmethod
    def read_sensors():
        for sensor in SensorMonitor.sensors:
            print(sensor.name + " in " + sensor.group + ": " + str(sensor.read()))
            pass

    @staticmethod
    def setup_sensors():
        SensorMonitor.sensors = []
        idents = {}
        for data in Config.get("Sensors"):
            ident = data["Name"] + "///" + data["Group"]
            if ident in idents:
                raise Exception("There can not be multiple sensors with the same group and name!")
            idents[ident] = ident
            SensorMonitor.sensors.append(Sensor(data["Name"], data["Group"], data["Backend"], data))

    @staticmethod
    def run():
        SensorMonitor.setup_sensors()
        SensorMonitor.read_sensors()

        pass
