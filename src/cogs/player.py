from discord.ext import commands, tasks
import discord
import asyncio
import os
from copy import deepcopy
from typing import Union
from datetime import timedelta
import random
import inspect
from yt_dlp import YoutubeDL
import functools
from constants import MUSIC_STORAGE, MAX_MSG_EMBED_SIZE, CONFIG_FILE_LOC, BOT_PREFIX
from src.player.youtube.search import SearchVideos
from src.player.media_metadata import MediaMetadata
from src.player.youtube.download_media import isExist, SingleDownloader
from src.player.observers import *
from src.data_transfer import *
from src.player.link_identifier import LinkIdentifier
from src.player.load_media import LoadMedia
from src.configs import Config
from src.logger import BotHandler
from dataclasses import dataclass

import re

import logging

YOUTUBEDL_PARAMS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': os.path.join(MUSIC_STORAGE, '%(id)s.%(ext)s'),
}

NO_LOOP = 0
LOOP = 1


async def run_blocker(client, func, *args, **kwargs):
    func_ = functools.partial(func, *args, **kwargs)
    return await client.loop.run_in_executor(None, func_)


def _time_split(time: int):
    return str(timedelta(seconds=time))

@dataclass
class Job:
    """
    Defines a job for the bot to do.

    Args:
        job_name (str): The name of the job. Accepts either 'search' or 'access'.
        work (str): The workload required for the job.
    """
    job: str  # accepts either "search" or "access"
    work: str
    query_type: Union[str, int]
    work_type: str = 'normal' # accepts either 'normal' or 'chapter'


YT_DLP_SESH = YoutubeDL(YOUTUBEDL_PARAMS)


class RequestQueue(DownloaderObservers):
    def __init__(self, observer = DownloaderObservable()):
        super().__init__(observer)
        self.priority: Union[Job, None] = None
        self.on_hold: List[Job] = []
        self._completed_priority = False
        self._ongoing_process = False
    
    def add_new_request(self, job: Job):
        if self.priority is None and not self.on_hold:
            self.priority = job
        elif self.priority is None:
            self.priority = self.on_hold.pop(0)
            self.on_hold.append(job)
        else:
            self.on_hold.append(job)

    def update(self):
        if inspect.stack()[1][3] == "notify_observers":
            self._completed_priority = True

    async def process_requests(self, client, ctx: commands.Context, vault: Vault, selector_choice):
        """
        Projected solution:
            - If self.priority is not None, proceed to download the file(s) in the playlist given in self.priority
            - Other than that, pop one from on_hold and let the process continues
            - If priority is None, and the on_hold list is empty, nothing needs to be done at all. We done!

            - If the download process is completed for one list, continue with the next one.
        """
        def check_valid_input(m):
            return m.author == ctx.author and m.channel == ctx.channel

        if self.priority is not None and self._ongoing_process:
            while not self._completed_priority:
                await asyncio.sleep(1)
            self._completed_priority = False
            self._ongoing_process = False
            await self.process_requests(client, ctx, vault, selector_choice)
        elif self.priority is not None and not self._completed_priority:
            self._ongoing_process = True
            guild_id = ctx.guild.id
            new_sender = Sender(guild_id, vault)

            query = self.priority.work
            if self.priority.job == "search":
                if not selector_choice:
                    sv_obj = SearchVideos()
                    sv_obj.subscribe(self)
                    result: List[MediaMetadata] = await run_blocker(client, sv_obj.search, query)
                    results_embed = discord.Embed(
                        color=discord.Color.blue()
                    )
                    r_link = ""
                    for res_ind, res in enumerate(result):
                        if res_ind != len(result) - 1:
                            r_link += f"**{res_ind + 1}. [{res.title}]({res.original_url})** ({_time_split(res.duration)})\n"
                        else:
                            r_link += f"**{res_ind + 1}. [{res.title}]({res.original_url})** ({_time_split(res.duration)})\n"

                    results_embed.add_field(
                        name="Select a video.",
                        value=r_link,
                        inline=False
                    )
                    results_embed.set_footer(text="Timeout in 30s")
                    await ctx.send(embed=results_embed)

                    try:
                        q_msg = await client.wait_for('message', check=check_valid_input, timeout=30)
                    except asyncio.TimeoutError:
                        self.priority = None
                        return await ctx.send(f"Timeout! Search session for query {query} terminated.")
                    sv_obj.unsubscribe(self)
                    if q_msg.content.isdigit() and 1 <= int(q_msg.content) <= 5:
                        data = [result[int(q_msg.content) - 1]]
                    else:
                        self.priority = None  # reset. This session no longer exists
                        return await ctx.send("Illegal input. Terminated search session.")
                else:
                    sv_obj = SearchVideos(limit=1)
                    sv_obj.subscribe(self)
                    data: List[MediaMetadata] = await run_blocker(client, sv_obj.search, query)
                    sv_obj.unsubscribe(self) # avoid the bot to store far too many unnecessary observants.
            else:
                load_sesh = LoadMedia(query, self.priority.query_type, work_type = self.priority.work_type)
                load_sesh.subscribe(self)
                try:
                    data = await run_blocker(client, load_sesh.load_info)
                except ValueError:
                    return await ctx.send("Cannot load playlist on play chapter requests.")
                load_sesh.unsubscribe(self)

            new_sender.send(data)
            self.priority = None
        elif self.priority is None and self.on_hold:
            self.priority = self.on_hold.pop(0)
            await self.process_requests(client, ctx, vault, selector_choice)
    

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



