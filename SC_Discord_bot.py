import asyncio
import discord
import yt_dlp
from discord.ext import commands
from collections import deque

yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = deque([]) 

    async def play_next(self, interaction: discord.Interaction):
        """Plays the next song in the queue."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if self.queue:
                next_url = self.queue.popleft()
                player = await YTDLSource.from_url(next_url, loop=self.bot.loop, stream=True)

                interaction.guild.voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.on_track_end(interaction, e)))
                
                await interaction.followup.send(f"Now playing: {player.title}")
            else:
                await interaction.followup.send("Queue is empty!")
        except Exception as e:
            await interaction.followup.send(f"Failed to play next due to exception: {e}")

    async def on_track_end(self, interaction: discord.Interaction, error):
        """Called when a track ends. Starts the next song."""
        if error:
            print(f"Player error: {error}")
        await self.play_next(interaction)

    @discord.app_commands.command(name="join", description="Join a voice channel")
    async def join(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        """Joins a voice channel"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if interaction.guild.voice_client is not None:
                return await interaction.guild.voice_client.move_to(channel)
            await channel.connect()
            
            await interaction.followup.send(f"Joined {channel.name}.")
        except Exception as e:
                await interaction.followup.send(f"Failed to join due to exception: {e}")

    @discord.app_commands.command(name="show_queue", description="Show the current queue")
    async def show_queue(self, interaction: discord.Interaction):
        """Shows the current queue."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        if self.queue:
            queue_list = '\n'.join(self.queue)
            
            await interaction.followup.send(f"Current queue:\n{queue_list}")
        else:
            
            await interaction.followup.send("The queue is empty.")

    @discord.app_commands.command(name="ping", description="does a ping")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Ping!")

    @discord.app_commands.command(name="play", description="Add a song to the queue")
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if interaction.guild.voice_client is None:
                if interaction.user.voice and interaction.user.voice.channel:
                    await interaction.user.voice.channel.connect()
                else:
                    return await interaction.followup.send("You must be in a voice channel to use this command.")
            """Adds a song to the queue and plays if idle."""
            if interaction.guild.voice_client is None and not interaction.user.voice:
                return await interaction.followup.send("You must be connected to a voice channel.")

            self.queue.append(url)  
            

            if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
                print(f"now playing")
                await self.play_next(interaction)  

            queue_list = '\n'.join(self.queue)
            await interaction.followup.send(f"Queued: {url}")
            print(f"Queue: {queue_list}")
        except Exception as e:
            await interaction.followup.send(f"Failed to play due to exception: {e}")

    @discord.app_commands.command(name="volume", description="Change the player's volume")
    async def volume(self, interaction: discord.Interaction, volume: int):
        """Changes the player's volume"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        if interaction.guild.voice_client is None:
            
            return await interaction.followup.send("Not connected to a voice channel.")

        interaction.guild.voice_client.source.volume = volume / 100
        
        await interaction.followup.send(f"Changed volume to {volume}%")

    @discord.app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        """Stops playback and clears the queue."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        self.queue.clear()
        if interaction.guild.voice_client:
            
            await interaction.guild.voice_client.disconnect()
        
        await interaction.followup.send("Playback stopped and queue cleared.")


intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("?"),
    description='Relatively simple music bot example',
    intents=intents,
)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command:
        await bot.tree.sync()  

async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start('BOTTOKEN')  # Replace with your bot token

asyncio.run(main())