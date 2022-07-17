import datetime
import json
import logging
import os.path
import random
import time
import traceback

import adafruit_shtc3
import adafruit_ahtx0

import board
import sgp30

from config import Config
from i2c import I2C
# noinspection PyUnresolvedReferences
import RPi.GPIO as GPIO


class AbstractSensor:
    def __init__(self, config: dict):
        self.config = config
        pin = self.get_config('GPIO.Power', False)
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

    def __reboot_device(self):
        pass


class SensorShtc3(AbstractSensor):
    device: adafruit_shtc3.SHTC3 = None

    def __init__(self, config: dict):
        super().__init__(config)

    def __get_device(self) -> adafruit_shtc3.SHTC3:
        if self.device is None:
            logging.info("Starting SHTC3 sensor")
            pin = self.get_config('GPIO.Power', False)
            if pin:
                GPIO.output(pin, GPIO.LOW)
                time.sleep(0.2)
                GPIO.output(pin, GPIO.HIGH)
            i2c = board.I2C()
            device = None
            try:
                device = adafruit_shtc3.SHTC3(i2c)
            except Exception as e:
                logging.info(e)
            self.device = device

        return self.device

    def read(self):
        return self.__get_device().measurements


class SensorAhtx0(AbstractSensor):
    device: adafruit_ahtx0.AHTx0 = None

    def __init__(self, config: dict):
        super().__init__(config)

    def __get_device(self) -> adafruit_ahtx0.AHTx0:
        if self.device is None:
            logging.info("Starting AHTx0 sensor")
            pin = self.get_config('GPIO.Power', False)
            if pin:
                GPIO.output(pin, GPIO.LOW)
                time.sleep(0.2)
                GPIO.output(pin, GPIO.HIGH)
            i2c = board.I2C()
            device = None
            try:
                device = adafruit_ahtx0.AHTx0(i2c)
            except Exception as e:
                logging.info(e)
            self.device = device

        return self.device

    def read(self, index):
        if index == 'relative_humidity':
            return self.__get_device().relative_humidity
        if index == 'temperature':
            return self.__get_device().temperature
        raise Exception("Wrong AHTx0 index (" + index + ")!")


class SensorSgp30(AbstractSensor):
    sgp30_device = None
    last_reboot = None

    def __init__(self, config: dict):
        super().__init__(config)

    def __save_baseline(self):
        sensor = self.__get_device()
        baseline = sensor.get_baseline()
        file = open(self.__get_sgp30_baseline_file(sensor), 'w')
        json.dump({'co2': baseline.equivalent_co2, 'voc': baseline.total_voc}, file)
        file.close()

    def __get_device(self) -> sgp30.SGP30:
        if self.sgp30_device is None:
            try:
                self.__boot_device()
            except Exception as e:
                logging.critical(e)
            self.last_reboot = time.time()

        reboot_interval = self.get_config('RebootInterval', False)
        if reboot_interval:
            reboot_interval = Config.parse_time(reboot_interval)
            if time.time() - self.last_reboot >= reboot_interval:
                self.last_reboot = time.time()
                self.__reboot_device()

        return self.sgp30_device

    def __boot_device(self):
        logging.info("Starting SGP30 sensor")
        self.__power_on()
        time.sleep(10)
        self.sgp30_device = sgp30.SGP30(i2c_addr=self._get_i2c_address(0x58))
        logging.info("Warming up SGP30 sensor")
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

    @staticmethod
    def __get_sgp30_baseline_file(sensor: sgp30.SGP30) -> str:
        return os.path.dirname(__file__) + "/sgp30_baseline_" + str(sensor.get_unique_id())

    def __power_on(self):
        logging.info("Powering on " + self.backend)
        pin = self.get_config('GPIO.Power', False)
        GPIO.output(pin, GPIO.HIGH)

    def __power_off(self):
        logging.info("Powering off " + self.backend)
        pin = self.get_config('GPIO.Power', False)
        GPIO.output(pin, GPIO.LOW)
        self.sgp30_device = None

    def __reboot_device(self):
        logging.info("Rebooting " + self.backend)
        self.__power_off()
        time.sleep(1)
        self.__get_device()

    def __read(self):
        return self.__get_device().get_air_quality()

    def read(self):
        return self.__get_device().get_air_quality()


class Sensor(AbstractSensor):
    devices = {}

    def __init__(self, config: dict):
        super().__init__(config)
        self.last_value = None
        self.last_read = 0
        self.sgp30 = None
        self.values = {}
        self.validate_config()

    def get_sgp30(self):
        i2c_address = self._get_i2c_address()
        if 'sgp30' + i2c_address not in Sensor.devices:
            Sensor.devices['sgp30' + i2c_address] = SensorSgp30(self.config)
        return Sensor.devices['sgp30' + i2c_address]

    def get_shtc3(self):
        if 'shtc3' not in self.devices:
            self.devices['shtc3'] = SensorShtc3(self.config)
        return self.devices['shtc3']

    def get_ahtx0(self):
        if 'ahtx0' not in self.devices:
            self.devices['ahtx0'] = SensorAhtx0(self.config)
        return self.devices['ahtx0']

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
            _result["values"][t] = value / scale + self.get_config('Offset', 0, readout)
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
                _value = value.equivalent_co2 + self.get_config('Offset', 0, key)
            elif index == 'total_voc':
                _value = value.total_voc + self.get_config('Offset', 0, key)
            else:
                raise Exception('Invalid SGP30.Index for readout ' + key + '!')

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
                raise Exception('SHTC3.Index not defined for readout ' + key + '!')

            if index == 'temperature':
                _value = temperature + self.get_config('Offset', 0, key)
            elif index == 'relative_humidity':
                _value = relative_humidity + self.get_config('Offset', 0, key)
            else:
                raise Exception('Invalid SHTC3.Index for readout ' + key + '!')

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
                raise Exception('AHTx0.Index not defined for readout ' + key + '!')

            _value = self.get_ahtx0().read(index) + self.get_config('Offset', 0, key)

            _result = self.get_result_template(key)
            _result["values"][t] = _value
            results.append(_result)

        return results

    def should_read_now(self):
        return time.time() - self.last_read >= Config.get_interval(self.get_config('Interval', "1s"))

    def read(self):
        try:
            if self.backend == 'i2c':
                self.last_value = self.__read_i2c()
                return self.last_value

            if self.backend == 'sgp30':
                self.last_value = self.__read_sgp30()
                return self.last_value

            if self.backend == 'shtc3':
                self.last_value = self.__read_shtc3()
                return self.last_value

            if self.backend == 'ahtx0':
                self.last_value = self.__read_ahtx0()
                return self.last_value

            if self.backend == 'random':
                t = datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S%z")
                _result = self.get_result_template(None)
                _result["values"][t] = random.randint(0, 100)
                return [_result]

            raise Exception("Sensor type undefined")
        except Exception as e:
            logging.critical(e)
            logging.critical(traceback.format_exc())
