import datetime
import logging
import random
import time
import traceback

from config import Config
from i2c import I2C

# noinspection PyUnresolvedReferences
import RPi.GPIO as GPIO

from sensor_abstract import AbstractSensor
from sensor_ahtx0 import SensorAhtx0
from sensor_gme680 import SensorGme680
from sensor_htu31d import SensorHtu31d
from sensor_sgp30 import SensorSgp30
from sensor_shtc3 import SensorShtc3
from sensor_scd30 import SensorScd30


class Sensor(AbstractSensor):
    devices = {}

    def __init__(self, config: dict):
        super().__init__(config)
        self.last_value = None
        self.last_read = 0
        self.sgp30 = None
        self.values = {}
        self.validate_config()

    def get_htu31d(self):
        if "htu31d" not in self.devices:
            self.devices["htu31d"] = SensorHtu31d(self.config)
        return self.devices["htu31d"]

    def get_sgp30(self):
        i2c_address = self._get_i2c_address()
        if "sgp30" + i2c_address not in Sensor.devices:
            Sensor.devices["sgp30" + i2c_address] = SensorSgp30(self.config)
        return Sensor.devices["sgp30" + i2c_address]

    def get_shtc3(self):
        if "shtc3" not in self.devices:
            self.devices["shtc3"] = SensorShtc3(self.config)
        return self.devices["shtc3"]

    def get_ahtx0(self):
        if "ahtx0" not in self.devices:
            self.devices["ahtx0"] = SensorAhtx0(self.config)
        return self.devices["ahtx0"]

    def get_gme680(self):
        if "gme680" not in self.devices:
            self.devices["gme680"] = SensorGme680(self.config)
        return self.devices["gme680"]

    def get_scd30(self):
        if "scd30" not in self.devices:
            self.devices["scd30"] = SensorScd30(self.config)
        return self.devices["scd30"]

    def validate_config(self):
        if not self.backend:
            raise Exception("Sensor setup incomplete - Backend must be set!")

    def get_i2c_block_size(self):
        t = 0
        for readout_key in self.get_readout_keys():
            register = self.get_config("I2C.Register", 1000, readout_key)
            length = self.get_config("I2C.Length", 1000, readout_key)
            t = max(t, register + length)
        return t

    def __read_i2c(self):
        bus_nr = self._get_i2c_bus()
        address = self._get_i2c_address()

        if address is None:
            raise Exception("I2C address not defined")

        bus = I2C.get_bus(bus_nr)

        try:
            data: list = bus.read_i2c_block_data(address, 0, self.get_i2c_block_size())
        except IOError:
            return None

        results = []
        t = self.get_time()
        for readout in self.get_readout_keys():
            register = self.get_config("I2C.Register", 0, readout_key=readout)
            length = self.get_config("I2C.Length", readout_key=readout)
            scale = self.get_config("Scale", 1, readout)

            _data = data[register : register + length]
            value = 0
            for entry in _data:
                value = value << 8 | entry

            _result = self.get_result_template(readout)
            _result["values"][t] = value / scale + self.get_config("Offset", 0, readout)
            results.append(_result)
        return results

    def __read_sgp30(self):
        try:
            value = self.get_sgp30().read()
        except IOError:
            return None

        results = []

        t = self.get_time()

        for key in self.get_readout_keys():
            index = self.get_config("SGP30.Index", readout_key=key)
            if index is None:
                raise Exception("SGP30.Index not defined for readout " + key + "!")

            if index == "equivalent_co2":
                _value = value.equivalent_co2 + self.get_config("Offset", 0, key)
            elif index == "total_voc":
                _value = value.total_voc + self.get_config("Offset", 0, key)
            else:
                raise Exception("Invalid SGP30.Index for readout " + key + "!")

            _result = self.get_result_template(key)
            _result["values"][t] = _value
            results.append(_result)

        return results

    def __read_htu31d(self):
        try:
            temperature, relative_humidity = self.get_htu31d().read()
        except IOError:
            return None

        results = []

        t = self.get_time()

        for key in self.get_readout_keys():
            index = self.get_config("HTU31D.Index", readout_key=key)
            if index is None:
                raise Exception("HTU31D.Index not defined for readout " + key + "!")

            if index == "temperature":
                _value = temperature + self.get_config("Offset", 0, key)
            elif index == "relative_humidity":
                _value = relative_humidity + self.get_config("Offset", 0, key)
            else:
                raise Exception("Invalid HTU31D.Index for readout " + key + "!")

            _result = self.get_result_template(key)
            _result["values"][t] = _value
            results.append(_result)

        return results

    def __read_shtc3(self):
        try:
            temperature, relative_humidity = self.get_shtc3().read()
        except IOError as e:
            logging.error(e)
            return None

        results = []

        t = self.get_time()

        for key in self.get_readout_keys():
            index = self.get_config("SHTC3.Index", readout_key=key)
            if index is None:
                raise Exception("SHTC3.Index not defined for readout " + key + "!")

            if index == "temperature":
                _value = temperature + self.get_config("Offset", 0, key)
            elif index == "relative_humidity":
                _value = relative_humidity + self.get_config("Offset", 0, key)
            else:
                raise Exception("Invalid SHTC3.Index for readout " + key + "!")

            _result = self.get_result_template(key)
            _result["values"][t] = _value
            results.append(_result)

        return results

    def __read_ahtx0(self):

        results = []

        t = self.get_time()

        for key in self.get_readout_keys():
            index = self.get_config("AHTx0.Index", readout_key=key)
            if index is None:
                logging.info(self.config)
                raise Exception("AHTx0.Index not defined for readout " + key + "!")

            _value = self.get_ahtx0().read(index) + self.get_config("Offset", 0, key)

            _result = self.get_result_template(key)
            _result["values"][t] = _value
            results.append(_result)

        return results

    def __read_gme680(self):

        results = []

        t = self.get_time()

        for key in self.get_readout_keys():
            index = self.get_config("GME680.Index", readout_key=key)
            if index is None:
                logging.info(self.config)
                raise Exception("GME680.Index not defined for readout " + key + "!")

            _value = self.get_gme680().read(index) + self.get_config("Offset", 0, key)

            _result = self.get_result_template(key)
            _result["values"][t] = _value
            results.append(_result)

        return results

    def __read_scd30(self):
        try:
            measurements = self.get_scd30().read()
            if measurements is None:
                return None
            co2, temperature, relative_humidity = measurements
        except IOError:
            return None

        results = []

        t = self.get_time()

        for key in self.get_readout_keys():
            index = self.get_config("SCD30.Index", readout_key=key)
            if index is None:
                raise Exception("SCD30.Index not defined for readout " + key + "!")

            if index == "temperature":
                _value = temperature + self.get_config("Offset", 0, key)
            elif index == "humidity":
                _value = relative_humidity + self.get_config("Offset", 0, key)
            elif index == "co2":
                _value = co2 + self.get_config("Offset", 0, key)
            else:
                raise Exception("Invalid SCD30.Index for readout " + key + "!")

            _result = self.get_result_template(key)
            _result["values"][t] = _value
            results.append(_result)

        return results

    def should_read_now(self):
        return time.time() - self.last_read >= Config.get_interval(
            self.get_config("Interval", "1s")
        )

    def read(self):
        try:
            if self.backend == "i2c":
                self.last_value = self.__read_i2c()
                return self.last_value

            if self.backend == "sgp30":
                self.last_value = self.__read_sgp30()
                return self.last_value

            if self.backend == "shtc3":
                self.last_value = self.__read_shtc3()
                return self.last_value

            if self.backend == "gme680":
                self.last_value = self.__read_gme680()
                return self.last_value

            if self.backend == "htu31d":
                self.last_value = self.__read_htu31d()
                return self.last_value

            if self.backend == "ahtx0":
                self.last_value = self.__read_ahtx0()
                return self.last_value

            if self.backend == "scd30":
                self.last_value = self.__read_scd30()
                return self.last_value

            if self.backend == "random":
                t = datetime.datetime.fromtimestamp(time.time()).strftime(
                    "%Y-%m-%d %H:%M:%S%z"
                )
                _result = self.get_result_template(None)
                _result["values"][t] = random.randint(0, 100)
                return [_result]

            raise Exception("Sensor type undefined")
        except Exception as e:
            logging.critical(e)
            logging.critical(traceback.format_exc())
