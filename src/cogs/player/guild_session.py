from typing import List, Union, Dict
from src.cogs.player.request_queue import RequestQueue
from src.player.media_metadata import MediaMetadata
from src.cogs.player.utils import NO_LOOP
from copy import deepcopy
import os
from constants import MUSIC_STORAGE


class GuildSession:
    def __init__(self):
        self.queue: List[MediaMetadata] = list()                            # represents the queue that is being played in the voice channel
        self.request_queue: RequestQueue = RequestQueue()                   # represents the object that handles the loading of media
        self.loop: int = NO_LOOP                                            # represents whether the audio is looped or not in a guild
        
        self.loop_count: Union[Dict[MediaMetadata, int], None] = None       # represents how many times an audio is looped. This applies to the loop with number argument
        self.loop_counter: int = 0                                          # represents how many times an audio has been looped. Again, this applies to the loop command with the number argument

        self.selected_chapter: Dict[MediaMetadata, int] = {}                # represents the current chapter
        self.song_title_suffix: Dict[MediaMetadata, str] = {}

        self.cur_song: Union[MediaMetadata, None] = None
        self.previous_song: Union[MediaMetadata, None] = None
        self.cur_processing: bool = False
        self.retry_count: int = 0
        self.cached_options: Dict[MediaMetadata, Dict[str, str]] = {}
        self.requires_download: List[MediaMetadata] = list()

        self.timeout_timer = 0


    @staticmethod
    def _delete_files(song_metadata: MediaMetadata):
        fp = os.path.join(MUSIC_STORAGE, f"{song_metadata.id}.mp3")
        try:
            if os.path.isfile(fp) or os.path.islink(fp):
                os.unlink(fp)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (fp, e))

    def reset(self):
        bogus_queue = deepcopy(self.queue)
        for item in bogus_queue:
            self._delete_files(item)
        self.queue.clear()
        self.request_queue = RequestQueue()
        self.cur_song = None
        self.loop = NO_LOOP
        self.loop_count = None
        self.loop_counter = 0

        self.selected_chapter.clear()
        self.song_title_suffix.clear()
        self.cur_song = None
        self.previous_song = None
        self.cur_processing = False
        self.retry_count = 0
        self.cached_options.clear()
        self.requires_download = list()

        self.timeout_timer = 0