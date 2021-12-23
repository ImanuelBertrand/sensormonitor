import yaml
from os.path import exists
from enum import Enum


class Config:
    data: dict = None
    config_file: str = 'conf.yml'

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
    def dump():
        print(Config.get_config_data())