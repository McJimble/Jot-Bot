import discord
import yt_dlp
import json
import random
import asyncio
import functools
import math
import itertools
import sys
import time

from typing import Union
from async_timeout import timeout
from discord.ext import commands, tasks
from ..server_only_cog import ServerOnlyCog

jot_certfied = 'jot certified'
yes_reaction = '🟩'
no_reaction = '🟥'
filledSquare = '■'
emptySquare = '□'
emptySquaresInitProgBar = ''
for _ in range(20):
    emptySquaresInitProgBar += emptySquare

redHSV = [.01667, .74, .91]
greenHSV = [.27777, .74, .91]

std_cooldown = 5
pause_resume_cooldown = 10
temp_msg_cooldown = 25

# Since I only have like 30 hours of python coding experience in my life,
# I took most of the supporting classes from the link below, but added some extra stuff for my needs.
# https://gist.github.com/vbe0201/ade9b80f2d3b64643d854938d40a0a2d

class YTDLSource():
    YTDL_OPTIONS_PLAYLIST = {
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
        'extract_flat': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

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

    FFMPEG_OPTIONS = [
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        '-vn',
    ]
    
    ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
    ytdl_playlist = yt_dlp.YoutubeDL(YTDL_OPTIONS_PLAYLIST)

    def __init__(self, ctx: commands.Context, data: dict, volume: float):

        self.audio_source = None # discord.PCMVolumeTransformer, will be created with get_audio is called. DO NOT CALL DIRECTLY
        self.ffmpeg_source = None # discord.FFmpegPCMAudio, will be created with get_audio and passed into audio_source. DO NOT CALL!
        self.volume = volume

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
    
    # Create the FFMmpeg source with the stored data from constructor if it doesn't exist.
    # Can't create it in __init__ or too much memory is used when doing big playlists.
    @property
    def audio(self) -> discord.PCMVolumeTransformer:
        if self.audio_source is None:
            self.ffmpeg_source = discord.FFmpegPCMAudio(source=self.stream_url, before_options=YTDLSource.FFMPEG_OPTIONS[0], options=YTDLSource.FFMPEG_OPTIONS[1])
            self.audio_source = discord.PCMVolumeTransformer(self.ffmpeg_source, self.volume)
        return self.audio_source

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{:02d}'.format(days))
        if hours > 0:
            duration.append('{:02d}'.format(hours))

        duration.append('{:02d}'.format(minutes))
        duration.append('{:02d}'.format(seconds))

        finalstr = str(':'.join(duration))
        finalstr.removesuffix(':')
        return finalstr

class Song:

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        embed = (discord.Embed(title='Now playing',
                               description='```css\n{0.source.title}\n```'.format(self),
                               color=discord.Color.brand_green())
                 .add_field(name='Duration', value=self.source.duration)
                 .add_field(name='Requested by', value=self.requester.mention)
                 .add_field(name='Uploader', value='[{0.source.uploader}]({0.source.uploader_url})'.format(self))
                 .add_field(name='URL', value='[Click]({0.source.url})'.format(self))
                 .set_image(url=self.source.thumbnail))

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

    def remove(self, index: int) -> Song:
        ret = self._queue[index]
        if ret:
            del self._queue[index]
            return ret
        
        return None

# This is just a container to help me organize Queue logic.
# Could maybe abstract this better in the future but for now 
# it's just here to avoid doing some dictionary with list values bullshit or something
class TimedReactiveEmbed():

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
        self.context = context
        self._musicQueue = SongQueue()

        self.next = asyncio.Event()
        self.current = None
        self.voice = None
        self.currentChannel = None

        self.exists = True
        self.extracting_videos = False
        self.loop = False
        self.volume = 1.0
        self.volume_fac = 0.5       
        self.skip_proposal = None

        self.cooldowns = dict() # {cooldown_name (str): seconds_until_usable}
        self.cooldowns['p'] = 0
        self.cooldowns['r'] = 0
        self.cooldowns['q'] = 0
        self.cooldowns['v'] = 0
        self.cooldowns['n'] = 0

        # Represents an active Embed when downloading a playlist. Only one can exist at a time.
        # When not null, a playlist can be queued for download. Otherwise, user must wait until done.
        self.active_download_embed = None
        self.active_download_message = None
                                        
        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    # If no playlist download is occurring, creates and sets the current download embed.
    # If a playlist download is occurring, updates certain embed info (if provided)
    async def update_download_embed(self, ctx: commands.Context, data: dict, extractedVideos: int, failedVideos: int):
        
        playlistTitle = data['title']
        totalVideos = data['playlist_count']

        complete = extractedVideos + failedVideos == totalVideos
        progressStr = 'Complete!' if complete else 'In Progress...'

        embed = discord.Embed()
        embed.title = 'Extracting videos from playlist *{0}*'.format(playlistTitle)

        totalSquares = len(emptySquaresInitProgBar)
        fillFrac = float(extractedVideos) / totalVideos
        filledSquareCnt = int(totalSquares * fillFrac)

        # Text Progress Bar for description
        downloadProgressStr = str()
        for i in range(filledSquareCnt):
            downloadProgressStr += filledSquare
        embed.description = downloadProgressStr + emptySquaresInitProgBar[filledSquareCnt:]

        # Blend color from red to green, set embed color to this value.
        h = (1.0 - fillFrac) * redHSV[0] + fillFrac * greenHSV[0]
        s = redHSV[1]
        v = redHSV[2]
        embed.color = discord.Color.from_hsv(h, s, v)

        # Add fields
        embed.add_field(name='Extracted:', value='{0} / {1}'.format(extractedVideos, totalVideos))
        embed.add_field(name='Failed Extractions:', value=failedVideos)
        embed.add_field(name=progressStr, value=' ')

        # Set active values if this is a new message/embed. If they exist, edit current message.
        if self.active_download_embed is None:
            self.active_download_embed = embed
            self.active_download_message = await ctx.send(embed=embed)
        else:
            await self.active_download_message.edit(embed=embed)

    @property
    def musicQueue(self) -> SongQueue:
        return self._musicQueue

    def is_playing(self) -> bool:
        return self.voice and self.current

    def shuffle(self):
        self.musicQueue.shuffle()

    def clear_queue(self) -> bool:
        if self.musicQueue.empty():
            return False
            
        for _ in range(self._musicQueue.qsize()):
            self._musicQueue.get_nowait()
            self._musicQueue.task_done()

    def remove_queue_element(self, remVal: int):
        return self.musicQueue.remove(remVal)

    def reset_skip_state(self):
        if self.skip_proposal:
            self.creator.listening_skip_msgs.pop(self.skip_proposal.vote_message.id)
            self.skip_proposal = None

    async def audio_player_task(self):
        while True:
            self.next.clear()

            if not self.loop:
                # Try to get the next song within 1 minutes.
                # If no song will be added to the queue in time,
                # the player will disconnect due to performance
                # reasons.
                try:
                    async with timeout(60):  # 1 minute
                        self.current = await self.musicQueue.get()
                        self.reset_skip_state()

                except asyncio.TimeoutError:
                    if not self.extracting_videos and self.musicQueue.empty():
                        self.exists = False
                        self.bot.loop.create_task(self.stop())
                        return
                    continue

                self.voice.stop()
                self.current.source.audio.volume = self.volume * self.volume_fac
                self.voice.play(self.current.source.audio, after=self.play_next_song)
                await self.current.source.channel.send(embed=self.current.create_embed())

            elif self.loop:
                #print('playing on loop')
                self.voice.stop()
                ffmpeg = discord.FFmpegPCMAudio(source= self.current.source.stream_url, before_options=YTDLSource.FFMPEG_OPTIONS[0], options=YTDLSource.FFMPEG_OPTIONS[1])
                self.replay = discord.PCMVolumeTransformer(source=ffmpeg, volume=self.volume)
                self.voice.play(self.replay, after=self.play_next_song)

            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise Exception(str(error))
        
        self.next.set()


    async def skip(self):
        self.reset_skip_state()

        if self.is_playing():
            self.voice.stop()
            cur = str(self.current.source.title)
            if not self.musicQueue.empty():
                await self.context.send(f'Successfully skipped **{cur}**')
            else:
                self.current = None
                await self.context.send(f'Skip was successful.')

    async def stop(self):
        self.clear_queue()
        self.reset_skip_state()

        if self.voice:
            await self.voice.disconnect()
            self.voice.cleanup()
            self.voice = None

        self.creator.voice_states.pop(self.context.guild.id)

    async def set_volume(self, volume: float):
        self.volume = volume * self.volume_fac
        if self.is_playing():
            self.voice.pause()
            self.current.source.audio.volume = self.volume
            self.voice.resume()

class MusicSFXCog(ServerOnlyCog, name = "Music/Audio"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = dict() # {guild_id (int): voice_state}
        self.listening_skip_msgs = dict() # {message_id (int): voice_state}
        self.listening_queue_msgs = dict() # {user_id (int): MultiPageEmbed}

        self.handle_cooldowns.start()

        
    def get_voice_state(self, ctx: commands.Context) -> VoiceState:
        state = self.voice_states.get(ctx.guild.id)
        return state

    def get_non_bot_members(self, channel: discord.VoiceChannel) -> int:
        count = 0
        for mem in channel.members:
            if not mem.bot:
                count += 1

        return count

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    async def create_sources(self, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None) -> list: 

        # Processes a single entry and returns the YTDLSource.
        async def process_entry(loop: asyncio.BaseEventLoop, entry: str):
            webpage_url = entry.get('webpage_url')
            if webpage_url is None:
                webpage_url = entry.get('url')

            partial = functools.partial(YTDLSource.ytdl.extract_info, webpage_url, download=False)

            processed_info = await loop.run_in_executor(None, partial)
            if processed_info is None:
                raise Exception('Couldn\'t fetch `{}`'.format(webpage_url))

            if 'entries' not in processed_info:
                info = processed_info
            else:
                info = None
                while info is None:
                    try:
                        info = processed_info['entries']
                        info = info[0]
                    except IndexError:
                        raise Exception('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

            return YTDLSource(ctx, info, volume=self.get_voice_state(ctx).volume)
        
        loop = loop or asyncio.get_event_loop()
        state = self.get_voice_state(ctx)
        if not state:
            return
        
        partial = functools.partial(YTDLSource.ytdl_playlist.extract_info, search, download=False, process=True)
        data = await loop.run_in_executor(None, partial)
        data = yt_dlp.YoutubeDL.sanitize_info(data)

        if data is None:
            raise Exception('Couldn\'t find anything that matches `{}`'.format(search))

        sources = []

        # Single video; extract just once.
        if 'entries' not in data:
            result = await process_entry(loop, data)
            if result is None:
                raise Exception('Error processing data `{}`'.format(data))
            else:
                sources.append(result)

        # Playlist, but too long.
        elif len(data['entries']) > 100:
            raise Exception('Cannot extract a playlist larger than 100 videos for performance reasons.')
        
        # Playlist; go through each entry and add to list.
        else:
            if state.extracting_videos:
                await ctx.send('Already extracting a playlist. Please wait before extracting another.')
                return None
            
            state.extracting_videos = True
            currTime = time.time()
            prevTime = time.time()
            videosProcessed = videosFailed = 0
            entryProcessed = False
            for entry in data['entries']:
                try:
                    result = await process_entry(loop, entry)
                    if result is not None:
                        videosProcessed += 1
                        if entryProcessed == False:
                            await state.update_download_embed(ctx, data, videosProcessed, videosFailed)
                            entryProcessed = True
                        else:
                            # Wait 5 seconds at a time, then update embed.
                            currTime = time.time()
                            if (currTime - prevTime >= 5):
                                prevTime = currTime
                                await state.update_download_embed(ctx, data, videosProcessed, videosFailed)
                        sources.append(result)
                    else:
                        raise Exception('Video failed to process')
                    
                except Exception as e:
                    videosFailed += 1
            
            if not entryProcessed:
                raise Exception('Error processing entry `{}`'.format(entry))
            else:
                state.extracting_videos = False
                await state.update_download_embed(ctx, data, videosProcessed, videosFailed)
        
        return sources

    def generate_queue_embed(self, requestAuthor: discord.User, state: VoiceState, page: int):

        items_per_page = 10
        pages = math.ceil(len(state.musicQueue) / items_per_page)

        page = max(min(pages, page), 1)

        start = (page - 1) * items_per_page
        end = start + items_per_page
        queue = ''
        for i, song in enumerate(state.musicQueue[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(title='Queue view for {}'.format(requestAuthor.display_name),
                description='**{} tracks:**\n\n{}'.format(len(state.musicQueue), queue),
                color=discord.Color.gold())
                 .set_footer(text='Viewing page {}/{}'.format(page, pages)))
        
        return embed

    async def edit_and_update_queue_message(self, author: discord.User, state: VoiceState, queueMsg: TimedReactiveEmbed, newPage: int):
        newEmb = self.generate_queue_embed(author, state, newPage)
        newMsg = await queueMsg.message.edit(embed=newEmb)
        await newMsg.add_reaction('⏪')
        await newMsg.add_reaction('◀')
        await newMsg.add_reaction('▶')
        await newMsg.add_reaction('⏩')
        queueMsg.message = newMsg
        queueMsg.time_remaining = temp_msg_cooldown

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('An error occurred: {}'.format(str(error)))

    @tasks.loop(seconds=1)
    async def handle_cooldowns(self):
        for state in self.voice_states.values():
            for cmdVal in state.cooldowns:
                state.cooldowns[cmdVal] -= 1
                #print("{0}: {1}".format(cmdVal, state.cooldowns[cmdVal]))

        toDel = []
        for id in self.listening_queue_msgs.keys():
            listener = self.listening_queue_msgs[id]
            listener.time_remaining -= 1
            if listener.time_remaining <= 0:
                await listener.message.clear_reactions()
                toDel.append(id)

        for id in toDel:
            self.listening_queue_msgs.pop(id)
        

    @commands.command(name='Join', aliases = ['j'], help='Makes the bot join your current voice channel. Can be used to move the bot as well. **Shorthand: !bj**')
    async def join(self, ctx: commands.Context):
        state = self.get_voice_state(ctx)
        if not state or not state.exists:
            state = VoiceState(creator=self, bot = self.bot, context=ctx)
            self.voice_states[ctx.guild.id] = state

        elif state.voice and state.voice.channel == ctx.author.voice.channel:
            raise commands.CommandError('Bot is already in this voice channel')

        dest = ctx.author.voice.channel
        if state.voice:
            await state.voice.move_to(dest)
            if state.currentChannel != ctx.author.voice.channel:
                state.context = ctx
        else:
            state.voice = await dest.connect()

        state.currentChannel = ctx.author.voice.channel

    @commands.command(name='Play', aliases = ['p'], help='Searches for a youtube video with the specified search string and adds the first result to the queue. **Shorthand: !p**')
    async def play(self, ctx: commands.Context, *, search=''):
        if search == '':
            return await ctx.send('Please provide an expression to search with this command')

        if not self.get_voice_state(ctx):
            await self.join(ctx)

        state = self.get_voice_state(ctx)
        if not state:
            return

        async with ctx.typing():
            try:
                sources = await self.create_sources(ctx, search, loop=self.bot.loop)
                if sources is None:
                    return
            except Exception as e:
                state.extracting_videos = False
                await ctx.send('An error occured processing this request: {}'.format(str(e)))
            else:
                if len(sources) == 0:
                    await ctx.send('Error: URL returned no results')
                elif len(sources) == 1:
                    song = Song(sources[0])
                    await self.get_voice_state(ctx).musicQueue.put(song)
                    await ctx.send('{} added to queue.'.format(str(sources[0])))
                else:
                    cnt = 0
                    for source in sources:
                        song = Song(source)
                        await self.get_voice_state(ctx).musicQueue.put(song)
                        cnt += 1

                    state.active_download_embed = None
                    state.active_download_message = None
                    await ctx.send('Successfully added {} videos from playlist. Check queue for details.'.format(str(cnt)))
    
    @commands.command(name='VoteSkip', aliases=['vs'], help='Same as !skip, but guarantees a vote is started (instead of being bypassed by admins/requester). **Shorthand: !vs**')
    async def voteskip(self, ctx: commands.Context):
        await self.skip(ctx, certifiedVote='v')

    @commands.command(name='Skip', aliases=['s'], help='Starts a vote skip on the currently playing song. Jot certfied users OR song requester skip automatically unless !voteskip was used. **Shorthand: !s**')
    async def skip(self, ctx: commands.Context, *, certifiedVote=''):
        state = self.get_voice_state(ctx)

        if not state.is_playing():
            return await ctx.send('Nothing to skip!')

        # Admins, jot certified users, or song requester can skip, unless they specified to vote as a parameter.
        if ctx.author.id == state.current.source.requester.id or ((ctx.author.guild_permissions.administrator or self.is_user_jot_certified(ctx)) and state.is_playing()):
            if not certifiedVote.lower() in ['v', 'vote']:
                await state.skip()
                return

        if state.skip_proposal:
            embed = discord.Embed()
            embed.color = discord.Color.red()
            embed.title = "{} is already proposed to skip!".format(str(state.current.source.title))
            embed.description = "[Jump to message and vote here]({})".format(str(state.skip_proposal.vote_message.jump_url))
            await ctx.send(embed=embed)
        else:
            users = self.get_non_bot_members(state.currentChannel)
            embed = discord.Embed()
            embed.title = '**Skip \'{}\'?**'.format(str(state.current.source.title))
            embed.description = '**{0} out of {1}** users in the channel must react with 🟩 to skip.'.format(math.ceil(max(1, users / 2)), users)
            msg = await ctx.send(embed=embed)
            state.skip_proposal = VoteProposal(message=msg)
            await msg.add_reaction('🟩')
            self.listening_skip_msgs[msg.id] = state

    @commands.command(name='Current', aliases=['playing', 'now', 'n'], help='Shows the currently playing song. **Shorthands: !playing, !now, !n**')
    async def now(self, ctx: commands.Context):

        state = self.get_voice_state(ctx)
        if state.cooldowns['n'] > 0:
            return await ctx.send("\'Playing\' command is on cooldown. Please wait another {} seconds.".format(str(state.cooldowns['n'])))

        state.cooldowns['n'] = std_cooldown
        await ctx.send(embed=state.current.create_embed())

    @commands.command(name='Pause', aliases=['pau', 'pa'], help='Pauses the music until resumed. **Shorthand: !pau, !pa**')
    async def pause(self, ctx: commands.Context):
        
        state = self.get_voice_state(ctx)
        if state.cooldowns['p'] > 0:
            return await ctx.send("\'Pause\' command is on cooldown. Please wait another {} seconds.".format(str(state.cooldowns['p'])))

        if state.is_playing() and state.voice.is_playing():
            state.voice.pause()
            state.cooldowns['p'] = pause_resume_cooldown
            await ctx.send("Player is paused.")
        pass

    @commands.command(name='Resume', aliases=['res'], help='Resumes the current song if music is currently paused. **Shorthand: !res**')
    async def resume(self, ctx: commands.Context):

        state = self.get_voice_state(ctx)
        if state.cooldowns['r'] > 0:
            return await ctx.send("\'Resume\' command is on cooldown. Please wait another {} seconds.".format(str(state.cooldowns['r'])))

        if state.is_playing() and not state.voice.is_playing():
            state.voice.resume()
            state.cooldowns['r'] = pause_resume_cooldown
            await ctx.send("Resuming Player.")
        pass

    @commands.command(name='Volume', aliases=['v'], help='Sets the volume of the player. Can set values from 0-500%')
    async def volume(self, ctx: commands.Context, *, val: int):
        state = self.get_voice_state(ctx)
        if state.cooldowns['v'] > 0:
            return await ctx.send('\'Volume\' command is on cooldown. Please wait {} seconds'.format(str(state.cooldowns['v'])))
        else:
            val = max(min(1000, val), 0)
            await ctx.send('Setting volume to **{}%**'.format(str(val)))
            await state.set_volume(val / 100)
            state.cooldowns['v'] = std_cooldown
        pass 

    @commands.command(name='Queue', aliases=['q'], help='Displays the current queue, with specified page, 10 sources per page. React to the response to go to the first, previous, next, and last pages respectively. **Shorthand: !q**')
    async def queue(self, ctx: commands.Context, *, pg=1):
        async def send_and_react(state):
            emb = self.generate_queue_embed(ctx.author, state, pg)
            msg = await ctx.send(embed=emb)
            await msg.add_reaction('⏪')
            await msg.add_reaction('◀')
            await msg.add_reaction('▶')
            await msg.add_reaction('⏩')
            return msg

        state = self.get_voice_state(ctx)
        if state.cooldowns['q'] > 0:
            return await ctx.send('\'Queue\' command used too quickly. Please wait {} seconds.'.format(str(state.cooldowns['q'])))
        if len(state.musicQueue) == 0:
            return await ctx.send('Queue is empty!')

        listener = self.listening_queue_msgs.get(ctx.author.id)
        if listener:
            await listener.message.delete()
            msg = await send_and_react(state)
            listener.message = msg
            listener.time_remaining = temp_msg_cooldown
            state.cooldowns['q'] = std_cooldown
            pass
        else:
            msg = await send_and_react(state)
            listener = TimedReactiveEmbed(msg, current_page=pg)
            listener.message = msg
            state.cooldowns['q'] = std_cooldown
            self.listening_queue_msgs[ctx.author.id] = listener
        pass

    @commands.command(name='Reset', aliases=['restart'], help='Stops audio, clears queue, and rejoins voice channel. Use if bot gets stuck.')
    async def reset(self, ctx: commands.Context):
        state = self.get_voice_state(ctx)

        if state:
            await state.stop()

            # Just so error doesn't appear if reset was called by someone outside the channel
            if not ctx.author.voice or not ctx.author.voice.channel:
                await self.join(ctx)
                

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
            if state.skip_proposal.total_votes >= math.ceil(self.get_non_bot_members(state.currentChannel) / 2):
                await state.skip()

        # Check for queue reaction; works if reaction author matches id of someone who recently asked for queue
        state = self.voice_states.get(user.guild.id)
        queueListener = self.listening_queue_msgs.get(user.id)
        if queueListener:
            match str(reaction.emoji):
                case '⏪':
                    queueListener.current_page = 1
                    pass
                case '◀':
                    queueListener.current_page -= 1
                    pass
                case '▶':
                    queueListener.current_page += 1
                    pass
                case '⏩':
                    queueListener.current_page = math.ceil(len(state.musicQueue) / 10)
                    pass
            await self.edit_and_update_queue_message(user, state, queueListener, queueListener.current_page)
        pass
    
    @commands.command(name='Shuffle', aliases=['sh'], help='Shuffles the current queue. **Shorthand: !sh**')
    async def shuffle(self, ctx: commands.Context):
        self.get_voice_state(ctx).shuffle()
        await ctx.send('Successfully shuffled queue. Use !queue for details.')
        pass

    @commands.command(name='Loop', aliases=['l'], help='Loops the current songs until this command is used again. **Shorthand: !l**')
    async def loop(self, ctx: commands.Context):
        state = self.get_voice_state(ctx)
        if not state.is_playing():
            return await ctx.send('Cannot loop, nothing is currently being played.')

        state.loop = not state.loop
        if state.loop:
            await ctx.send('**{}** is now being looped.'.format(str(state.current.source.title)))
        else:
            await ctx.send('Loop disabled.')

    @commands.command(name='ClearQueue', aliases=['c', 'clear'], help='Clears the current queue')
    async def clearQueue(self, ctx: commands.Context):
        state = self.get_voice_state(ctx)

        if not state.musicQueue.empty():
            state.clear_queue()
            await ctx.send('Queue cleared!')
        else:
            await ctx.send('Queue is already empty.')
        pass

    @commands.command(name='Remove', aliases=['r'], help='Removes the specified source index from the queue. Use the same value displayed by !q. **Shorthand: !r**')
    async def remove(self, ctx: commands.Context, *, rem: int):
        state = self.get_voice_state(ctx)

        if state.musicQueue.empty():
            raise commands.CommandError('Cannot remove from empty queue.')
        elif rem <= 0 or state.musicQueue.qsize() < rem - 1:
            raise commands.CommandError('Invalid queue index.')

        remSong = state.remove_queue_element(rem - 1)
        if remSong:
            songName = str(remSong.source.title)
            await ctx.send(f'Successfully removed {songName}')

    @commands.command(name='Disconnect', aliases=['dc'], help='Disconnects the bot from the current voice channel. **Shorthand: !dc**')
    async def disconnect(self, ctx: commands.Context):
        state = self.get_voice_state(ctx)
        if state:
            await state.stop()

    @join.before_invoke
    @play.before_invoke
    async def ensure_voice_channel(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            state = self.get_voice_state(ctx)
            if state and state.voice:
                return
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Bot is already in a voice channel. Use !move to switch channels.')

    @loop.before_invoke
    @queue.before_invoke
    @pause.before_invoke
    @now.before_invoke
    @skip.before_invoke
    @volume.before_invoke
    @resume.before_invoke
    @clearQueue.before_invoke
    async def voice_state_must_exist(self, ctx: commands.Context):
        if not self.get_voice_state(ctx):
            raise commands.CommandError('Bot must be in a voice channel for this command!')
        
    @loop.before_invoke
    @volume.before_invoke
    @clearQueue.before_invoke
    @disconnect.before_invoke
    @reset.before_invoke
    @shuffle.before_invoke
    async def user_must_be_certified(self, ctx: commands.Context):
        if not self.is_user_jot_certified(ctx):
            raise commands.CommandError('Cannot use this command, user must be Jot Certified!')
    
    def is_user_jot_certified(self, ctx: commands.Context):
        roles = ctx.author.roles
        for role in roles:
            if role.name.lower() == jot_certfied:
                return True
            
        return False
        


async def setup(bot):
    await bot.add_cog(MusicSFXCog(bot))