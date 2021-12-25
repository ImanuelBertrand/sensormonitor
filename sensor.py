import random

from config import Config


class Sensor:
    config: dict

    def __init__(self, config: dict):
        self.config = config
        self.validate_config()

    @property
    def name(self):
        return self.get_config("Name")

    @property
    def group(self):
        return self.get_config("Group")

    @property
    def backend(self):
        return self.get_config("Backend")

    def validate_config(self):
        if not self.name or not self.group or not self.backend:
            raise Exception("Sensor setup incomplete - Name, Group and Backend must be set!")

    def read_i2c(self):
        address = self.get_config("i2c.address")
        if address is None:
            raise Exception("I2C address not defined")

    def get_config(self, key, default=None):
        return Config.get(key=key, default=default, data=self.config)

    def read(self):
        if self.backend == 'i2c':
            return self.read_i2c()
        if self.backend == 'random':
            return random.randint(0, 100)
        raise Exception("Sensor type undefined")
