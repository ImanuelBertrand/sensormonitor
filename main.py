#!/usr/bin/python3
import logging
from sensormonitor import SensorMonitor
import os
import traceback

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                    filename=os.path.dirname(__file__) + '/monitor.log',
                    encoding='utf-8', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S%z')

try:
    SensorMonitor.run()
except Exception as e:
    logging.error(type(e))
    logging.error(e)
    logging.error(traceback.format_exc())
    raise
