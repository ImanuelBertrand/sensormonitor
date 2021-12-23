import logging
from sensormonitor import SensorMonitor

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', filename='monitor.log',
                    encoding='utf-8', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S%z')

SensorMonitor.run()
