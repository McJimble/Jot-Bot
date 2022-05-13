import enum
from random import randint

class Card():
    class Suit(enum.IntEnum):
        spade = 0,
        club = 1,
        heart = 2,
        diamond = 3

    # Convert a card suit enum to int() and use that as the index here.
    suitUnicodes = ['\u2664', '\u2667', '\u2661', '\u2662']

    def __init__(self, value: int, suit: Suit):
        self.value = value
        self.suit = suit

    def __str__(self):
        return self.valToString() + Card.suitUnicodes[int(self.suit)]

    def __eq__(self, other):
        return self.value == other.value and int(self.suit) == int(other.suit)

    def generateDeck():
        deck = []
        for suit in range(0, 4):    # For each of the 4 suits ...
            for x in range(2, 15):  # Generate values 2 - 14...
                deck.append(Card(x, Card.Suit(suit)))    # J, Q, K, A are accounted for string reps. on their own

        return list(deck)

    def valToString(self):
        if self.value <= 10:
            return str(self.value)
        
        match self.value:
            case 11:
                return 'J'
            case 12:
                return 'Q'
            case 13:
                return 'K'
            case 14:
                return 'A'

    def charToVal(letter: chr):
        try:
            ret = int(letter)
            return ret
        except ValueError:
            match letter:
                case 'J':
                    return 11
                case 'Q':
                    return 12
                case 'K':
                    return 13
                case 'A':
                    return 14
            
            return None

    def getBlackJackValue(self):
        if self.value <= 10:
            return self.value
        elif self.value >= 11 and self.value < 14:
            return 10
        else:
            return 11


