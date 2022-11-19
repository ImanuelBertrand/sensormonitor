import logging
import time

from sensor_abstract import AbstractSensor

# noinspection PyUnresolvedReferences
import RPi.GPIO as GPIO
import scd30_i2c


class SensorScd30(AbstractSensor):
    device: scd30_i2c.SCD30 = None

    def __init__(self, config: dict):
        super().__init__(config)

    def __get_device(self) -> scd30_i2c.SCD30:
        if self.device is None:
            logging.info("Starting SCD30 sensor")
            pin = self.get_config("GPIO.Power", False)
            if pin:
                GPIO.output(pin, GPIO.LOW)
                time.sleep(0.2)
                GPIO.output(pin, GPIO.HIGH)
            device = None
            try:
                device = scd30_i2c.SCD30()
                device.set_measurement_interval(2)
                device.start_periodic_measurement()
            except Exception as e:
                logging.info(e)
            self.device = device

        return self.device

    def read(self, index=None):
        device = self.__get_device()
        start_time = time.time()
        while not device.get_data_ready() and time.time() - start_time < 5:
            time.sleep(0.2)
        if not device.get_data_ready():
            return None
        measurements = self.__get_device().read_measurement()
        if measurements is None:
            return None

        if index is None:
            return measurements

        if index == "co2":
            return measurements[0]
        if index == "temperature":
            return measurements[1]
        if index == "humidity":
            return measurements[2]
        raise Exception("Wrong SCD30 index (" + index + ")!")
