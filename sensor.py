from i2c import I2C
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
        bus_nr = self.get_config("I2C.Bus")
        address = self.get_config("I2C.Address")
        register = self.get_config("I2C.Register")
        length = self.get_config("I2C.Length")
        scale = self.get_config("I2C.Scale")

        if address is None:
            raise Exception("I2C address not defined")

        bus = I2C.get_bus(bus_nr)
        data = bus.read_i2c_block_data(address, register, length)

        value = 0
        for entry in data:
            value = (value << 8) + entry

        return value / scale

    def get_config(self, key, default=None):
        return Config.get(key=key, default=default, data=self.config)

    def read(self):
        if self.backend == 'i2c':
            return self.read_i2c()
        if self.backend == 'random':
            return random.randint(0, 100)
        raise Exception("Sensor type undefined")
