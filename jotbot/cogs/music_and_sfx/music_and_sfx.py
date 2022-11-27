import discord
import youtube_dl
import random
import asyncio
import functools
import math
import itertools

from typing import Union
from async_timeout import timeout
from discord.ext import commands, tasks
from ..server_only_cog import ServerOnlyCog

yes_reaction = '🟩'
no_reaction = '🟥'
std_cooldown = 5
queue_check_cooldown = 20
now_cooldown = 10

# Since I only have like 30 hours of python coding experience in my life,
# I took most of the supporting classes from the link below.
# They are very intuitive ways of writing this stuff and I'd rather not reinvent the wheel
# https://gist.github.com/vbe0201/ade9b80f2d3b64643d854938d40a0a2d

class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
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

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 1.0):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** by **{0.uploader}**'.format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise Exception('Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise Exception('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise Exception('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise Exception('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{:02d}:'.format(days))
        if hours > 0:
            duration.append('{:02d}:'.format(hours))
        if minutes > 0:
            duration.append('{:02d}:'.format(minutes))
        if seconds > 0:
            duration.append('{:02d}:'.format(seconds))

        return ', '.join(duration)

class Song:
    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        embed = (discord.Embed(title='Now playing',
                               description='```css\n{0.source.title}\n```'.format(self),
                               color=discord.Color.blurple())
                 .add_field(name='Duration', value=self.source.duration)
                 .add_field(name='Requested by', value=self.requester.mention)
                 .add_field(name='Uploader', value='[{0.source.uploader}]({0.source.uploader_url})'.format(self))
                 .add_field(name='URL', value='[Click]({0.source.url})'.format(self))
                 .set_thumbnail(url=self.source.thumbnail))

        return embed

class SongQueue(asyncio.Queue):

    def __init__(self):
        super().__init__(maxsize=150)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]

# This is just a container to help me organize Queue logic.
# Could maybe abstract this better in the future but for now 
# it's just here to avoid doing some dictionary with list values bullshit
class MultiPageEmbed():

    def __init__(self, message: discord.Message, time_remaining=20, current_page=1):
        self.message = message
        self.time_remaining = time_remaining
        self.current_page = current_page

class VoteProposal():

    def __init__(self, message: discord.Message):
        self.vote_message = message
        self.total_votes = 0

class VoiceState():
    
    def __init__(self, creator: commands.Cog, bot: commands.Bot, context: commands.Context):
        self.bot = bot
        self.creator = creator
        self._context = context
        self._musicQueue = SongQueue()

        self.next = asyncio.Event()
        self.current = None
        self.voice = None
        self.currentChannel = None

        self.loop = False
        self.volume = 0.5       
        self.skip_proposal = None

        self.cooldowns = dict() # [cooldown_name (str), seconds_until_usable]
        self.cooldowns['p'] = 0
        self.cooldowns['r'] = 0
        self.cooldowns['q'] = 0
        self.cooldowns['v'] = 0
        self.cooldowns['n'] = 0

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()
        if self.skip_proposal:
            try:
                del self.creator.listening_skip_msgs[self.skip_proposal.vote_message.id]
            except Exception as e:
                return


    @property
    def context(self) -> commands.Context:
        return self._context

    @property
    def musicQueue(self) -> asyncio.Queue:
        return self._musicQueue

    def is_playing(self) -> bool:
        return self.voice and self.current

    def shuffle(self):
        self.musicQueue.suffle()

    def clear_queue(self) -> bool:
        if self.musicQueue.empty():
            return False
            
        for _ in range(self._musicQueue.qsize()):
            self._musicQueue.get_nowait()
            self._musicQueue.task_done()

    def remove_queue_element(self, remVal: int) -> bool:
        if self._musicQueue.empty():
            return False

        temp = SongQueue()
        for ind in range(self._musicQueue.qsize()):
            popVal = self._musicQueue.get_nowait()
            if ind != remVal:
                temp.put_nowait(popVal)
        
        self._musicQueue = temp

    async def audio_player_task(self):
        while True:
            self.next.clear()

            if not self.loop:
                # Try to get the next song within 3 minutes.
                # If no song will be added to the queue in time,
                # the player will disconnect due to performance
                # reasons.
                try:
                    async with timeout(180):  # 3 minutes
                        self.current = await self._musicQueue.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return

            self.current.source.volume = self.volume
            self.voice.play(self.current.source, after=self.play_next_song)
            await self.current.source.channel.send(embed=self.current.create_embed())

            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise Exception(str(error))

        self.next.set()

    def skip(self):
        if self.skip_proposal:
            try:
                del self.creator.listening_skip_msgs[self.skip_proposal.vote_message.id]
            except Exception as e:
                return

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.clear_queue()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None
        
    

