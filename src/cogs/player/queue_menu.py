import discord


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
