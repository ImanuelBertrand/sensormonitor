import random

from config import Config


class Sensor:
    name: str
    group: str
    backend: str
    config: dict

    def __init__(self, name: str, group: str, backend: str, config: dict):
        self.name = name
        self.group = group
        self.backend = backend
        self.config = config

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
