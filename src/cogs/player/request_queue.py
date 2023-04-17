from discord.ext import commands
from src.player.observers import *
from typing import Union, List
from src.cogs.player.job import Job
import inspect
import asyncio
from src.data_transfer import *


class RequestQueue(DownloaderObservers):
    def __init__(self, observer = DownloaderObservable()):
        """ Initialize a new request queue for the player

        Args:
            observer (DownloaderObservable, optional): An observable object for the request queue.
        """
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
            
            data = await self.priority.act(
                observer = self,
                client = client,
                ctx = ctx,
                selector_choice = selector_choice
            )
            self.priority = None

            if not data:
                return
            
            new_sender.send(data)
        elif self.priority is None and self.on_hold:
            self.priority = self.on_hold.pop(0)
            await self.process_requests(client, ctx, vault, selector_choice)
    