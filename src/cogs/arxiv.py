from discord.ext import commands, tasks
import discord

from arxiv import Client, Search, SortCriterion, Result
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple


class arXivGuildSession:
    def __init__(self):
        self.client: Client = Client()
        self.prev_subs_search_res: List[Result] = list()
        self.subscribe_list: Dict[int, List[Dict[str, Any]]] = defaultdict(list)


class arXiv(commands.Cog):
    def __init__(
        self, 
        bot: discord.ext.commands.Bot
    ):
        """
        Initialize the bot.

        Args:
            bot (discord.ext.commands.Bot): The Discord Bot client.
        """
        self._bot = bot
        self._guild_sessions: Dict[int, arXivGuildSession] = defaultdict(lambda: arXivGuildSession())

    def _find_guild_sesh(self, ctx: commands.Context):
        return self._guild_sessions[ctx.guild.id]

    @commands.hybrid_command(name='subscribe_paper')
    async def subscribe_paper(
        self,
        ctx: commands.Context,
        *,
        query: str
    ):
        sesh = self._find_guild_sesh(ctx)
        task = tasks.loop(hours=1)(self._subscribe)
        sesh.subscribe_list[ctx.author.id].append({
            query: task
        })
        print(sesh.subscribe_list)
        task.start(ctx, query)
        await ctx.send("Subscribed! The bot will find new papers every hour under the provided query.")
    
    async def _subscribe(self, ctx: commands.Context, query: str):
        sesh = self._find_guild_sesh(ctx)
        searcher = Search(
            query=query,
            max_results=100, # theres no way there will be more than 100 papers PER HOUR if anyone knows what they are looking for...
            sort_by=SortCriterion.SubmittedDate
        )

        results = list(sesh.client.results(searcher))

        print(f"Running the results for the run of {datetime.now()}.")
        time_now = datetime.now(tz=timezone.utc)
        time_before = time_now - timedelta(hours=2)

        if len(sesh.prev_subs_search_res) != 0:
            results = [r for r in results if r not in sesh.prev_subs_search_res]

        # filtering results
        results = [r for r in results if r.published > time_before and r.published < time_now]
        if len(results) > 0:
            for result in results:
                embed = self._build_embed(result)
                await ctx.send(embed=embed)
            
            sesh.prev_subs_search_res.clear()
            sesh.prev_subs_search_res = deepcopy(results)

    @commands.hybrid_command(name='unsubscribe_paper')
    async def unsubscribe_paper(self, ctx: commands.Context, *, query: str):
        sub_list = self._find_guild_sesh(ctx).subscribe_list[ctx.author.id]
        finding_query = [(index, i) for index, i in enumerate(sub_list) if list(i.keys())[0] == query]
        print(finding_query)
        if len(finding_query) == 0:
            return await ctx.send("No task found with provided query.")
        else:
            associated_task = finding_query[0][1][query]
            await ctx.send(f"No longer subscribed to finding new papers using the query {query}.")
            associated_task.stop()
            del sub_list[finding_query[0][0]]
            

    @commands.hybrid_command(name='unsubscribe_all')
    async def unsubscribe_all(self, ctx: commands.Context):
        sub_list = self._find_guild_sesh(ctx).subscribe_list[ctx.author.id]
        all_tasks = [list(i.values())[0] for i in sub_list]
        if len(all_tasks) == 0:
            await ctx.send("No task found.")
        else:
            await ctx.send("No longer subscribed to finding new papers.")
            for task in all_tasks:
                task.stop()

            sub_list.clear()
            

    @commands.hybrid_command()
    async def findpaper(self, ctx: commands.Context, *, query: str):
        searcher = Search(
            query=query,
            max_results=5, 
            sort_by=SortCriterion.SubmittedDate
        )

        results = list(self._find_guild_sesh(ctx).client.results(searcher))

        if len(results) > 0:
            for result in results:
                embed = self._build_embed(result)
                await ctx.send(embed=embed)
        else:
            await ctx.send("No results have been found.")

    def _build_embed(self, result: Result):
        result_embed = discord.Embed(
            title=result.title,
            description=", ".join([a.name for a in result.authors]),
            color=discord.Color.dark_red(),
            url=result.pdf_url
        )

        result_embed.set_thumbnail(url='https://public.boxcloud.com/api/2.0/internal_files/804104772302/versions/860288648702/representations/png_paged_2048x2048/content/1.png?access_token=1!AEgx010olcDzcZEirc7owzQmEvWa84G6rA90m8ORJjnd0eqKllWt5-ymHnXR-qRhlHZnIT4Xj5oWfq2tWF9jrE2Xc08pU-RincsPsT3e-zXnBI7V-MJJzJVM3i-L5nB-QM2CT9aTTbPmv0orRSOFgqgLkzgzxrSamLFNYyq3vsewFD633tYGcBK0Q-WB47UuYDXDZsYRNwsga7gkDgNdSqSD7z2-nyPPerBH0jELUVRfzEF978DfG59CyM1c2ejIXik_gFXko4o9r_O50gMCo0OiaV5I3irRUnbOFRVrEhFGyr50YZX3x2zjbCl4cIabmn5DIsh6uoKSN8MX-zI6KzlBbLrrnZp724atUaSGwpGeKyutE2q3WhYdeBtibBvQ_9jSvNefbpRTwQkN1fGG-Jtnc28_av3QHtjXcblwTMh1miaqhLqZOSCvoCeZDX4kh8-hixD3AZhxL8nLgvpF5_fSgTXo4arzZvnpkkt69A-mwMR6x9Xgt6HxC5O_dziu3WeLzcLgFlISOWy3OuEuykh5ndJvvLXjet0_6XBXCNZtFqqQT8sAalxTJ-6_szxaYUgC40ntMqLhi_m5qUabNgWYGhlHHzOhkfmqfQ..&shared_link=https%3A%2F%2Fcornell.app.box.com%2Fv%2Farxiv-logomark-small-png&box_client_name=box-content-preview&box_client_version=2.108.0')

        abs_splitted = result.summary.split()
        end_abs = []

        for abs_part in abs_splitted:
            if sum([len(s) for s in end_abs]) + len(abs_part) < 300:
                end_abs.append(abs_part)

            else:
                break

        abstract = f"{' '.join(end_abs)}... [More]({result.pdf_url.replace('pdf', 'abs')})"
  
        result_embed.add_field(
            name='Abstract',
            value=abstract
        )

        result_embed.set_footer(text='Thank you to arXiv for use of its open access interoperability.')

        return result_embed
        

async def setup(bot):
    await bot.add_cog(arXiv(bot))