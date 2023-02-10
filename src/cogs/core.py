import discord
from discord.ext import commands
from constants import BOT_PREFIX


class Core(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self._bot = bot

    @commands.hybrid_command(name = "help", aliases = ['h'])
    async def help(self, ctx):
        """A general help command so users know all available commands.
        """
        embed = discord.Embed(title = "Help!",
                              description= f"Command prefix: {BOT_PREFIX}. Slash commands are also supported.",
                              color = discord.Color.blue())
            
        embed.add_field(
            name = f"{BOT_PREFIX}play <url/query>",
            value = "Plays the audio from the given url, or play a song chosen/auto-picked from the query.",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}playchapter <index of chapter> <url/query>",
            value = "Plays the audio in a specific chapter from the given url. The index counting starts from 1.",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}playnextchapter",
            value = "Plays the next chapter in the same video. Requires the video to have chapters, else this won't have any meaning to work.",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}pause",
            value = "Pauses the current media",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}resume",
            value = "Resumes the current media",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}queue/q/playlist",
            value = "Checks the current queue",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}skip",
            value = "Skips the current song. The current song will be repeated if loop is set for the song.",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}fskip/forceskip/force_skip",
            value = "Skips the current song regardless of loop status. Next song will not be looped using this command.",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}loop <optional: number of times to loop>",
            value = "Loops the curent media. If a number of times is specified, the song will be looped for that number of times.",
            inline = False
        )

        embed.add_field(
            name=f"{BOT_PREFIX}shuffle",
            value="Shuffles the queue",
            inline=False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}clear",
            value = "Clears the current queue",
            inline = False
        )

        embed.add_field(
            name = f"{BOT_PREFIX}set_state",
            value = "Sets either the bot to select the first song found immediately or allow the user to select on input being a query. Requires admin.",
            inline = False
        )

        await ctx.send(embed = embed)


async def setup(bot):
    await bot.add_cog(Core(bot))
