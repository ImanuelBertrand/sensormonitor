from config import Config


class Sensor:
    name: str
    group: str
    Type: str
    config: dict

    def read_i2c(self):
        address = self.get_config("i2c.address")
        if address is None:
            raise Exception("I2C address not defined")

    def get_config(self, key, default=None):
        return Config.get(key=key, default=default, data=self.config)

    def get_value(self):
        if self.Type == 'i2c':
            return self.read_i2c()
        raise Exception("Sensor type undefined")