class Blackjack():

    class State(enum.Enum):
        ongoing = 1
        dealerWin = 2
        playerWin = 3
        tie = 4

    # Parsing the state string has no error-checking btw
    def __init__(self, stateStr=""):
        self.dealer = []
        self.player = []
        self.deck = Card.generateDeck()
        self.lastGameLoopOutcome = str()

        self.state = Blackjack.State.ongoing
        self.stand = False
        self.gameOver = False

        if len(stateStr) <= 0 or stateStr is None:
            self.dealCards()
            totDealer = Blackjack.getHandBJValue(self.dealer)
            totPlayer = Blackjack.getHandBJValue(self.player)

            if totPlayer == 21 and totDealer != 21 and self.state == Blackjack.State.ongoing:
                self.lastGameLoopOutcome += "You beat the dealer with a blackjack!\n"
                self.state = Blackjack.State.playerWin
                self.gameOver = True

            return

        state = stateStr.split(' ')

        dealerCards = state[0].split(',')
        playerCards = state[1].split(',')
        for card in dealerCards:
            if card[0] != '1':
                val = int(Card.charToVal(card[0]))
                suit = Card.suitUnicodes.index(card[1])
            else:
                val = int(Card.charToVal(card[0:2]))
                suit = Card.suitUnicodes.index(card[2])

            self.dealer.append(Card(val, Card.Suit(suit)))
            self.deck.remove(self.dealer[-1])

        for card in playerCards:
            if card[0] != '1':
                val = int(Card.charToVal(card[0]))
                suit = Card.suitUnicodes.index(card[1])
            else:
                val = int(Card.charToVal(card[0:2]))
                suit = Card.suitUnicodes.index(card[2])

            self.player.append(Card(val, Card.Suit(suit)))
            self.deck.remove(self.player[-1])

    def __str__(self):
        ret = str()
        dLength = len(self.dealer)
        for i in range(0, dLength):
            ret += str(self.dealer[i])
            if i < dLength - 1:
                ret += ','
        
        ret += " "

        pLength = len(self.player)
        for i in range(0, pLength):
            ret += str(self.player[i])
            if i < pLength - 1:
                ret += ','

        return ret

    # Returns the blackjack value of the given hand, accounting for aces.
    #
    # hand: iterable that only contains Card instances.
    def getHandBJValue(hand, hideLast=False):
        lHand = len(hand)
        tot = 0
        aceCount = 0
        for i in range(0, lHand):
            if hideLast and i == lHand - 1:
                break

            card = hand[i]
            bjVal = card.getBlackJackValue()
            if card.value == 14:
                tot += 1
                aceCount += 1
            else:
                tot += bjVal

        # Account for aces last in case they make user bust; this way we don't
        # have to sort or something to check for this.
        for i in range(0, aceCount):
            if (tot + 10) <= 21:
                tot += 10
            else:
                break

        return tot

    def getStateStrDealerHidden(self):
        ret = str()
        dLength = len(self.dealer)
        for i in range(0, dLength):
            if i == dLength - 1:
                ret += "??"
            else:
                ret += str(self.dealer[i])
            if i < dLength - 1:
                ret += ','
        
        ret += " "

        pLength = len(self.player)
        for i in range(0, pLength):
            ret += str(self.player[i])
            if i < pLength - 1:
                ret += ','

        return ret

    def dealCards(self):
        self.dealer.append(self.deck.pop(randint(0, len(self.deck) - 1)))
        self.player.append(self.deck.pop(randint(0, len(self.deck) - 1)))
        self.dealer.append(self.deck.pop(randint(0, len(self.deck) - 1)))
        self.player.append(self.deck.pop(randint(0, len(self.deck) - 1)))
        

    def tryDealerDraw(self):
        if Blackjack.getHandBJValue(self.dealer) < 17:
            self.dealer.append(self.deck.pop(randint(0, len(self.deck) - 1)))

            totDealer = Blackjack.getHandBJValue(self.dealer)

            if totDealer > 21:
                self.lastGameLoopOutcome += "The dealer busted!\n"
                self.state = Blackjack.State.playerWin

            return True

        return False


    def playerDraw(self):
        self.player.append(self.deck.pop(randint(0, len(self.deck) - 1)))
        self.lastGameLoopOutcome += f"You drew a {str(self.player[-1])}\n"

        totPlayer = Blackjack.getHandBJValue(self.player)

        if totPlayer > 21:
            self.lastGameLoopOutcome = "You busted!"
            self.state = Blackjack.State.dealerWin
            self.gameOver = True

    def gameLogicLoop(self):
        if self.gameOver:
            return
        self.lastGameLoopOutcome = ""
        if self.stand:
            while self.tryDealerDraw():
                pass
        else:
            temp = self.tryDealerDraw()
            if temp:
                self.lastGameLoopOutcome += f" The dealer drew another card. Revealing the previous one drawn.\n"


        totDealer = Blackjack.getHandBJValue(self.dealer)
        totPlayer = Blackjack.getHandBJValue(self.player)

        if totPlayer == 21 and totDealer < 21 and totDealer >= 17 and self.state == Blackjack.State.ongoing:
            self.lastGameLoopOutcome += "You beat the dealer with a blackjack!\n"
            self.state = Blackjack.State.playerWin
            self.gameOver = True
            return

        if self.state == Blackjack.State.ongoing and not self.stand:
            if totDealer == 21 and totPlayer == 21:
                self.lastGameLoopOutcome += "You tied with the dealer.\n"
                self.state = Blackjack.State.tie
            elif totDealer > 21:
                self.lastGameLoopOutcome += "The dealer busted!\n"
                self.state = Blackjack.State.playerWin
            elif totPlayer > 21:
                self.lastGameLoopOutcome += "You busted!\n"
                self.state = Blackjack.State.dealerWin
        else:
            if totDealer == totPlayer:
                self.lastGameLoopOutcome += "You tied with the dealer.\n"
                self.state = Blackjack.State.tie
            elif totDealer > totPlayer and totDealer <= 21:
                self.lastGameLoopOutcome += "The dealer won...\n"
                self.state = Blackjack.State.dealerWin
            elif totPlayer <= 21:
                self.lastGameLoopOutcome += "You beat the dealer!\n"
                self.state = Blackjack.State.playerWin

        if self.state != Blackjack.State.ongoing:
            self.gameOver = True
        pass

    def playerHit(self):
        if self.state != Blackjack.State.ongoing and not self.stand:
            return

        self.playerDraw()
        self.gameLogicLoop()
        

    def playerStand(self):
        if self.state != Blackjack.State.ongoing:
            return

        self.stand = True
        self.gameLogicLoop()
