import logging
import time

import adafruit_ahtx0
import board

from sensor_abstract import AbstractSensor

# noinspection PyUnresolvedReferences
import RPi.GPIO as GPIO


class SensorAhtx0(AbstractSensor):
    device: adafruit_ahtx0.AHTx0 = None

    def __init__(self, config: dict):
        super().__init__(config)

    def __get_device(self) -> adafruit_ahtx0.AHTx0:
        if self.device is None:
            logging.info("Starting AHTx0 sensor")
            pin = self.get_config("GPIO.Power", False)
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
        if index == "relative_humidity":
            return self.__get_device().relative_humidity
        if index == "temperature":
            return self.__get_device().temperature
        raise Exception("Wrong AHTx0 index (" + index + ")!")
