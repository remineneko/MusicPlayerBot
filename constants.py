import dotenv
import os

dotenv.load_dotenv()

TOKEN = os.environ.get('BOT_API_TOKEN')
BOT_PREFIX = ">3"

ROOT_FOLDER = os.path.dirname(os.path.realpath(__file__))
MUSIC_STORAGE = os.path.join(ROOT_FOLDER, "music_storage")

MAX_MSG_EMBED_SIZE = 1024
CONFIG_FILE_LOC = "config.ini"
MAX_NUMBER_OF_FILES = 100