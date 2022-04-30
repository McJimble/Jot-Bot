import discord
import sqlite3
from .jasino_cards import *
from .jasino_random import *
from .jasino_slots import *

from discord.ext import commands, tasks
from random import *

moneyPerTick = 10
moneyTickRate = 1

slotSizeX = 4
slotSizeY = 4

# Casino but the 'C' is 'J' lol
class JasinoCog(commands.Cog, name = "jasino"):

    def __init__(self, bot):
        self.bot = bot
        self.jasinoChannel = 966891187535511552
        self.lottery_jimmy_old.start()
        self.award_money_all.start()
        self.slotColorWin = discord.Colour.green()
        self.slotColorLose = discord.Colour.red()
        self.slotColorNeutral = discord.Colour.dark_gold()

        # Icons paired with their probability weight
        self.jasinoIcons = [
            JasinoIcon(':black_joker:',             7777, 0, 20,  JasinoIconType.wild),
            JasinoIcon(u'😎',                       500,  2, 30,  JasinoIconType.normal),
            JasinoIcon(u'💩',                       0,    1, 50,  JasinoIconType.lose_all),    # Lose all your money lol
            JasinoIcon(u'🥨',                       150,  4, 100,  JasinoIconType.normal),
            JasinoIcon(u'🍒',                       25,   5, 200,  JasinoIconType.normal),
            JasinoIcon(u'🍐',                       5,    7, 225,  JasinoIconType.normal),
            JasinoIcon(':arrows_counterclockwise:',  1,   9, 250,  JasinoIconType.reroll),
        ]

        # TODO: move this to real database on AWS at some point. Current implementation saves DB locally on the
        # instance hosting the script. This is obviously a dogshit way to do stuff if more people ever use this.
        self.localDB = sqlite3.connect('jasino.db')
        self.dbCursor = self.localDB.cursor()
        self.dbCursor.execute('''
            CREATE TABLE IF NOT EXISTS jasinousers(user_id INTEGER, display_name TEXT, balance INTEGER, blackjack_state TEXT)''')

    # Verifies that the user is already in the database. If they are, returns their balance.
    # user: user object, prefereably from converting in a command.
    def verifyDBEntry(self, user: discord.User):
        self.dbCursor.execute(f"SELECT balance FROM jasinousers WHERE user_id = {user.id}")
        res = self.dbCursor.fetchone()
        if res is None:
            sql = ("INSERT INTO jasinousers(user_id, display_name, balance, blackjack_state) VALUES(?, ?, ?, ?)")
            val = (user.id, user.name, 100, "")
            self.dbCursor.execute(sql, val)
            self.localDB.commit()
            print(f"{user.name} not in the table, inserting with $100")
            return 0

        return int(res[0])

    def getUserBJState(self, user: discord.User):
        self.verifyDBEntry(user)
        self.dbCursor.execute(f"SELECT blackjack_state FROM jasinousers WHERE user_id = {user.id}")
        res = self.dbCursor.fetchone()
        return str(res[0])

    def setUserBJState(self, user: discord.User, state: str):
        self.verifyDBEntry(user)
        sql = ("UPDATE jasinousers SET blackjack_state = ? WHERE user_id = ?")
        val = (state, user.id)
        self.dbCursor.execute(sql, val)
        self.localDB.commit()

    def resetUserBalance(self, user: discord.User):
        self.dbCursor.execute(f"SELECT balance FROM jasinousers WHERE user_id = {user.id}")
        res = self.dbCursor.fetchone()
        if res is not None:
            sql = ("UPDATE jasinousers SET balance = ? WHERE user_id = ?")
            val = (str(0), user.id)
            self.dbCursor.execute(sql, val)
            self.localDB.commit()
            return 0
    
    async def addBalance(self, ctx, amt: int, printResult=False):
        user = ctx.author
        balance = self.verifyDBEntry(user)
        
        sql = ("UPDATE jasinousers SET balance = ? WHERE user_id = ?")
        val = (str(balance + amt), user.id)
        self.dbCursor.execute(sql, val)
        self.localDB.commit()

        balance = self.verifyDBEntry(user)

        if printResult:
            await ctx.send(f"Added ${amt}, new balance: ${balance}.")


    def generateSlotCheckPositions(self, countX: int, countY: int):
        
        positions = []

        # Generate horizontal matches
        for y in range(countY):
            horizontalPositions = []
            for x in range(countY):
                horizontalPositions.append((y, x))
            positions.append(horizontalPositions)

        # Generate vertical matches
        for y in range(countY):
            verticalPositions = []
            for x in range(countY):
                verticalPositions.append((x, y))
            positions.append(verticalPositions)

        # Generate diagonal matches
        diagonalPositions1 = []
        diagonalPositions2 = []
        for x in range(countX):
            diagonalPositions1.append((x, x))
            diagonalPositions2.append((x, countX - x - 1))

        positions.append(diagonalPositions1)
        positions.append(diagonalPositions2)

        return positions
    
    def match_sequential(self, posList, results):
        lastNonWild = None
        length = len(posList) #cache bc why not
        for i in range(0, length):
            cur = results[posList[i][1]][posList[i][0]]

            if cur.type == JasinoIconType.wild:
                continue

            if lastNonWild is not None:
                if cur.id != lastNonWild.id:
                    return None
            lastNonWild = cur if cur.type != JasinoIconType.wild else lastNonWild
            
        lastNonWild = lastNonWild if lastNonWild is not None else self.jasinoIcons[0]
        return lastNonWild

    # Verifies the bet is valid based on current balance and sign of bet.
    # Removes the bet amount from balance if valid.
    # Assumes bet is a string at first, since it initially comes as one from command args.
    #
    # Returns: Tuple -> (bet: int, balance: int)
    async def verifyBet(self, ctx, bet: str, autoRemove=True):
        if bet == "allin":
            bet = self.verifyDBEntry(ctx.author)
            if bet == 0:
                return None
        else:
            try:
                bet = int(bet)
            except ValueError:
                return None

        if bet < 0:
            return None

        balance = self.verifyDBEntry(ctx.author)
        if bet > balance or balance == 0:
            await ctx.send(f"You don't have enough money to bet that much {ctx.author.name}!")
            return None

        if autoRemove:
            await self.addBalance(ctx, -bet)

        return (bet, balance)

    @commands.command()
    async def slothelp(self, ctx):
        useStr = "**Usage**\n!slots <bet amount> : spin the slots, taking the bet amount from your account\n" "!slots allin : spin the slots, using all the money in your account\n"

        iconInfo = "\n**Payouts**\nMatching 4 in a row of one of these horizontally or diagonally awards (bet X payout):\n"
        for icon in sorted(self.jasinoIcons):
            iconInfo += f"{icon.iconEncoding}: ${icon.payout} {icon.extraHelpInfo()}\n"
        await ctx.send(f"{useStr}{iconInfo}")

    @commands.command()
    async def slots(self, ctx, bet):

        temp = await self.verifyBet(ctx, bet)
        if temp is None:
            return

        bet = temp[0]
        balance = temp[1]

        resultIcons = [[]*slotSizeY]*slotSizeX # 4x4 2d array of icons
        for x in range(slotSizeX):
            resultIcons[x] = weighted_random_list(self.jasinoIcons, slotSizeX)

        posList = self.generateSlotCheckPositions(slotSizeX, slotSizeY)
        results = []

        for positions in posList:
            # Get result from match func., payout for each slot icon returned from it.
            r = self.match_sequential(positions, resultIcons)
            if r is not None:
                results.append(r)
        
        payoutMessages = []
        payoutTotal = 0
        reroll = False
        if len(results) <= 0:
            payoutMessages = ["You win nothing, loser"]
        for result in results:
            payoutTotal += bet * result.payout

            if result.type == JasinoIconType.lose_all:
                payoutTotal = int(await self.verifyDBEntry(ctx.author)) * -1
                payoutMessages = [result.payoutMessageByType(payoutTotal)]
                await self.resetUserBalance(ctx.author)
                break
            
            reroll = True if result.type == JasinoIconType.reroll else reroll

            payoutMessages.append(result.payoutMessageByType(bet))
            await self.addBalance(ctx, bet * result.payout)

        await self.sendSlotResultEmbed(ctx, resultIcons, payoutMessages, bet, payoutTotal)

        if reroll:
            await self.slots(ctx, bet)
    
    async def sendSlotResultEmbed(self, ctx, resultIcons, payoutMsgs, bet: int, payoutTotal: int):
        bal = self.verifyDBEntry(ctx.author)
        sign = '+' if payoutTotal - bet >= 0 else '-'

        slotEmbed = discord.Embed()
        slotEmbed.description = "\n".join(payoutMsgs)

        titleAppend = None
        if payoutTotal > 0:
            slotEmbed.color = self.slotColorWin
            titleAppend = "You Win!!!"
        elif payoutTotal < 0:
            slotEmbed.color = self.slotColorLose
            titleAppend = "You Lost..."
        else:
            slotEmbed.color = self.slotColorNeutral
            titleAppend = "You Lost..."

        slotEmbed.title = f"{ctx.author.name}, {titleAppend}"

        slotStr = str()
        for y in range(slotSizeX):
            for x in range(slotSizeY):
                slotStr += resultIcons[x][y].iconEncoding
            slotStr += '\n'

        slotEmbed.add_field(name="Bet:", value=str(bet))
        slotEmbed.add_field(name="Payout:", value=f"${payoutTotal}")
        slotEmbed.add_field(name="Slot Result:", value=slotStr, inline=False)
        slotEmbed.add_field(name="New Balance:", value=f"${bal} ({sign}${abs(payoutTotal - bet)})")

        await ctx.send(embed=slotEmbed)

    @commands.command()
    async def bj(self, ctx, arg: str):
        await self.blackjack(ctx, arg)

    @commands.command()
    async def blackjack(self, ctx, arg: str):
        bjState = self.getUserBJState(ctx.author)
        betData = await self.verifyBet(ctx, arg, False)
        bet = None
        firstMove = False

        # If no bjState, assume user is trying to bet.
        if len(bjState) <= 0:
            if betData is None:
                await ctx.send(f"You are not currently in a blackjack match, **{ctx.author.name}**\nStart a match with !blackjack <bet amount>")
                return
            bet = betData[0]
            await self.addBalance(ctx, -bet)
            firstMove = True

        # If there is a bjState, retrieve bet and state from DB, then initialize the game.
        else:
            bjState = bjState.split(' ')
            bet = int(bjState.pop(2).strip())
            bjState = " ".join(bjState)

        # Assume game is ongoing or brand-new, as state is reset in DB upon a game ending.
        bjGame = Blackjack(bjState)

        if bjGame.state == Blackjack.State.ongoing and not firstMove:
            if arg.lower() == "hit":
                bjGame.playerHit()
            elif arg.lower() == "stand":
                bjGame.playerStand()
            else:
                await ctx.send(f"Invalid move. You can only **Hit** or **Stand**")
                return

        payout = 0
        if bjGame.gameOver:
            match bjGame.state:
                case Blackjack.State.tie:
                    payout = bet
                    await self.addBalance(ctx, bet)
                case Blackjack.State.playerWin:
                    payout = bet * 2
                    await self.addBalance(ctx, payout)

            # Set bj state in DB to empty
            self.setUserBJState(ctx.author, "")
            pass
        else:
            # Set bj state in DB to str(bjGame) + " bet"
            self.setUserBJState(ctx.author, str(bjGame) + f" {bet}")
            pass
        
        await self.sendBlackJackEmbed(ctx, bet, payout, bjGame, firstMove)
        pass

    async def sendBlackJackEmbed(self, ctx, bet: int, payout: int, bjGame: Blackjack, firstMove=False):
        bal = self.verifyDBEntry(ctx.author)
        sign = '+' if payout - bet >= 0 else '-'

        bjEmbed = discord.Embed()
        bjEmbed.color = discord.Color.blurple()
        dealerStr = bjGame.getStateStrDealerHidden().split(' ')[0]
        dealerHidden = True

        if firstMove:
            bjEmbed.title = f"New game started, {ctx.author.name}"
        else:
            bjEmbed.title = f"Match ongoing for {ctx.author.name}"
            
        if bjGame.gameOver:

            dealerStr = str(bjGame).split(' ')[0]
            dealerHidden = False

            match bjGame.state:
                case Blackjack.State.playerWin:
                    bjEmbed.title = f"You Win, {ctx.author.name}!!"
                    bjEmbed.color = discord.Color.green()
                    pass
                case Blackjack.State.dealerWin:
                    bjEmbed.title = f"You lost, {ctx.author.name}..."
                    bjEmbed.color = discord.Color.red()
                    pass
                case Blackjack.State.tie:
                    bjEmbed.title = f"It's a tie, {ctx.author.name}."
                    bjEmbed.color = discord.Color.dark_gold()
                    pass
        
        bjEmbed.add_field(name="Dealer Hand:", value=dealerStr)
        bjEmbed.add_field(name="Dealer Value:", value=Blackjack.getHandBJValue(bjGame.dealer, dealerHidden))
        bjEmbed.add_field(name="\u200B", value="\u200B")
        bjEmbed.add_field(name="Player Hand:", value=str(bjGame).split(' ')[1])
        bjEmbed.add_field(name="Player Value:", value=Blackjack.getHandBJValue(bjGame.player))
        bjEmbed.add_field(name="\u200B", value="\u200B")

        if bjGame.state == Blackjack.State.playerWin or bjGame.state == Blackjack.State.tie or firstMove:
            bjEmbed.add_field(name="New Balance:", value=f"${bal} (${sign}{abs(payout - bet)})")
        
        bjEmbed.description = bjGame.lastGameLoopOutcome

        await ctx.send(embed=bjEmbed)

    @commands.command()
    async def balance(self, ctx):
        user = ctx.author
        balance = self.verifyDBEntry(user)
        
        await ctx.send(f"{user.name} currently has ${balance}")

    @tasks.loop(minutes=moneyTickRate)
    async def award_money_all(self):
        sql = (f"UPDATE jasinousers SET balance = balance + {moneyPerTick}")
        self.dbCursor.execute(sql)
        self.localDB.commit()

    @commands.command()
    async def rolldice(self, ctx, amt: int):

        rollTotal = 0
        for i in range(amt):
            rollTotal += randint(1, 6)

        await ctx.send(f"You rolled a: {rollTotal}")


    # Simple idea friend had where there is a 1/20,000,000 chance every second of someone receiving
    # $5 from everyone on our server.
    @tasks.loop(seconds=1)
    async def lottery_jimmy_old(self):
        valJ = randint(0, 10000000)
        if valJ == 1:
            await self.bot.get_channel(self.jasinoChannel).send("Jimmy. @everyone")

        names = ["Jimmy", "Dan", "Matt", "James", "Adam", "Carmelo", "Jorge", "Mark"]
        valWin = randint(0, 20000000)
        if valWin == 2:
            winner = names[randint(0, len(names) - 1)]
            await self.bot.get_channel(self.jasinoChannel).send(winner.upper() + " WINS $5 FROM EVERY USER ON THE SERVER!!! @everyone")

    @commands.command()
    async def set_jasino_channel(self, ctx, id: int):
        self.jasinoChannel = id
        print(id)

def setup(bot):
    bot.add_cog(JasinoCog(bot))