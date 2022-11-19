import datetime
import time

# noinspection PyUnresolvedReferences
import RPi.GPIO as GPIO

from config import Config


class AbstractSensor:
    def __init__(self, config: dict):
        self.config = config
        pin = self.get_config("GPIO.Power", False)
        if pin:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(0.5)
            GPIO.output(pin, GPIO.HIGH)

    def log(self, message):
        print(self.name + ": " + message)

    @property
    def name(self):
        return self.get_config("Name")

    @property
    def group(self):
        return self.get_config("Group")

    @property
    def backend(self):
        return self.get_config("Backend")

    def get_config(self, key, default=None, readout_key=None):
        if readout_key is not None:
            _key = "Readouts." + str(readout_key) + "." + key
        else:
            _key = key

        result = Config.get(key=_key, default=None, data=self.config)

        if result is not None:
            return result

        if readout_key is not None:
            result = Config.get(key=key, default=None, data=self.config)

        if result is not None:
            return result

        return default

    def _get_i2c_bus(self):
        return self.get_config("I2C.Bus", 1)

    def _get_i2c_address(self, default=None):
        return self.get_config("I2C.Address", default)

    @staticmethod
    def get_time():
        return datetime.datetime.fromtimestamp(time.time()).strftime(
            "%Y-%m-%d %H:%M:%S%z"
        )

    def get_readout_keys(self):
        values = self.get_config("Readouts")
        if not isinstance(values, dict):
            return [None]
        else:
            return values.keys()

    def get_result_template(self, readout_key=None):
        name = self.get_config("Name", "", readout_key)
        group = self.get_config("Group", "", readout_key)
        topic = self.get_config("Topic", "sensors/" + group + "/" + name, readout_key)
        return {
            "name": name,
            "group": self.get_config("Group", "", readout_key),
            "friendly_name": self.get_config("Friendly Name", name, readout_key),
            "unit_of_measure": self.get_config("Unit", None, readout_key),
            "device_class": self.get_config("Device Class", None, readout_key),
            "topic": topic,
            "precision": self.get_config("Precision", 0, readout_key),
            "values": {},
        }

    def __reboot_device(self):
        pass
