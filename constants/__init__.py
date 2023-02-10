from .bot_config import BotConfig
import os

BOT_API_TOKEN = BotConfig().api_token
BOT_PREFIX = ">3"

ROOT_FOLDER = os.path.dirname(os.path.realpath(__file__))
MUSIC_STORAGE = os.path.join(ROOT_FOLDER, "music_storage")

MAX_MSG_EMBED_SIZE = 1024
CONFIG_FILE_LOC = "config.ini"