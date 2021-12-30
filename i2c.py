import smbus2


class I2C:
    buses: dict = {}

    @staticmethod
    def get_bus(nr):
        if nr not in I2C.buses:
            I2C.buses[nr] = smbus2.SMBus(nr)
        return I2C.buses[nr]

    @staticmethod
    def close_all():
        for nr in I2C.buses:
            I2C.buses[nr].close()
        I2C.buses = {}
