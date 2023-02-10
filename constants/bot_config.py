import configparser
from typing import Union
from pathlib import Path
from src.logger import BotHandler
from constants.exceptions import *
import os
import logging

ENVIRONMENT_NAME = 'MUSIC_DISCORD_BOT_API_KEY'


class BotConfig:
    """
    Sets up basic configurations for the bot.
    """
    def __init__(self, config_file: Union[str, Path] = "bot_core_config.ini"):
        self._config_logger = logging.getLogger(__name__)
        self._config_logger.setLevel(logging.INFO)
        self._config_logger.addHandler(BotHandler())
        
        self._config_logger.info("Setting up the bot... Please wait a moment.")
        self._config_file = config_file
        if not os.path.isfile(config_file):
            self._config_logger.info("Config file not found, creating a new one.")
            self._create_new_config(self.__first_time_run())
            self._config_logger.info("Config file created. Continuing setting up the bot...")

        self._data = self._read_config()
        
    def __first_time_run(self):
        if ENVIRONMENT_NAME in os.environ:
            return os.environ[ENVIRONMENT_NAME]
        else:
            raise EnvironmentVariableNotFoundException("The environment variable must be manually set before using this script.")

    def _create_new_config(self, api_key: str):
        config = configparser.ConfigParser()
        config['DEFAULT'] = {
            'API_KEY': api_key
        }
        
        with open(self._config_file, 'w') as cf:
            config.write(cf)

    def _read_config(self):
        config = configparser.ConfigParser()
        config.read(self._config_file)
        return self.__verify(config['DEFAULT']['API_KEY'])

    def __verify(self, api_key:str):
        if ENVIRONMENT_NAME in os.environ:
            return api_key if api_key == os.environ[ENVIRONMENT_NAME] else None
        else:
            raise EnvironmentVariableNotFoundException("The environment variable must be manually set before using this script.")

    @property
    def api_token(self):
        if not self._data:
            raise ModificationFoundException("The config file has been manually edited - please check the key in the config file.")
        else:
            return self._data