class MusicSFXCog(ServerOnlyCog, name = "music_and_sfx"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = dict() # [guild_id (int), voice_state]
        self.listening_skip_msgs = dict() # [message_id (int), voice_state]
        self.listening_queue_msgs = dict() # [user_id (int), MultiPageEmbed] 

        
    def get_voice_state(self, ctx: commands.Context) -> VoiceState:
        return self.voice_states[ctx.guild.id]

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def generate_queue_embed(self, requestAuthor: discord.User, state: VoiceState, page: int):

        items_per_page = 10
        pages = math.ceil(len(state.musicQueue) / items_per_page)

        page = max(min(pages, page), 1)

        start = (page - 1) * items_per_page
        end = start + items_per_page
        queue = ''
        for i, song in enumerate(state.musicQueue[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(title='Queue view for {}'.format(requestAuthor.display_name),description='**{} tracks:**\n\n{}'.format(len(state.musicQueue), queue))
                 .set_footer(text='Viewing page {}/{}'.format(page, pages)))
        return embed

    async def edit_and_update_queue_message(self, author: discord.User, state: VoiceState, queueMsg: MultiPageEmbed, newPage: int):
        newEmb = self.generate_queue_embed(author, state, newPage)
        newMsg = await queueMsg.message.edit(embed=newEmb)
        newMsg.add_reaction('⏪')
        newMsg.add_reaction('◀')
        newMsg.add_reaction('▶')
        newMsg.add_reaction('⏩')
        queueMsg.message = newMsg
        queueMsg.time_remaining = queue_check_cooldown

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('An error occurred: {}'.format(str(error)))

    async def search(self, ctx: commands.Context):
        pass


    @tasks.loop(seconds=1)
    async def handle_cooldowns(self):
        for id, state in self.voice_states:
            for cmdVal in state.cooldowns.keys():
                state.cooldowns[cmdVal] -= 1

        for id in self.listening_queue_msgs.keys():
            listener = self.listening_queue_msgs[id]
            listener.time_remaining -= 1
            if listener.time_remaining <= 0:
                await listener.message.delete()
                del self.listening_queue_msgs[id]

    @commands.command(aliases = ['j'])
    async def join(self, ctx: commands.Context):
        if not self.get_voice_state(ctx):
            self.voice_states[ctx.guild.id] = VoiceState(bot = self.bot, context=ctx)
        elif self.get_voice_state(ctx).context.voice_client.channel == ctx.author.voice.channel:
            raise commands.CommandError('Bot is already in this voice channel')

        dest = ctx.author.voice.channel
        state = self.get_voice_state(ctx)
        if state.voice:
            await state.voice.move_to(dest)
            if state.voice.context.voice_client.channel != ctx.author.voice.channel:
                state.context = ctx
        else:
            state.voice = await dest.connect()

        state.currentChannel = ctx.author.voice.channel

    @commands.command(aliases = ['p'])
    async def play(self, ctx: commands.Context, *, search: str):
        if not self.get_voice_state(ctx):
            await self.join(ctx)

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except Exception as e:
                await ctx.send('An error occured processing this request: {}'.format(str(e)))
            else:
                song = Song(source)

                await self.get_voice_state(ctx).musicQueue.put(song)
                await ctx.send('{} added to queue.'.format(str(source)))

    @commands.command(aliases=['s'])
    async def skip(self, ctx: commands.Context):
        state = self.get_voice_state(ctx)
        if state.skip_proposal:
            embed = discord.Embed()
            embed.color = discord.Color.red()
            embed.title = "{} is already proposed to skip!".format(str(state.current.title))
            embed.description = "[Jump to message and vote here]({})".format(str(state.skip_proposal.vote_message.url))
            await ctx.send(embed=embed)
        else:
            users = len(state.currentChannel.members) - 1
            embed = discord.Embed()
            embed.title = '**Skip {}?**'.format(str(state.current.title))
            embed.descripton = '**{0} out of {1}** users in the channel must react with 🟩 to skip.'.format(int(users / 2), users)
            msg = await ctx.send(embed=embed)
            state.skip_proposal = VoteProposal(message=msg)
            await msg.add_reaction('🟩')
            self.listening_skip_msgs[msg.id] = state

    @commands.command(aliases=['pau'])
    async def pause(self, ctx: commands.Context):

        pass

    @commands.command(aliases=['res'])
    async def resume(self, ctx: commands.Context):
        pass

    @commands.command(aliases=['v'])
    async def volume(self, ctx: commands.Context, *, val: int):
        state = self.get_voice_state(ctx)
        if not state.cooldowns['v'] > 0:
            return await ctx.send('Volume command is on cooldown. Please wait {} seconds'.format(str(self.cooldowns['v'])))
        else:
            val = max(min(300, val), 0)
            await ctx.send('Setting volume to **{}**'.format(str(val)))
            state.volume = val / 100
            state.cooldowns['v'] = std_cooldown
        pass 

    @commands.command(aliases=['q'])
    async def queue(self, ctx: commands.Context, *, pg: int):
        async def send_and_react(state):
            emb = self.generate_queue_embed(ctx.author, state, pg)
            msg = await ctx.send(embed=emb)
            msg.add_reaction('⏪')
            msg.add_reaction('◀')
            msg.add_reaction('▶')
            msg.add_reaction('⏩')
            return msg

        state = self.get_voice_state(ctx)
        if state.cooldowns['q'] > 0:
            return await ctx.send('Queue command used too quickly. Please wait {} seconds.'.format(str(state.cooldowns['q'])))
        if len(state.musicQueue) == 0:
            return await ctx.send('Queue is empty!')

        listener = self.listening_queue_msgs.get(ctx.author.id)
        if listener:
            await listener.message.delete()
            msg = await send_and_react(state)
            listener.message = msg
            listener.time_remaining = queue_check_cooldown
            state.cooldowns['q'] = std_cooldown
            pass
        else:
            msg = await send_and_react(state)
            listener = MultiPageEmbed(msg, page=pg)
            listener.message = msg
            state.cooldowns['q'] = std_cooldown
            self.listening_queue_msgs[ctx.author.id] = listener
        pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        if user == self.bot.user or not user.voice:
            return
        
        # Check for skip (if valid); update skip count and act accordingly
        state = self.listening_skip_msgs.get(reaction.message.id)
        if state and state.skip_proposal:
            if not user.voice.channel == state.currentChannel:
                return
            
            # Reaction is valid; add to vote total, and skip song if total >= required / 2
            state.skip_proposal.total_votes += 1
            if state.skip_proposal.total_votes >= int((len(state.currentChannel.members) - 1) / 2):
                state.skip()

        # Check for queue reaction.
        auth = reaction.message.author
        qListener = self.listening_queue_msgs[auth.id]
        state = self.voice_states.get(auth.guild.id)
        if qListener:
            if reaction.emoji == '⏪':
                self.edit_and_update_queue_message(auth, state, qListener, 1)
                pass
            elif reaction.emoji == '◀':
                self.edit_and_update_queue_message(auth, state, qListener, qListener.pg - 1)
                pass
            elif reaction.emoji == '▶':
                self.edit_and_update_queue_message(auth, state, qListener, qListener.pg + 1)
                pass
            elif reaction.emoji == '⏩':
                self.edit_and_update_queue_message(auth, state, qListener, math.ceil(len(state.musicQueue) / 10))
                pass
            pass

        pass
    
    @commands.command(aliases=['sh'])
    async def shuffle(self, ctx: commands.Context):
        self.get_voice_state(ctx).shuffle()
        pass

    @commands.command(aliases=['l'])
    async def loop(self, ctx: commands.Context):
        state = self.get_voice_state(ctx)
        if not state.is_playing():
            return await ctx.send('Cannot loop, nothing is currently being played.')

        state.loop = not state.loop
        if state.loop:
            await ctx.send('{} is now being looped.'.format(str(state.current.source.title)))
        else:
            await ctx.send('Loop disabled.')

    @commands.command(aliases=['c', 'clear'])
    async def clearQueue(self, ctx: commands.Context):
        state = self.get_voice_state(ctx)

        if not state.musicQueue.empty():
            state.clear_queue()
            await ctx.send('Queue cleared!')
        else:
            await ctx.send('Queue is already empty.')
        pass

    @commands.command(aliases=['r'])
    async def remove(self, ctx: commands.Context, *, rem: int):
        state = self.get_voice_state(ctx)

        if state.musicQueue.empty():
            raise commands.CommandError('Cannot remove from empty queue.')
        elif rem <= 0 or state.musicQueue.qsize() >  rem - 1:
            raise commands.CommandError('Invalid queue index.')

        state.remove_queue_element(rem)

    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx: commands.Context):
        if ctx.author.voice.channel != self.get_voice_state(ctx).context.voice_client.channel:
            raise commands.CommandError('Must be in the same voice channel is the bot to disconnect it.')

        await self.get_voice_state(ctx).stop()
        del self.voice_states[ctx.guild.id]

    @join.before_invoke
    @play.before_invoke
    @on_reaction_add.before_invoke
    async def ensure_voice_channel(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Bot is already in a voice channel. Use !move to switch channels.')

    @loop.before_invoke
    @queue.before_invoke
    @pause.before_invoke
    @skip.before_invoke
    @volume.before_invoke
    @resume.before_invoke
    @clearQueue.before_invoke
    @disconnect.before_invoke
    async def voice_state_must_exist(self, ctx: commands.Context):
        if not self.get_voice_state(ctx):
            raise commands.CommandError('Bot must be in a voice channel for this command!')


async def setup(bot):
    await bot.add_cog(MusicSFXCog(bot))