class QueueMenu(discord.ui.View):
    def __init__(self, queue_embeds):
        super().__init__()
        self.value = None
        self.queue_embeds = queue_embeds
        self._len = len(queue_embeds)
        self.current_index = 0
        
    @discord.ui.button(emoji="<:MillieLeft:1050096572983152650>")
    async def previous_q(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index -= 1
        if self.current_index + self._len == 0:
            self.current_index = 0
        await interaction.response.edit_message(embed = self.queue_embeds[self.current_index])

    @discord.ui.button(emoji="<:MillieRight:1050096570890211458>")
    async def next_q(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index += 1
        if self.current_index - self._len == 0:
            self.current_index = 0
        await interaction.response.edit_message(embed = self.queue_embeds[self.current_index])


class Player(commands.Cog):
    _NEW_PLAYER = 1
    _REFRESH_PLAYER = 0

    _FFMPEG_STREAM_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    _FFMPEG_PLAY_OPTIONS = {
        'options': '-vn',
    }

    _FFMPEG_STREAM_PARTIAL_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_time} -t {fast_forward}',
        'options': '-vn'
    }    

    _ACCESS_JOB = "access"
    _SEARCH_JOB = "search"

    _MAX_RETRY_COUNT = 3

    _MAX_AUDIO_ALLOWED_TIME = 21600

    
    
    # URL_REFRESH_TIME = 21600 # issue found at https://gist.github.com/vbe0201/ade9b80f2d3b64643d854938d40a0a2d?permalink_comment_id=4140046#gistcomment-4140046
                               # basically, if the playlist is set to be played for 6 hrs, the latter links will expire.
                               # though, this should only matter to streaming music, right?

    def __init__(self, bot: discord.ext.commands.Bot):
        self._bot = bot
        self._players: Dict[int, discord.FFmpegPCMAudio] = {}
        self._vault = Vault()
        self._bot_config = Config(CONFIG_FILE_LOC)
        self._guild_sessions: Dict[int, GuildSession] = defaultdict(lambda: GuildSession())

        # Stores information on which guild the bot is staying inside VC 
        self._active_guild_session_cache: Dict[int, GuildSession] = {}                                          

    def get_players(self, ctx, job=_NEW_PLAYER):
        guild_id = ctx.guild.id
        guild_sesh = self._guild_sessions[guild_id]
        if guild_id in self._players and job:
            return self._players[guild_id]
        else:
            if guild_sesh.cur_song not in guild_sesh.requires_download:
                if guild_sesh.cur_song not in guild_sesh.cached_options:
                    player = discord.FFmpegPCMAudio(guild_sesh.cur_song.url, **self._FFMPEG_STREAM_OPTIONS)
                else:
                    s_o = guild_sesh.cached_options[guild_sesh.cur_song]
                    player = discord.FFmpegOpusAudio(guild_sesh.cur_song.url, **s_o)
            else:
                while not os.path.isfile(os.path.join(MUSIC_STORAGE, f"{guild_sesh.cur_song.id}.mp3")):
                    asyncio.run_coroutine_threadsafe(asyncio.sleep(1), ctx.bot.loop)
                player = discord.FFmpegPCMAudio(os.path.join(MUSIC_STORAGE, f"{guild_sesh.cur_song.id}.mp3"),
                                            **self._FFMPEG_PLAY_OPTIONS)
            self._players[guild_id] = player
            return player

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot and member.id == self._bot.user.id:
            if before.channel and not after.channel:
                self._cleanup(member)

        if before.channel is not None:
            guild_ = self._guild_sessions[before.channel.guild.id]
            voice = discord.utils.get(self._bot.voice_clients , channel__guild__id = before.channel.guild.id)
            self._active_guild_session_cache[before.channel.guild.id] = guild_

            # voice is voiceClient and if it's none? that means the bot is not in an y VC of the Guild that triggerd this event 
            if voice is None:
                return

            # if VC left by the user is not equal to the VC that bot is in? then return
            if voice.channel.id != before.channel.id:
                return

            if not after.channel and member.bot and member.id == self._bot.user.id:
                # apparently this is not triggered somehow.
                self._cleanup(member)

            if len(voice.channel.members) <= 1:
                guild_.timeout_timer = 0

                _timeout_logger = logging.getLogger(__name__)
                _timeout_logger.setLevel(logging.INFO)
                _timeout_logger.addHandler(BotHandler())            

                while True:
                    _timeout_logger.info(f"Guild ID: {before.channel.guild.id} Time {guild_.timeout_timer} Total Members in Voice Channel {len(voice.channel.members)}")
                    await asyncio.sleep(1)

                    guild_.timeout_timer += 1

                    # if vc has more than 1 member or bot is already disconnected ?
                    # reset and break. Cooldown no longer applies
            
                    if len(voice.channel.members) >= 2 or not voice.is_connected():
                        guild_.timeout_timer = 0
                        break

                    # if bot has been alone in the VC for more than 300 seconds consecutively ? disconnect
                    if guild_.timeout_timer >= 300:
                        await self.disconnect(voice)
                        self._cleanup(member)

    def _cleanup(self, member: discord.Member):
        print("cleanup is triggered")
        guild_id = member.guild.id
        self._guild_sessions[guild_id].reset()
        try:
            del self._players[guild_id]
        except KeyError:
            pass
                
        self._FFMPEG_STREAM_PARTIAL_OPTIONS = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_time} -t {fast_forward}',
                    'options': '-vn'
        }
        print(f"cleanup applied on guild {guild_id}")


    # @commands.Cog.listener()
    # async def on_voice_state_update(self, member: discord.Member, before, after):
    #     # add cases where ALL users left the VC and the bot is left idle for some time.

    #     if member.bot and member.id == self._bot.user.id:
    #         if before.channel and not after.channel:
    #             guild_id = member.guild.id
    #             self._guild_sessions[guild_id].reset()
    #             try:
    #                 del self._players[guild_id]
    #             except KeyError:
    #                 pass
                
    #             self._FFMPEG_STREAM_PARTIAL_OPTIONS = {
    #                 'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_time} -t {fast_forward}',
    #                 'options': '-vn'
    #             }

    async def process_query(self, ctx: commands.Context, query, process_chapter = False):
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]

        if ctx.interaction:
            await ctx.interaction.response.defer()

        query = query.strip()

        if query:
            query_type = LinkIdentifier(query).url_type
        elif not query and ctx.message.attachments:
            query = ctx.message.attachments[0]
            query_type = LinkIdentifier.NORMAL_URL
        else:
            return await ctx.send("No input has been given.")
        

        if query_type:
            cmd_job = self._ACCESS_JOB
        else:
            cmd_job = self._SEARCH_JOB
        job = Job(cmd_job, query, query_type, work_type='chapter') if process_chapter else Job(cmd_job, query, query_type)
        guild_.request_queue.add_new_request(job)

        # part that is causing errors
        if not guild_.cur_processing:
            self._bot.loop.create_task(self.bg_process_rq(ctx))

    @staticmethod
    def sanitize_(chapters: List[Dict]):
        for chapter in chapters:
            if re.search(r'\<Untitled Chapter (\d+)\>', chapter['title']):
                chapters.remove(chapter)

    @commands.hybrid_command()
    async def playchapter(self, ctx: commands.Context, chapter_index: str, *, query: str):
        """ Plays a chapter in a video.

        Args:
            ctx (commands.Context): _description_
            chapter_index (str): _description_
            query (str): _description_

        """
        try:
            index_chapter = int(chapter_index) - 1
        except ValueError:
            return await ctx.send("The chapter index must be a number")
        
        await self.process_query(ctx, query, True)
        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]

        while self._vault.isEmpty(guild_id):
            await asyncio.sleep(1)

        # both runs at the same time from here.
        data: List[MediaMetadata] = self._vault.get_data(guild_id)
        if len(data) > 1:
            return await ctx.send("playchapter only supports a single video.")
        elif data:
            song: MediaMetadata = data[0]
            if not song.chapters:
                return await ctx.send("The song chosen does not have any chapters.")
            else:
                try:
                    song_copy = deepcopy(song)
                    guild_.selected_chapter[song_copy] = index_chapter
                    # In VERY RARE cases, ss_title and ss_end are flipped.
                    # For instance, the metadata of this [video](https://youtu.be/nB1cpZWWQ5E) has the very first "chapter" having flipped ss_title and ss_end (the 0:00:00 to 0:00:01 one) 
                    # I'm not entirely sure why this is flipped, but all I know that it breaks the program

                    # solution: sanitize the chapters before this is used.
                    self.sanitize_(song.chapters)

                    ss_start, ss_title, ss_end = list(song.chapters[index_chapter].values())
                    
                    ss_start = int(ss_start)
                    ss_end = int(ss_end)
                    
                    suffix = f" - {ss_title}"
                    song.title += suffix
                    guild_.song_title_suffix[song] = suffix
                    
                    self._FFMPEG_STREAM_PARTIAL_OPTIONS = {
                            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_time} -t {fast_forward}',
                            'options': '-vn'
                        } 
                    self._FFMPEG_STREAM_PARTIAL_OPTIONS['before_options'] = self._FFMPEG_STREAM_PARTIAL_OPTIONS['before_options'].format(start_time= ss_start, fast_forward= ss_end - ss_start)
                    guild_.cached_options.update({data[0]: self._FFMPEG_STREAM_PARTIAL_OPTIONS})
                except IndexError:
                    return await ctx.send("The chapter index is higher than the amount the video has. Please check your input")
            await self.time_check(ctx, data, guild_)

            msg = self.get_msg(data)

            guild_.queue.extend(data)
            
            await ctx.send(msg)
            
            try:
                voiceChannel = discord.utils.get(
                    ctx.message.guild.voice_channels,
                    name=ctx.author.guild.get_member(ctx.author.id).voice.channel.name
                    )
            except AttributeError:
                return await ctx.send('You need to be in a voice channel to use this command')

            await self.pre_play_process(ctx, voiceChannel)

    @commands.hybrid_command()
    async def playnextchapter(self, ctx: commands.Context):
        guild_id = ctx.guild.id
        guild_ : GuildSession = self._guild_sessions[guild_id]
      
        if not guild_.selected_chapter:
            return await ctx.send(f"You have no songs that was initialized by {BOT_PREFIX}playchapter command, or your previous call to this command asked for a chapter beyond what the video has.")
        
        cur_song = guild_.cur_song
        data = [deepcopy(cur_song)]
        song = data[0]

        if cur_song not in guild_.song_title_suffix:
            return await ctx.send(f"The current song was not evoked by {BOT_PREFIX}playchapter command.")
        
        try:
            song.title = song.title.removesuffix(guild_.song_title_suffix[cur_song])
            song_copy = deepcopy(song) # so that the data wont be mutated.
            next_index = guild_.selected_chapter[song_copy] + 1
            guild_.selected_chapter[song_copy] = next_index
            ss_start, ss_title, ss_end = list(song.chapters[next_index].values())
                        
            ss_start = int(ss_start)
            ss_end = int(ss_end)

            suffix = f" - {ss_title}"
            
            song.title += suffix
            guild_.song_title_suffix[song] = suffix
            self._FFMPEG_STREAM_PARTIAL_OPTIONS = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_time} -t {fast_forward}',
                'options': '-vn'
            }   
            self._FFMPEG_STREAM_PARTIAL_OPTIONS['before_options'] = self._FFMPEG_STREAM_PARTIAL_OPTIONS['before_options'].format(start_time= ss_start, fast_forward= ss_end - ss_start)

            guild_.cached_options.update({song: self._FFMPEG_STREAM_PARTIAL_OPTIONS})
        except IndexError:
            guild_.selected_chapter.clear()
            guild_.song_title_suffix.clear()
            return await ctx.send("There are no more chapters after this chapter.")

        await self.time_check(ctx, data, guild_)

        msg = self.get_msg(data)

        guild_.queue.extend(data)
        await ctx.send(msg)
            
        try:
            voiceChannel = discord.utils.get(
                ctx.message.guild.voice_channels,
                name=ctx.author.guild.get_member(ctx.author.id).voice.channel.name
                    )
        except AttributeError:
            return await ctx.send('You need to be in a voice channel to use this command')

        await self.pre_play_process(ctx, voiceChannel)

    @commands.hybrid_command()
    async def play(self, ctx: commands.Context, *, query: str = None):
        """
        Plays audio in the voice channel.
        Subsequent calls from users in the same channel will add more media entries to the queue.
        :param ctx: The context of the command.
        :param query: The url, or query to search for the desired video.
        :return:
        """
        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]

        await self.process_query(ctx, query)

        while self._vault.isEmpty(guild_id):
            await asyncio.sleep(1)

        # both runs at the same time from here.
        data = self._vault.get_data(guild_id)
        if data is not None:

            # checking for entries that requires downloading
            # These entries are some but not limited to:
            #  - Entries that are more than 6 hours in play time.
            #  - Entries that make the playlist plays longer than 6 hours 
            # All of this is mainly to preserve the items in the playlist.

            await self.time_check(ctx, data, guild_)

            msg = self.get_msg(data)
            
            guild_.queue.extend(data)
            if ctx.interaction:
                await ctx.interaction.followup.send(msg)
            else:
                await ctx.send(msg)
            
            try:
                voiceChannel = discord.utils.get(
                    ctx.message.guild.voice_channels,
                    name=ctx.author.guild.get_member(ctx.author.id).voice.channel.name
                    )
            except AttributeError:
                return await ctx.send('You need to be in a voice channel to use this command')

            await self.pre_play_process(ctx, voiceChannel)

    # def refresh_stream_link(self, ctx: commands.Context, song: MediaMetadata):
    #     guild_ = self._guild_sessions[ctx.guild.id]
    #     song_url = song.original_url
    #     new_job = Job(self._ACCESS_JOB, song_url)
    #     guild_.request_queue.add_new_request(new_job)
    #     if not guild_.cur_processing:
    #         self._bot.loop.create_task(self.bg_process_rq(ctx))
    
    def get_msg(self, data):
        data_l = len(data)
        if data_l == 1:
            return f"Added {data[0].title} to the queue."
        elif not data_l:
            return "No songs are added."
        else:
            return f"Added {data_l} songs to the queue."

    async def time_check(self, ctx, data, guild_):
        queue_total_play_time = sum([int(i.duration) for i in guild_.queue]) if guild_.queue else 0
        for item_ind, item in enumerate(data):
            if item.duration >= self._MAX_AUDIO_ALLOWED_TIME: # for now, for safety, that is removed
                await ctx.send(f"Video {item.title} is too long! Current max length allowed to be played for individual video is 6 hours! Removed from queue.")
                data.remove(item)
            elif queue_total_play_time + item.duration >= self._MAX_AUDIO_ALLOWED_TIME:
                guild_.requires_download.extend(data[item_ind:])
                break
            else:
                queue_total_play_time += item.duration

    async def pre_play_process(self, ctx, voiceChannel):
        """
        Processes the data before playing the songs in the voice channel.

        Args:
            ctx (commands.Context): Context of the command
            data (List[MediaMetadata]): The data to be processed
            voiceChannel (_type_): The voice channel to connect to

        """
        guild_ = self._guild_sessions[ctx.guild.id]
        
        try:
            if guild_.requires_download:
                self.bg_download_check.start(ctx)
        except RuntimeError:
            pass

        if not self._is_connected(ctx) and guild_.queue:
            await voiceChannel.connect()

        voice = ctx.voice_client
        await self.play_song(ctx, voice)

    async def bg_process_rq(self, ctx):
        """ Processes the requests in the background

        Args:
            ctx (commands.Context): Context of the command
        """
        guild_ = self._guild_sessions[ctx.guild.id]
        guild_.cur_processing = True
        while guild_.cur_processing:
            if guild_.request_queue.on_hold or guild_.request_queue.priority is not None:
                await guild_.request_queue.process_requests(self._bot, ctx, self._vault, self._bot_config.isAutoPick(ctx.guild.id))
            else:
                guild_.cur_processing = False

    @tasks.loop(seconds = 20)
    async def bg_download_check(self, ctx):
        guild_ = self._guild_sessions[ctx.guild.id]

        for item in guild_.requires_download:
            if not isExist(item):
                down_sesh = SingleDownloader(item, YT_DLP_SESH)
                await run_blocker(self._bot, down_sesh.download)

    async def disconnect(self, voice):
        try:
            await voice.disconnect()
        except discord.errors.ConnectionClosed:
            await asyncio.sleep(1)
            await self.disconnect(voice)

    async def play_song(self, ctx: commands.Context, voice, refresh = False):
        guild_ = self._guild_sessions[ctx.guild.id]

        if not voice.is_playing():
            try:
                guild_.cur_song = guild_.queue.pop(0)
            except IndexError:
                guild_.cur_song = None
            if guild_.cur_song is None:
                await self.disconnect(voice)
                return
            player = self.get_players(ctx, self._REFRESH_PLAYER) if refresh else self.get_players(ctx)

            voice.play(
                player,
                after=lambda e:
                self.retry_play(ctx, voice, e) if e else self.play_next(ctx)
                    )

            await ctx.send('**Now playing:** {}'.format(guild_.cur_song.title), delete_after=20)
        else:
            await asyncio.sleep(1)
    
    def retry_play(self, ctx, voice, e):
        guild_ = self._guild_sessions[ctx.guild.id]
        if guild_.retry_count < self._MAX_RETRY_COUNT:
            guild_.retry_count += 1
            guild_.queue.insert(0, guild_.cur_song)
            guild_.cur_song = None
            asyncio.run_coroutine_threadsafe(self.play_song(ctx, voice, True), ctx.bot.loop)
        else:
            print("Player error: %s", e)

    def play_next(self, ctx: commands.Context):
        guild_ = self._guild_sessions[ctx.guild.id]

        vc = discord.utils.get(self._bot.voice_clients, guild=ctx.guild)

        if guild_.loop:
            if guild_.loop_count is not None:
                if guild_.loop_counter < list(guild_.loop_count.values())[0]:
                    guild_.loop_count += 1
                else:
                    guild_.loop = NO_LOOP
                    self.play_next(ctx)
            
            player = self.get_players(ctx, self._REFRESH_PLAYER)
            ctx.voice_client.play(
                player,
                after=lambda e:
                print('Player error: %s' % e) if e else self.play_next(ctx)
            )
            
        elif len(guild_.queue) >= 1:
            try:
                guild_.previous_song = guild_.cur_song
                guild_.cur_song = guild_.queue.pop(0)
                if guild_.cur_song in guild_.requires_download and not isExist(guild_.cur_song):
                    guild_.queue.insert(0, guild_.cur_song)
                    guild_.cur_song = guild_.previous_song
                    guild_.previous_song = None
                    raise IOError("File not exist just yet")
            
            except IndexError:
                guild_.cur_song = None
            if guild_.cur_song is None:
                asyncio.run_coroutine_threadsafe(ctx.send("Finished playing!"), ctx.bot.loop)
                asyncio.run_coroutine_threadsafe(self.disconnect(ctx.voice_client), ctx.bot.loop)
                return
            
            player = self.get_players(ctx, self._REFRESH_PLAYER)
            
            ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))
            
            asyncio.run_coroutine_threadsafe(ctx.send(
                    f'**Now playing:** {guild_.cur_song.title}',
                    delete_after=20
                ), ctx.bot.loop)
        elif ctx.voice_client is None:
            pass
        elif not ctx.voice_client.is_playing():
            asyncio.run_coroutine_threadsafe(vc.disconnect(), self._bot.loop)
            asyncio.run_coroutine_threadsafe(ctx.send("Finished playing!"), ctx.bot.loop)

    @commands.command()
    @commands.is_owner()
    async def debug(self, ctx):
        """Debugs a section of the code. Only the owner can use this.

        Args:
            ctx (commands.Context()): context of the message
        """
        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]
        await ctx.send(guild_.queue)
        if guild_.cur_song is not None:
            await ctx.send(guild_.cur_song)
        else:
            await ctx.send("Currently no song is playing")

        await ctx.send(guild_.queue)
        await ctx.send(guild_.cur_song)

    @commands.hybrid_command(name='stop')
    async def stop_(self, ctx: commands.Context):
        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        if self._is_connected(ctx):
            await self.disconnect(ctx.voice_client)
            await ctx.send("Left the voice channel.")
        else:
            await ctx.send("I am not in any voice chat right now")

    @commands.hybrid_command(name="skip")
    async def skip_(self, ctx):
        """
        Skips to next song in queue
        """
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        if self._is_connected(ctx):
            ctx.voice_client.pause()
            try:
                await ctx.send("Skipping current song...")
                ctx.voice_client.stop()
            except IOError:
                ctx.voice_client.resume()
                return await ctx.send("The next media file is not ready to be played just yet - please be patient.")
        else:
            await ctx.send("I am not in any voice chat right now")

    @commands.hybrid_command(name= 'fskip', aliases = ['forceskip', 'force_skip'])
    async def force_skip(self, ctx):
        """
        Skips to next song in queue, but forces the skip -- the loop will be ignored.
        """
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]

        if self._is_connected(ctx):
            ctx.voice_client.pause()
            try:
                guild_.loop = NO_LOOP # next song is set to NOT loop - which should be what people want anyway.
                self.play_next(ctx)
            except IOError:
                ctx.voice_client.resume()
                return await ctx.send("The next media file is not ready to be played just yet - please be patient.")
        else:
            await ctx.send("I am not in any voice chat right now")

    @commands.hybrid_command(name="pause")
    async def pause(self, ctx):
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        if self._is_connected(ctx):
            ctx.voice_client.pause()
            await ctx.send("Paused!")
        else:
            await ctx.send("I am not in any voice chat right now")

    @commands.hybrid_command(name='resume')
    async def resume(self, ctx):
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        if self._is_connected(ctx):
            ctx.voice_client.resume()
            await ctx.send("Resumed!")
        else:
            await ctx.send("I am not in any voice chat right now")

    @commands.hybrid_command(name="queue", aliases=["q", "playlist"])
    async def queue_(self, ctx: commands.Context):
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]

        if self._is_connected(ctx):
            cur_playing_embed = discord.Embed(
                color=discord.Color.blue()
            )

            cur_playing_embed.add_field(
                name="Currently playing",
                value=f"**[{guild_.cur_song.title}]({guild_.cur_song.original_url})** ({_time_split(guild_.cur_song.duration)})\n"
            )

            await ctx.send(embed=cur_playing_embed)

            all_additional_embeds_created = False
            all_embeds = []
            cur_index = 0
            if guild_.queue:
                while not all_additional_embeds_created:
                    next_playing_embed = discord.Embed(
                        color=discord.Color.blue()
                    )

                    r_link = ""
                    max_reached = False
                    while not max_reached and cur_index < len(guild_.queue):
                        res_ind = cur_index
                        res = guild_.queue[res_ind]
                        string = f"**{res_ind + 1}. [{res.title}]({res.original_url})** ({_time_split(res.duration)})\n"
                        if len(r_link) <= MAX_MSG_EMBED_SIZE - len(string):
                            r_link += string
                            cur_index += 1
                        else:
                            max_reached = True
                    if cur_index == len(guild_.queue):
                        all_additional_embeds_created = True
                    if r_link != "":
                        next_playing_embed.add_field(
                            name="Next songs",
                            value=r_link,
                            inline=False
                        )
                    all_embeds.append(next_playing_embed)
            for e_ind, embed in enumerate(all_embeds):
                embed.set_footer(text=f"Page {e_ind + 1}/{len(all_embeds)}")
            
            if all_embeds:
                q_view = QueueMenu(all_embeds)
                await ctx.reply(embed = all_embeds[0], view = q_view)
        else:
            await ctx.send("I am not in any voice chat right now")

    @commands.hybrid_command(name='clear')
    async def clear_(self, ctx):
        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        guild_.queue.clear()
        await ctx.send("Queue cleared!")

    @commands.hybrid_command(name='loop')
    async def loop(self, ctx, loop_amount = None):
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")
        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]

        if guild_.loop:
            if loop_amount is not None:
                return await ctx.send(f"Already looping a couple of times - please type {BOT_PREFIX}loop to end loop.")
            guild_.loop = NO_LOOP
            if guild_.loop_count is not None:
                guild_.loop_count = None
            await ctx.send("No longer looping current song.")
        else:
            if loop_amount is not None:
                if not loop_amount.isdigit():
                    return await ctx.send("Please enter a number if you want to loop the current song a number of times.")
                else:
                    guild_.loop_count = {
                        guild_.cur_song : int(loop_amount)
                        }
                    await ctx.send(f"Looping current song for {loop_amount} more times.")
            else:
                await ctx.send("Looping current song.")
            guild_.loop = LOOP
            

    @commands.hybrid_command(name='shuffle')
    async def shuffle(self, ctx):
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]
        if guild_.queue:
            random.shuffle(guild_.queue)
            await ctx.send("Queue is shuffled. To check current queue, please use >3queue, or >3q")
        else:
            await ctx.send("There is nothing to be shuffled.")

    @commands.command(name='set_song_choosing_state', aliases=['set_state'])
    @commands.has_permissions(administrator=True)
    async def set_state(self, ctx):
        """
        Changes from either selecting songs or just pick the first one while searching.
        Requires admin privilege in the server or the bot would just be abused back and forth.
        """
        guild_id = ctx.guild.id
        self._bot_config.set_state(guild_id)
        if self._bot_config.isAutoPick(guild_id):
            await ctx.send("Changed to auto select the first one on search.")
        else:
            await ctx.send("Changed to manually select video from search.")

    @staticmethod
    def peek_vc(ctx):
        """
        Checks to see if the author is in any vc or not.
        """
        voice_state = ctx.author.voice

        if voice_state is None:
            # Exiting if the user is not in a voice channel
            return False

        return True

    @set_state.error
    async def set_state_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            msg = f"You don't have the privilege to set this {ctx.message.author.mention}."
            await ctx.send(msg)

    def _is_connected(self, ctx):
        return discord.utils.get(self._bot.voice_clients, guild=ctx.guild)


async def setup(bot):
    await bot.add_cog(Player(bot))
