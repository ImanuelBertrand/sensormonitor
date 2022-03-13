import time
from config import Config
from i2c import I2C
import json
import os.path
import random
import sgp30
import datetime
import logging
from pprint import pp


class AbstractSensor:
    def __init__(self, config: dict):
        self.config = config

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
            _key = 'Readouts.' + str(readout_key) + '.' + key
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
        return datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S%z")

    def get_readout_keys(self):
        values = self.get_config("Readouts")
        if not isinstance(values, dict):
            return [None]
        else:
            return values.keys()

    def get_result_template(self, readout_key=None):
        name = self.get_config('Name', "", readout_key)
        group = self.get_config('Group', "", readout_key)
        topic = self.get_config('Topic', "sensors/" + group + "/" + name, readout_key)
        return {
            "name": name,
            "group": self.get_config('Group', "", readout_key),
            "friendly_name": self.get_config('Friendly Name', name, readout_key),
            'unit_of_measure': self.get_config('Unit', None, readout_key),
            "device_class": self.get_config("Device Class", None, readout_key),
            "topic": topic,
            "precision": self.get_config("Precision", 0, readout_key),
            "values": {}
        }


class SensorSgp30(AbstractSensor):
    sgp30_device: sgp30.SGP30 = None

    def __init__(self, config: dict):
        super().__init__(config)

    def __save_baseline(self):
        sensor = self.__get_device()
        baseline = sensor.get_baseline()
        file = open(self.__get_sgp30_baseline_file(sensor), 'w')
        json.dump({'co2': baseline.equivalent_co2, 'voc': baseline.total_voc}, file)
        file.close()

    @staticmethod
    def __get_sgp30_baseline_file(sensor: sgp30.SGP30) -> str:
        return os.path.dirname(__file__) + "/sgp30_baseline_" + str(sensor.get_unique_id())

    def __get_device(self) -> sgp30.SGP30:
        if self.sgp30_device is None:
            self.sgp30_device = sgp30.SGP30(i2c_addr=self._get_i2c_address(0x58))
            logging.info("Starting SGP30 sensor")
            self.sgp30_device.start_measurement()

            if os.path.exists(self.__get_sgp30_baseline_file(self.sgp30_device)):
                logging.info("Loading baseline")
                f = open(self.__get_sgp30_baseline_file(self.sgp30_device), 'r')
                contents = f.read()
                f.close()
                bl = json.loads(contents)
                if not isinstance(bl, dict):
                    bl = {}
                if 'co2' not in bl:
                    bl['co2'] = None
                if 'voc' not in bl:
                    bl['voc'] = None

                if bl['co2'] is not None and bl['voc'] is not None:
                    logging.info("Setting baseline: " + str(bl['co2']) + ' / ' + str(bl['voc']))
                    self.sgp30_device.set_baseline(bl['co2'], bl['voc'])

        return self.sgp30_device

    def __read(self):
        return self.__get_device().get_air_quality()

    def read(self):
        return self.__get_device().get_air_quality()


class Sensor(AbstractSensor):
    sgp30_devices = None

    def __init__(self, config: dict):
        super().__init__(config)
        Sensor.sgp30_devices = {}
        self.last_read = 0
        self.sgp30 = None
        self.values = {}
        self.validate_config()
        if self.backend == 'sgp30':
            self.get_sgp30()

    def get_sgp30(self):
        i2c_address = self._get_i2c_address()
        if i2c_address not in Sensor.sgp30_devices:
            Sensor.sgp30_devices[i2c_address] = SensorSgp30(self.config)
        return Sensor.sgp30_devices[i2c_address]

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
            register = self.get_config('I2C.Register', 0, readout_key=readout)
            length = self.get_config('I2C.Length', readout_key=readout)
            scale = self.get_config('Scale', 1, readout)

            _data = data[register:register + length]
            value = 0
            for entry in _data:
                value = value << 8 | entry

            _result = self.get_result_template(readout)
            _result["values"][t] = value / scale
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
                raise Exception('SGP30.Index not defined for readout ' + key + '!')

            if index == 'equivalent_co2':
                _value = value.equivalent_co2
            elif index == 'total_voc':
                _value = value.total_voc
            else:
                raise Exception('Invalid SGP30.Index for readout ' + key + '!')

            _result = self.get_result_template(key)
            _result["values"][t] = _value
            results.append(_result)

        return results

    def should_read_now(self):
        return time.time() - self.last_read >= Config.get_interval(self.get_config('Interval', "1s"))

    def read(self):
        self.last_read = time.time()
        if self.backend == 'i2c':
            return self.__read_i2c()

        if self.backend == 'sgp30':
            return self.__read_sgp30()

        if self.backend == 'random':
            t = datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S%z")
            _result = self.get_result_template(None)
            _result["values"][t] = random.randint(0, 100)
            return [_result]

        raise Exception("Sensor type undefined")
