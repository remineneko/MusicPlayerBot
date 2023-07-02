from typing import List, Union, Dict
from src.cogs.player.request_queue import RequestQueue
from src.player.media_metadata import MediaMetadata
from src.cogs.player.utils import NO_LOOP
from copy import deepcopy
import os
from constants import MUSIC_STORAGE


class GuildSession:
    def __init__(self):
        """ Represents a session in a guild.
        A "session" starts when the bot joins the voice channel, 
            and the "session" ends when the bot leaves the voice channel.
        """
        self.queue: List[MediaMetadata] = list()                            # represents the queue that is being played in the voice channel
        self.request_queue: RequestQueue = RequestQueue()                   # represents the object that handles the loading of media
        self.loop: int = NO_LOOP                                            # represents whether the audio is looped or not in a guild
        
        self.loop_count: Union[Dict[MediaMetadata, int], None] = None       # represents how many times an audio is looped. 
                                                                            # This applies to the loop with number argument
        self.loop_counter: int = 0                                          # represents how many times an audio has been looped. 
                                                                            # Again, this applies to the loop command with the number argument

        self.selected_chapter: Dict[MediaMetadata, int] = {}                # represents the selected chapter for the playchapter command
        self.song_title_suffix: Dict[MediaMetadata, str] = {}               # represents the suffix that the title has when playchapter is evoked

        self.cur_song: Union[MediaMetadata, None] = None                    # represents the current song that is being played in the voice channel
        self.previous_song: Union[MediaMetadata, None] = None               # represents the previous song that played in the voice channel
        self.cur_processing: bool = False                                   # represents whether the queue is being processed or not
        self.retry_count: int = 0                                           # represents the number of retries for a song when a song fails to load
        self.cached_options: Dict[MediaMetadata, Dict[str, str]] = {}       # represents the FFMPEG options stored to play the video, chapter-wise
        self.requires_download: List[MediaMetadata] = list()                # represents the list of songs that requires downloading prior to playing

        self.timeout_timer = 0                                              # represents the current timer for the bot when there is no one else in the voice channel
        self.is_active = False                                              # represents whether the guild is currently using the bot in voice channel or not.  

    @staticmethod
    def _delete_files(song_metadata: MediaMetadata):
        """ Deletes the files correspond to the metadata given

        Args:
            song_metadata (MediaMetadata): _description_
        """
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
        self.is_active = False