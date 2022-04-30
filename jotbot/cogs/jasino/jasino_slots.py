import enum

class JasinoIconType(enum.Enum):
    normal = 1
    wild = 2
    reroll = 3
    lose_all = 4

# Container for different icon info to make things more organized; makes it easy to add/remove them.
class JasinoIcon():

    def __init__(self, iconEncoding: str, payout: int, id: int, weight: int, type: JasinoIconType):
        self.iconEncoding = iconEncoding
        self.payout = payout
        self.id = id    # To more easily say one is equal to another
        self.weight = weight
        self.type = type

    def __lt__(self, other):
        return self.payout < other.payout

    def payoutMessageByType(self, bet):
        match self.type:
            case JasinoIconType.normal:
                WorL = "won" if bet * self.payout > 0 else "LOST"
                return f"You {WorL} ${abs(bet * self.payout)} from matching {self.iconEncoding}"
            case JasinoIconType.wild:
                return f"HOLY FUCK YOU WON THE JACKPOT BITCH!!! YOU GOT ${bet * self.payout}"
            case JasinoIconType.reroll:
                return f"You won a free reroll!"
            case JasinoIconType.lose_all:
                return f"Ha ha you lost all yo money nigga, boo hoo let me help you wipe off those tears with my fat stacks"
    
    def extraHelpInfo(self):
        match self.type:
            case JasinoIconType.normal:
                return str()
            case JasinoIconType.wild:
                return "(Wild; Can be matched with any other icon)"
            case JasinoIconType.reroll:
                return "(Awards a free reroll)"
            case JasinoIconType.lose_all:
                return "(Lose all your money lol)"
