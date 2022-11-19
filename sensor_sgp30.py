import json
import logging
import os
import time

import sgp30

from config import Config
from sensor_abstract import AbstractSensor

# noinspection PyUnresolvedReferences
import RPi.GPIO as GPIO


class SensorSgp30(AbstractSensor):
    sgp30_device = None
    last_reboot = None

    def __init__(self, config: dict):
        super().__init__(config)

    def __save_baseline(self):
        sensor = self.__get_device()
        baseline = sensor.get_baseline()
        file = open(self.__get_sgp30_baseline_file(sensor), "w")
        json.dump({"co2": baseline.equivalent_co2, "voc": baseline.total_voc}, file)
        file.close()

    def __get_device(self) -> sgp30.SGP30:
        if self.sgp30_device is None:
            try:
                self.__boot_device()
            except Exception as e:
                logging.critical(e)
            self.last_reboot = time.time()

        reboot_interval = self.get_config("RebootInterval", False)
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
            f = open(self.__get_sgp30_baseline_file(self.sgp30_device), "r")
            contents = f.read()
            f.close()
            bl = json.loads(contents)
            if not isinstance(bl, dict):
                bl = {}
            if "co2" not in bl:
                bl["co2"] = None
            if "voc" not in bl:
                bl["voc"] = None

            if bl["co2"] is not None and bl["voc"] is not None:
                logging.info(
                    "Setting baseline: " + str(bl["co2"]) + " / " + str(bl["voc"])
                )
                self.sgp30_device.set_baseline(bl["co2"], bl["voc"])

        return self.sgp30_device

    @staticmethod
    def __get_sgp30_baseline_file(sensor: sgp30.SGP30) -> str:
        return (
            os.path.dirname(__file__) + "/sgp30_baseline_" + str(sensor.get_unique_id())
        )

    def __power_on(self):
        logging.info("Powering on " + self.backend)
        pin = self.get_config("GPIO.Power", False)
        GPIO.output(pin, GPIO.HIGH)

    def __power_off(self):
        logging.info("Powering off " + self.backend)
        pin = self.get_config("GPIO.Power", False)
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
