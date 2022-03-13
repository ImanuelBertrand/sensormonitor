import re

import yaml
from os.path import exists
import os


class Config:
    data: dict = None
    config_file: str = os.path.dirname(__file__) + '/conf.yml'

    @staticmethod
    def load_file(file_name: str):
        if exists(Config.config_file):
            with open(file_name) as file:
                Config.data = yaml.safe_load(file)
            if Config.data is None:
                Config.data = {}
        else:
            Config.data = {}

    @staticmethod
    def get_config_data():
        if Config.data is None:
            Config.load_file(Config.config_file)
        return Config.data

    @staticmethod
    def get(key: str, default=None, data=None):
        if data is None:
            data = Config.get_config_data()

        path = key.split('.')
        for step in path:
            if step in data:
                data = data[step]
            else:
                return default
        return data

    @staticmethod
    def get_interval(value=None):
        if value is None:
            value = str(Config.get("Interval"))

        if value is None:
            raise Exception("Missing interval configuration")
        match = re.fullmatch(r"(\d+)([smh]?)", value)
        if match is None:
            raise Exception("Invalid interval configuration")

        number = int(match.group(1))
        unit = match.group(2)
        factor = {"": 1, "s": 1, "m": 60, "h": 3600}.get(unit)
        return number * factor

    @staticmethod
    def dump():
        print(Config.get_config_data())
