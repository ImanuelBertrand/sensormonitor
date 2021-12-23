from config import Config


class SensorMonitor:
    sensors = None

    @staticmethod
    def run():
        Config.dump()
        sensors = Config.get("Sensors")
        for name in sensors:
            print(name)

        pass
