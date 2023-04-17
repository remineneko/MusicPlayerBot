from .guild_session import GuildSession
from .utils import _time_split, run_blocker, YT_DLP_SESH, NO_LOOP, LOOP
from .job import Job
from .queue_menu import QueueMenu
from .timestamp_parser import parse_timestamp, UnableToParseError, parse_to_timestamp

from discord.ext import commands, tasks
from collections import defaultdict
import discord
import asyncio
from copy import deepcopy
from typing import List, Dict
import logging
import os
import re
import random

from src.data_transfer import Vault
from constants import MUSIC_STORAGE, MAX_MSG_EMBED_SIZE, CONFIG_FILE_LOC, BOT_PREFIX
from src.configs import Config
from src.logger import BotHandler
from src.player.media_metadata import MediaMetadata
from src.player.youtube.download_media import isExist, SingleDownloader
from src.player.link_identifier import LinkIdentifier


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
        """
        Initialize the bot.

        Args:
            bot (discord.ext.commands.Bot): The Discord Bot client.
        """
        self._bot = bot
        self._players: Dict[int, discord.FFmpegPCMAudio] = {}
        self._vault = Vault()
        self._bot_config = Config(CONFIG_FILE_LOC)
        self._guild_sessions: Dict[int, GuildSession] = defaultdict(lambda: GuildSession())

        # Stores information on which guild the bot is staying inside VC 
        self._active_guild_session_cache: Dict[int, GuildSession] = {}                                          

    def get_players(self, ctx: commands.Context, job: int =_NEW_PLAYER):
        """
        Gets the audio player for a voice channel in a guild.

        Args:
            ctx (commands.Context): _description_
            job (int, optional): _description_. Defaults to _NEW_PLAYER.

        Returns:
            discord.AudioSource: an audio source for the bot to play in the voice channel.
        """
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

            await self.pre_play_process(ctx, data)

    @commands.hybrid_command()
    async def playnextchapter(self, ctx: commands.Context):
        """
        Plays the next chapter in a video that has chapters.
        Requires the users to have used playchapter command prior to this command.

        Args:
            ctx (commands.Context): The context of the command
        """
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
            song_copy = deepcopy(song) # so that other data wont be mutated.
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

        await self.pre_play_process(ctx, data)

    @commands.hybrid_command()
    async def playfromchapter(self, ctx: commands.Context, chapter_index: str, *, query):
        """ Plays a video from a chapter.

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
            return await ctx.send("playfromchapter only supports a single video.")
        elif data:
            song: MediaMetadata = data[0]
            if not song.chapters:
                return await ctx.send("The song chosen does not have any chapters.")
            else:
                try:
                    song_copy = deepcopy(song)
                    guild_.selected_chapter[song_copy] = index_chapter

                    self.sanitize_(song.chapters)

                    ss_start, ss_title, ss_end = list(song.chapters[index_chapter].values())
                    
                    ss_start = int(ss_start)
                    ss_end = int(ss_end)
                    
                    self._FFMPEG_STREAM_PARTIAL_OPTIONS = {
                            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_time} -t {fast_forward}',
                            'options': '-vn'
                        } 
                    self._FFMPEG_STREAM_PARTIAL_OPTIONS['before_options'] = self._FFMPEG_STREAM_PARTIAL_OPTIONS['before_options'].format(start_time= ss_start, fast_forward= song.duration - ss_start)
                    
                    # caching options to allow the bot to play
                    guild_.cached_options.update({data[0]: self._FFMPEG_STREAM_PARTIAL_OPTIONS})
                except IndexError:
                    return await ctx.send("The chapter index is higher than the amount the video has. Please check your input")

            await self.pre_play_process(ctx, data)

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

        await self.process_query(ctx, query)

        while self._vault.isEmpty(guild_id):
            await asyncio.sleep(1)

        # both runs at the same time from here.
        data = self._vault.get_data(guild_id)
        if data:
            await self.pre_play_process(ctx, data)
        else:
            await ctx.send("No audio has been loaded.")

    @commands.hybrid_command()
    async def seek(self, ctx: commands.Context, timestamp: str):
        """
        Seeks to a certain point in the video.
        The user can either put in the timestamp in seconds (360 to represent 6 minute mark for example), 
            or ":" format - "6:30" to represent the timestamp to be 6 minutes and 30 seconds.
        
        For the ":" format, one can specify the hour and day using similar notations - "1:00:00" for 1 hour, 
            and "1:00:00:00" for 1 day.
        Args:
            ctx (commands.Context): The context of the command.
            timestamp (str): The timestamp of the video to seek to. 

        """
        guild_id = ctx.guild.id

        guild_ = self._guild_sessions[guild_id]

        if not guild_.cur_song:
            return await ctx.send("A song must be playing to use the seek command.")
        
        # parse the timestamp here
        # there are two timestamps format available - the number format and the semi-colon format
        try:
            start = parse_timestamp(timestamp)
        except UnableToParseError as e:
            return await ctx.send(e)
        
        # and then reparse for that printing.
        to_send = parse_to_timestamp(start)

        song = guild_.cur_song

        if start > song.duration:
            return await ctx.send("The seek point is further than the duration of the video.")
        
        if song in guild_.song_title_suffix:
            original_song = song
            song = deepcopy(song)
            song.title = song.title.removesuffix(guild_.song_title_suffix[original_song])

            # with seek being used, the previously song in chapter must be removed. 
            # after all, the current song is no longer provoked by playchapter right?

            del guild_.song_title_suffix[original_song]

        self._FFMPEG_STREAM_PARTIAL_OPTIONS = {
                            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {start_time} -t {fast_forward}',
                            'options': '-vn'
                        } 
        self._FFMPEG_STREAM_PARTIAL_OPTIONS['before_options'] = self._FFMPEG_STREAM_PARTIAL_OPTIONS['before_options'].format(start_time= start, fast_forward= song.duration - start)

        # to play this later on
        guild_.cached_options.update({song: self._FFMPEG_STREAM_PARTIAL_OPTIONS})
        await ctx.send(f"Playing from {to_send}")
        await self.pre_play_process(ctx, [song], play_immediately=True)

    async def pre_play_process(self, ctx, data, play_immediately=False):
        """
        Processes the data before playing the songs in the voice channel.

        Args:
            ctx (commands.Context): Context of the command
            data (List[MediaMetadata]): The data to be processed

        """
        guild_ = self._guild_sessions[ctx.guild.id]
        
        queue_total_play_time = sum([int(i.duration) for i in guild_.queue]) if guild_.queue else 0
        for item_ind, item in enumerate(data):
            try:
                if item.duration >= self._MAX_AUDIO_ALLOWED_TIME: # for now, for safety, that is removed
                    await ctx.send(f"Video {item.title} is too long! Current max length allowed to be played for individual video is 6 hours! Removed from queue.")
                    data.remove(item)
                elif queue_total_play_time + item.duration >= self._MAX_AUDIO_ALLOWED_TIME:
                    guild_.requires_download.extend(data[item_ind:])
                    break
                else:
                    queue_total_play_time += item.duration
            except TypeError: # occurs when this is a stream
                item.title = self.filter_name(item.title)

        data_l = len(data)
        if data_l == 1:
            msg = f"Added {data[0].title} to the queue."
        elif not data_l:
            msg = "No songs are added."
        else:
            msg = f"Added {data_l} songs to the queue."

        guild_.queue.extend(data)
        if not play_immediately:
            await ctx.send(msg)
                
        try:
            voiceChannel = discord.utils.get(
                ctx.message.guild.voice_channels,
                name=ctx.author.guild.get_member(ctx.author.id).voice.channel.name
                        )
        except AttributeError:
            return await ctx.send('You need to be in a voice channel to use this command')

        try:
            if guild_.requires_download:
                self.bg_download_check.start(ctx)
        except RuntimeError:
            pass
        
        if not self._is_connected(ctx) and guild_.queue:
            await voiceChannel.connect()

        voice = ctx.voice_client
        await self.play_song(ctx, voice, overwrite_player=play_immediately)
        

    def filter_name(self, title):
        expr = re.compile(' \d{4}-\d{2}-\d{2} \d{2}:\d{2}')
        if expr.search(title):
            return re.sub(expr, "", title)

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
        """
        Processes the audio clips that requires downloading in the background.

        Args:
            ctx (_type_): _description_
        """
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

    async def play_song(self, ctx: commands.Context, 
                        voice,refresh = False,
                        overwrite_player = False):
        """
        Plays the first song in the queue.

        Args:
            ctx (commands.Context): The context of the command.
            voice (discord.VoiceClient): The voice client that the bot is connected to.
            refresh (bool, optional): Whether the bot is refreshing the player or not. Defaults to False.
        """
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
            if not overwrite_player:
                await ctx.send('**Now playing:** {}'.format(guild_.cur_song.title), delete_after=20)
        elif overwrite_player:
            await self.skip_(ctx, verbose=False)
        else:
            await asyncio.sleep(1)
    
    def retry_play(self, ctx, voice, e):
        """
        Retries loading the player

        Args:
            ctx (commands.Context): The context of the command.
            voice (discord.VoiceClient): The voice client that the bot is connected to.
            e (Exception): The error that triggered when the bot failed to load the player.
        """
        guild_ = self._guild_sessions[ctx.guild.id]
        if guild_.retry_count < self._MAX_RETRY_COUNT:
            guild_.retry_count += 1
            guild_.queue.insert(0, guild_.cur_song)
            guild_.cur_song = None
            asyncio.run_coroutine_threadsafe(self.play_song(ctx, voice, True), ctx.bot.loop)
        else:
            print("Player error: %s", e)

    def play_next(self, ctx: commands.Context):
        """
        Supporting function to play the next item in queue
        """
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
        """
        Debugs a section of the code. Only the owner can use this.
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
        """
        Stops the player.
        """
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
    async def skip_(self, ctx, verbose=True):
        """
        Skips to next song in queue
        """
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        if self._is_connected(ctx):
            ctx.voice_client.pause()
            try:
                if verbose:
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
        """
        Pauses the player
        """
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
        """
        Resumes the player
        """
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
        """
        Shows the current queue that is being played in the voice channel.
        """
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
        """
        Clears the queue
        """
        guild_id = ctx.guild.id
        guild_ = self._guild_sessions[guild_id]
        can_join_vc = self.peek_vc(ctx)
        if not can_join_vc:
            return await ctx.send("You need to be in a voice channel to use this command.")

        guild_.queue.clear()
        await ctx.send("Queue cleared!")

    @commands.hybrid_command(name='loop')
    async def loop(self, ctx, loop_amount = None):
        """
        Loops the current song. Users can specify the number of times the song can be looped.
        """
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
        """
        Shuffles the playlist
        """
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
        """
        Checks whether the bot is connected to the voice client or not.
        """
        return discord.utils.get(self._bot.voice_clients, guild=ctx.guild)


async def setup(bot):
    await bot.add_cog(Player(bot))
