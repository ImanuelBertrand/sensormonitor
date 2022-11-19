import logging
import time

import adafruit_shtc3
import board

from sensor_abstract import AbstractSensor

# noinspection PyUnresolvedReferences
import RPi.GPIO as GPIO


class SensorShtc3(AbstractSensor):
    device: adafruit_shtc3.SHTC3 = None

    def __init__(self, config: dict):
        super().__init__(config)

    def __get_device(self) -> adafruit_shtc3.SHTC3:
        if self.device is None:
            logging.info("Starting SHTC3 sensor")
            pin = self.get_config("GPIO.Power", False)
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
