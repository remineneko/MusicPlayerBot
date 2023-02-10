from dataclasses import dataclass
from typing import Union, Literal
from abc import ABC, abstractmethod
import discord
import asyncio
from src.player.youtube.search import SearchVideos
from src.player.media_metadata import MediaMetadata
from src.player.youtube.download_media import isExist, SingleDownloader
from src.player.observers import *
from src.data_transfer import *
from src.player.load_media import LoadMedia
from src.cogs.player.utils import run_blocker, _time_split



@dataclass
class Job:
    """
    Defines a job for the bot to do.

    Args:
        job_name (str): The name of the job. Accepts either 'search' or 'access'.
        query (str): The query that the job is handling. 
        query_type (Union[str, int]): The type of query that the job is handling.
        work_type (str): The type of work that is being done, either 'normal', or 'chapter'.
            'chapter' should only be used when Youtube video chapters are specifically wanted; otherwise, use 'normal'.
    """
    job: Literal['search', "access"]  # accepts either "search" or "access"
    query: str
    query_type: Union[str, int]
    work_type: Literal['normal', 'chapter'] = 'normal' # accepts either 'normal' or 'chapter'

    async def act(self, observer, client, ctx, selector_choice):
        if self.job == 'search':
            return await SearchAction(self.query, self.query_type, self.work_type, observer, selector_choice, client, ctx).act()
        else:
            return await AccessAction(self.query, self.query_type, self.work_type, observer, selector_choice, client, ctx).act()


class BaseAction(ABC):
    def __init__(self, query, query_type, work_type, observer, selector_choice, client, ctx):
        self._query = query
        self._query_type = query_type
        self._work_type = work_type
        self._selector_choice = selector_choice
        self._observer = observer
        self._client = client
        self._ctx = ctx
 
    @abstractmethod
    async def act(self):
        raise NotImplementedError("Classes that inherit BaseAction must implement act().")


class SearchAction(BaseAction):
    async def act(self):
        def check_valid_input(m):
            return m.author == self._ctx.author and m.channel == self._ctx.channel

        if not self._selector_choice:
            sv_obj = SearchVideos()
            sv_obj.subscribe(self._observer)
            result: List[MediaMetadata] = await run_blocker(self._client, sv_obj.search, self._query)
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
            await self._ctx.send(embed=results_embed)

            try:
                q_msg = await self._client.wait_for('message', check=check_valid_input, timeout=30)
            except asyncio.TimeoutError:
                await self._ctx.send(f"Timeout! Search session for query {self._query} terminated.")
                sv_obj.unsubscribe(self._observer) # earlier unsub because we are returning early.
                return None
            sv_obj.unsubscribe(self._observer)
            if q_msg.content.isdigit() and 1 <= int(q_msg.content) <= 5:
                data = [result[int(q_msg.content) - 1]]
            else:
                await self._ctx.send("Illegal input. Terminated search session.")
                return None
        else:
            sv_obj = SearchVideos(limit=1)
            sv_obj.subscribe(self._observer)
            data: List[MediaMetadata] = await run_blocker(self._client, sv_obj.search, self._query)
            sv_obj.unsubscribe(self._observer)

        return data

class AccessAction(BaseAction):
    async def act(self):
        load_sesh = LoadMedia(self._query, self._query_type, work_type = self._work_type)
        load_sesh.subscribe(self._observer)
        try:
            data = await run_blocker(self._client, load_sesh.load_info)
        except ValueError:
            await self._ctx.send("Cannot load playlist on play chapter requests.")
            return None
        load_sesh.unsubscribe(self._observer)

        return data
    
