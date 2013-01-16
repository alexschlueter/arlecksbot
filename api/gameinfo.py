import random

from api.vector2 import Vector2

class LevelInfo(object):
    """
    Provides information about the level the game is played in.
    """

    def __init__(self):
        super(LevelInfo, self).__init__()

        self.width = 0
        """
        The width of world grid
        """
        self.height = 0
        """
        The height of world grid
        """
        self.blockHeights = [[]]
        """
        2d list describing the size of block at each position in world, 0 if there is no block at this position
        """

        self.teamNames = []
        """
        A list of the team names supported by this level.
        """
        self.flagSpawnLocations = {}
        """
        Map of team name the spawn location (Vector2) of the team's flag
        """
        self.flagScoreLocations = {}
        """
        Map of team name the location (Vector2) the flag must be taken to score
        """
        self.botSpawnAreas = {}
        """
        Map of team name the extents (Vector2, Vector2) of each team's bot spawn area
        """

        self.characterRadius = 0.0
        """
        The radius of the character
        """
        self.fieldOfViewAngles = []
        """
        The visibility angles of the bots in each of the different bot states. See BotInfo for the states
        """
        self.firingDistance = 0.0
        """
        The maximum firing distance of the bots
        """
        self.walkingSpeed = 0.0
        """
        The walking speed of the bots
        """
        self.runningSpeed = 0.0
        """
        The running speed of the bots
        """

        self.gameLength = 0.0
        """
        The length (seconds) of the game.
        """

        self.initializationTime = 0.0
        """
        The time (seconds) allowed for bot initialization before the start of the game.
        """

        self.respawnTime = 0.0
        """
        The time (seconds) between bot respawns.
        """


    def clamp(self, x, minValue, maxValue):
        return max(minValue, min(x, maxValue))

    def findRandomFreePositionInBox(self, area):
        """
        Find a random position for a character to move to in an area.
        None is returned if no position could be found.
        """
        minX, minY = self.clamp(area[0].x, 0, self.width-1), self.clamp(area[0].y, 0, self.height-1)
        maxX, maxY = self.clamp(area[1].x, 0, self.width-1), self.clamp(area[1].y, 0, self.height-1)
        rangeX, rangeY = maxX - minX, maxY - minY

        if (rangeX == 0.0) or (rangeY == 0.0):
            return None

        # pad the radius a little to ensure that the point is okay even after floating point errors
        # introduced by sending this value across the network to the game server
        radius = self.characterRadius + 0.01

        for i in range(0, 100):
            x, y = random.random() * rangeX + minX, random.random() * rangeY + minY
            ix, iy = int(x), int(y)
            # check if there are any blocks under current position
            if self.blockHeights[ix][iy] > 0:
                continue
            # check if there are any blocks in the four cardinal directions
            if (x - ix) < radius and ix > 0 and self.blockHeights[ix-1][iy] > 0:
                continue
            if (ix + 1 - x) < radius and ix < self.width - 1 and self.blockHeights[ix+1][iy] > 0:
                continue
            if (y - iy) < radius and iy > 0 and self.blockHeights[ix][iy-1] > 0:
                continue
            if (iy + 1 - y) < radius and iy < self.height - 1 and self.blockHeights[ix][iy+1] > 0:
                continue
            # check if there are any blocks in the four diagonals
            if (x - ix) < radius and (y - iy) < radius and ix > 0 and iy > 0 and self.blockHeights[ix-1][iy-1] > 0:
                continue
            if (ix + 1 - x) < radius and (y - iy) < radius and ix < self.width - 1 and iy > 0 and self.blockHeights[ix+1][iy-1] > 0:
                continue
            if (x - ix) < radius and (iy + 1 - y) < radius and ix > 0 and iy < self.height - 1 and self.blockHeights[ix-1][iy+1] > 0:
                continue
            if (ix + 1 - x) < radius and (iy + 1 - y) < radius and ix < self.width - 1 and iy < self.height - 1 and self.blockHeights[ix+1][iy+1] > 0:
                continue
            return Vector2(x, y)
        return None

    def findNearestFreePosition(self, target):
        """
        Find a free position near 'target' for a character to move to.
        None is returned if no position could be found.
        """
        for r in range(1, 100):
            areaMin = Vector2(target.x - r, target.y - r)
            areaMax = Vector2(target.x + r, target.y + r)
            position = self.findRandomFreePositionInBox((areaMin, areaMax))
            if position:
                return position
        return None

    @property
    def area(self):
        """
        Return the full area of the world.
        This can be used with findRandomFreePositionInBox to find a random position in the world.
        eg levelInfo.findRandomFreePositionInBox(levelInfo.area)
        """
        return (Vector2.ZERO, Vector2(self.width, self.height))


    @classmethod
    def createFromWorldBuilder(cls, world, worldBuilder, levelConfig):
        levelInfo = LevelInfo()

        worldBounds = world.getBounds()
        extents = worldBounds.getMaximum()
        levelInfo.width, levelInfo.height = int(extents.x), int(extents.z)
        levelInfo.blockHeights = [ [worldBuilder.getAltitude(x,y) for y in xrange(levelInfo.height)] for x in xrange(levelInfo.width)]

        levelInfo.teamNames = levelConfig.teamConfigs.keys()
        levelInfo.flagSpawnLocations = {}
        levelInfo.flagScoreLocations = {}
        levelInfo.botSpawnAreas = {}
        for (teamName, teamConfig) in levelConfig.teamConfigs.items():
            # print teamName, " flag:", teamConfig.flagSpawnLocation.x, teamConfig.flagSpawnLocation.y, " score:", teamConfig.flagScoreLocation.x, teamConfig.flagScoreLocation
            levelInfo.flagSpawnLocations[teamName] = teamConfig.flagSpawnLocation
            levelInfo.flagScoreLocations[teamName] = teamConfig.flagScoreLocation
            levelInfo.botSpawnAreas[teamName] = teamConfig.botSpawnArea

        return levelInfo



class GameInfo(object):
    """
    All of the filtered read-only information about the current game state.
    This shouldn't be modified. Modifying it will only hurt yourself.
    Updated each frame to show the current known information about the world.
    """


    def __init__(self):
        super(GameInfo, self).__init__()

        self.match = None
        """
        The MatchInfo object describing the current match
        """
        self.teams = {}
        """
        The dictionary containing the TeamInfo object for each team indexed by team name
        """
        self.team = None
        """
        The TeamInfo object describing your team
        """
        self.enemyTeam = None
        """
        The TeamInfo object describing the enemy team
        """
        self.bots = {}
        """
        The dictionary containing the BotInfo object for each bot indexed by bot name
        """
        self.flags = {}
        """
        The dictionary containing the FlagInfo object for each flag indexed by flag name
        """

    @property
    def bots_alive(self):
        """
        The list of all bots in this team that are currently alive.
        """
        return [b for b in self.team.members if b.health > 0]

    @property
    def bots_available(self):
        """
        The list of all bots in this team that are currently alive and not doing an action.
        """
        return [b for b in self.bots_alive if b.state == BotInfo.STATE_IDLE]

    @property
    def bots_holding(self):
        """
        The list of the attacking bots in this team that are deadlocked by defenders.
        """
        return [b for b in self.bots_alive if b.state == BotInfo.STATE_HOLDING]

    @property
    def enemyFlags(self):
        """
        Returns a list of FlagInfo objects for all enemy flags. Set up to support more than one enemy team
        """
        return [f for f in self.flags.values() if f.team != self.team]

    def addTeam(self, team):
        self.teams[team.name] = team
        for bot in team.members:
            self.bots[bot.name] = bot
        self.flags[team.flag.name] = team.flag


class TeamInfo(object):
    """
    Information about the current team including ids of all of the members of the team
    """

    def __init__(self, name):
        super(TeamInfo, self).__init__()

        self.name = name
        """
        The name of the team
        """
        self.members = []
        """
        A list of the BotInfo objects for each member of the team
        """
        self.flag = None
        """
        The FlagInfo object for this team's flag.
        """
        self.flagScoreLocation = None
        """
        The position (Vector2) where the team must return an enemy flag to score a point.
        """
        self.flagSpawnLocation = None
        """
        The position (Vector2) where this team's flag is spawned.
        """
        self.botSpawnArea = (Vector2.ZERO, Vector2.ZERO)
        """
        The (min, max) extents (Vector2, Vector2) of each team's bot spawn area
        """

    def __repr__(self):
        return "TeamInfo(name='{}')".format(self.name)


class FlagInfo(object):
    """
    Information about each of the flags.
    The positions of all flags are always known.
    If a flag is being carried the carrier is always known
    """

    def __init__(self, name):
        super(FlagInfo, self).__init__()

        self.name = name
        """
        name                The name of the flag
        """
        self.team = None
        """
        team                The team that owns this flag.
        """
        self.position = Vector2.ZERO
        """
        position            The current position of the flag (always known)
        """
        self.carrier = None
        """
        carrier             The BotInfo object for the bot that is currently carrying the flag (None if it is not being carried)
        """
        self.respawnTimer = 0
        """
        respawnTimer        Time in seconds until a dropped flag is respawned at its spawn location
        """

    def __repr__(self):
        return "FlagInfo(name='{}')".format(self.name)


class BotInfo(object):
    """
    Information that you know about each of the bots.
    Enemy bots will contain information about the last time they were seen.
    Friendly bots will contain full information.
    """

    STATE_UNKNOWN   =  0
    """
    The current state of the bot is unknown. This state should never be seen by commanders.
    """
    STATE_IDLE      =  1
    """
    The bot is not currently doing any actions. Auto-targeting is disabled.
    """
    STATE_DEFENDING =  2
    """
    The bot is defending. Auto-targeting is enabled.
    """
    STATE_MOVING    =  3
    """
    The bot is moving. Auto-targeting is disabled.
    """
    STATE_ATTACKING =  4
    """
    The bot is attacking. Auto-targeting is enabled.
    """
    STATE_CHARGING  =  5
    """
    The bot is charging. Auto-targeting is enabled.
    """
    STATE_SHOOTING  =  6
    """
    The bot is shooting.
    """
    STATE_TAKINGORDERS = 7
    """
    The bot is in a cooldown period after receiving an order. Auto-targeting is disabled.
    """
    STATE_HOLDING   =  8
    """
    The bot was in an attacking state but its movement is blocked by the firing arc of an enemy. It is holding position just outside the firing arc. Auto-targeting is enabled.
    """
    STATE_DEAD      =  9
    """
    The bot is dead.
    """

    def __init__(self, name):
        super(BotInfo, self).__init__()

        """
        The name of this bot
        """
        self.name = name
        """
        The name of this bot
        """
        self.team = None
        """
        The TeamInfo for the team that owns this bot
        """
        self.seenlast = None
        """
        The time (seconds) since this bot was last seen. For friendly bots this is always 0.
        """
        self.health = None
        """
        The health of the bot. This is always known for friendly bots.
        For enemy bots this is the current state if the bot is dead or is visible by this commander. Otherwise, this is the last known health value.
        """
        self.state = BotInfo.STATE_UNKNOWN
        """
        The state/action of the bot. The possible states are: `STATE_UNKNOWN`, `STATE_IDLE`, `STATE_DEFENDING`, `STATE_MOVING`, `STATE_ATTACKING`, `STATE_CHARGING`, `STATE_SHOOTING`, `TAKING_ORDERS`, `STATE_HOLDING`, `STATE_DEAD`
        This is always known for friendly bots.
        For enemy bots this is the current state if the bot is dead or is visible by this commander. Otherwise, this is the last known state.
        """
        self.position = None
        """
        The last known position (Vector2) of the bot.
        This is always known for friendly bots.
        For enemy bots this is the current state if the bot is dead or is visible by this commander. Otherwise, this is the last known position.
        """
        self.facingDirection = None
        """
        The last known facing direction (Vector2) of the bot.
        This is always known for friendly bots.
        For enemy bots this is the current state if the bot is dead or is visible by this commander. Otherwise, this is the last known facing direction.
        """
        self.flag = None
        """
        The flag being carried by the bot, None if no flag is carried. This is always known for both friendly and enemy bots.
        """
        self.visibleEnemies = []
        """
        List of BotInfo objects for enemies which are visible to this bot.
        For friendly bots the list will only include enemy bots which are visible by this commander.
        For enemy bots which are not visible by this commander, this will be an empty list.
        """
        self.seenBy = []
        """
        List of BotInfo objects for enemies which are visible by the team and can see this bot
        For friendly bots the list will only include enemy bots which are visible by this commander.
        For enemy bots which are not visible by this commander, this will be an empty list.
        """

    def __repr__(self):
        return "BotInfo(name='{}')".format(self.name)


class MatchInfo(object):
    """
    Information about the current match.
    """

    def __init__(self):
        super(MatchInfo, self).__init__()

        self.scores = {}
        """
        A dictionary of team name to score
        """
        self.timeRemaining = 0.0
        """
        Time in seconds until this match ends
        """
        self.timeToNextRespawn = 0.0
        """
        Time in seconds until the next bot respawn cycle
        """
        self.timePassed = 0.0
        """
        Time in seconds since the beginning of this match
        """
        self.combatEvents = []
        """
        List of combat events that have occurred during this match.
        """


class MatchCombatEvent(object):
    """
    Information about a particular game event.
    """

    TYPE_NONE = 0
    TYPE_KILLED = 1
    TYPE_FLAG_PICKEDUP = 2
    TYPE_FLAG_DROPPED = 3
    TYPE_FLAG_CAPTURED = 4
    TYPE_FLAG_RESTORED = 5
    TYPE_RESPAWN = 6

    def __init__(self, type, subject, instigator, time):
        super(MatchCombatEvent, self).__init__()

        self.type = type
        """
        The type of event (`TYPE_NONE`, `TYPE_KILLED`, `TYPE_FLAG_PICKEDUP`, `TYPE_FLAG_DROPPED`, `TYPE_FLAG_CAPTURED`, `TYPE_FLAG_RESTORED`, `TYPE_RESPAWN`)
        """
        self.subject = subject
        """
        The FlagInfo/BotInfo object of the flag/bot that this event is about
        """
        self.instigator = instigator
        """
        The BotInfo object of the bot which instigated this event
        """
        self.time = time
        """
        Time in seconds since the beginning of this match that this event occurred.
        """



def toJSON(python_object):
    if isinstance(python_object, Vector2):
        v = python_object
        return [v.x, v.y]

    if isinstance(python_object, LevelInfo):
        level = python_object
        return {'__class__': 'LevelInfo',
                '__value__': { 'width': level.width, 'height': level.height, 'blockHeights': level.blockHeights, 'teamNames': level.teamNames,
                               'flagSpawnLocations': level.flagSpawnLocations, 'flagScoreLocations': level.flagScoreLocations, 'botSpawnAreas': level.botSpawnAreas,
                               'characterRadius': level.characterRadius, 'fieldOfViewAngles': level.fieldOfViewAngles, 'firingDistance': level.firingDistance,
                               'walkingSpeed': level.walkingSpeed, 'runningSpeed': level.runningSpeed,
                               'gameLength': level.gameLength, 'initializationTime': level.initializationTime , 'respawnTime': level.respawnTime }}

    if isinstance(python_object, GameInfo):
        game = python_object
        return {'__class__': 'GameInfo',
                '__value__': { 'match': game.match, 'team': game.team.name, 'enemyTeam': game.enemyTeam.name,
                               'teams': game.teams, 'flags': game.flags , 'bots': game.bots }}

    if isinstance(python_object, TeamInfo):
        team = python_object
        members = [b.name for b in team.members]
        return {'__class__': 'TeamInfo',
                '__value__': { 'name': team.name, 'members': members, 'flag': team.flag.name,
                               'flagScoreLocation': team.flagScoreLocation, 'flagSpawnLocation': team.flagSpawnLocation, 'botSpawnArea': team.botSpawnArea }}

    if isinstance(python_object, FlagInfo):
        flag = python_object
        carrierName = flag.carrier.name if flag.carrier else None
        return {'__class__': 'FlagInfo',
                '__value__': { 'name': flag.name, 'position': flag.position, 'team': flag.team.name, 'carrier': carrierName, 'respawnTimer': flag.respawnTimer }}

    if isinstance(python_object, BotInfo):
        bot = python_object
        flag = bot.flag.name if bot.flag else None
        visibleEnemies = [b.name for b in bot.visibleEnemies]
        seenBy = [b.name for b in bot.seenBy]
        return {'__class__': 'BotInfo',
                '__value__': { 'name': bot.name, 'team': bot.team.name, 'health': bot.health, 'state': bot.state,
                               'position': bot.position, 'facingDirection': bot.facingDirection , 'seenlast': bot.seenlast,
                               'flag': flag, 'visibleEnemies': visibleEnemies, 'seenBy': seenBy }}

    if isinstance(python_object, MatchInfo):
        match = python_object
        return {'__class__': 'MatchInfo',
                '__value__': { 'scores': match.scores, 'timeRemaining': match.timeRemaining, 'timeToNextRespawn': match.timeToNextRespawn, 'timePassed': match.timePassed, 'combatEvents': match.combatEvents }}

    if isinstance(python_object, MatchCombatEvent):
        combatEvent = python_object
        instigatorName = combatEvent.instigator.name if combatEvent.instigator else None
        return {'__class__': 'MatchCombatEvent',
                '__value__': { 'type': combatEvent.type, 'subject': combatEvent.subject.name, 'instigator': instigatorName, 'time': combatEvent.time }}

    raise TypeError(repr(python_object) + ' is not JSON serializable')


def toVector2(list):
    if not list:
        return None
    assert len(list) == 2
    return Vector2(list[0], list[1])


def fromJSON(dct):
    if '__class__' in dct:
        if dct['__class__'] == 'LevelInfo':
            value = dct['__value__']
            level = LevelInfo()
            level.width = value['width']
            level.height = value['height']
            level.blockHeights = value['blockHeights']
            level.teamNames = [name.encode('utf-8') for name in value['teamNames']]
            level.flagSpawnLocations = {}
            for teamName, flagSpawnLocation in value['flagSpawnLocations'].items():
                level.flagSpawnLocations[teamName.encode('utf-8')] = toVector2(flagSpawnLocation)
            level.flagScoreLocations = {}
            for teamName, flagScoreLocation in value['flagScoreLocations'].items():
                level.flagScoreLocations[teamName.encode('utf-8')] = toVector2(flagScoreLocation)
            level.botSpawnAreas = {}
            for teamName, teamSpawnArea in value['botSpawnAreas'].items():
                level.botSpawnAreas[teamName.encode('utf-8')] = (toVector2(teamSpawnArea[0]), toVector2(teamSpawnArea[1]))
            level.characterRadius = value['characterRadius']
            level.fieldOfViewAngles = value['fieldOfViewAngles']
            level.firingDistance = value['firingDistance']
            level.walkingSpeed = value['walkingSpeed']
            level.runningSpeed = value['runningSpeed']
            level.gameLength = value['gameLength']
            level.initializationTime = value['initializationTime']
            level.respawnTime = value['respawnTime']
            return level

        if dct['__class__'] == 'GameInfo':
            value = dct['__value__']
            game = GameInfo()
            game.match = value['match']
            game.teams = {}
            for name, team in value['teams'].items():
                game.teams[name.encode('utf-8')] = team
            game.team = value['team'] # needs fixup
            game.enemyTeam = value['enemyTeam'] # needs fixup
            game.bots = {}
            for name, bot in value['bots'].items():
                game.bots[name.encode('utf-8')] = bot
            game.flags = {}
            for name, flag in value['flags'].items():
                game.flags[name.encode('utf-8')] = flag
            return game

        if dct['__class__'] == 'TeamInfo':
            value = dct['__value__']
            team = TeamInfo(value['name'].encode('utf-8'))
            team.members = value['members'] # needs fixup
            team.flag = value['flag'] # needs fixup
            team.flagScoreLocation = toVector2(value['flagScoreLocation'])
            team.flagSpawnLocation = toVector2(value['flagSpawnLocation'])
            team.botSpawnArea = (toVector2(value['botSpawnArea'][0]), toVector2(value['botSpawnArea'][1]))
            return team

        if dct['__class__'] == 'FlagInfo':
            value = dct['__value__']
            flag = FlagInfo(value['name'].encode('utf-8'))
            flag.team = value['team'] # needs fixup
            flag.position = toVector2(value['position'])
            flag.carrier = value['carrier'] if value['carrier'] else None # needs fixup
            flag.respawnTimer = value['respawnTimer']
            return flag


        if dct['__class__'] == 'BotInfo':
            value = dct['__value__']
            bot = BotInfo(value['name'].encode('utf-8'))
            bot.team = value['team'] # needs fixup
            bot.health = value['health']
            bot.state = value['state']
            bot.position = toVector2(value['position']) if value['position'] else None
            bot.facingDirection = toVector2(value['facingDirection']) if value['facingDirection'] else None
            bot.seenlast = value['seenlast'] if value['seenlast'] else None
            bot.flag = value['flag'] if value['flag'] else None # needs fixup
            bot.visibleEnemies = value['visibleEnemies'] # needs fixup
            bot.seenBy = value['seenBy'] # needs fixup
            return bot

        if dct['__class__'] == 'MatchInfo':
            value = dct['__value__']
            match = MatchInfo()
            match.scores = {}
            for teamName, score in value['scores'].items():
                match.scores[teamName.encode('utf-8')] = score
            match.timeRemaining = value['timeRemaining']
            match.timeToNextRespawn = value['timeToNextRespawn']
            match.timePassed = value['timePassed']
            match.combatEvents = value['combatEvents'] # TODO: check this deserialization
            return match

        if dct['__class__'] == 'MatchCombatEvent':
            value = dct['__value__']
            combatEvent = MatchCombatEvent(value['type'], value['subject'], value['instigator'], value['time']) # subject and instigator needs fixup
            return combatEvent

    return dct



def fixupReferences(obj, game):
    for name, bot in game.bots.items():
        assert bot is not None

    if isinstance(obj, LevelInfo):
        pass

    elif isinstance(obj, GameInfo):
        new_game = obj
        # game and new_game should be the same in production code
        # but they may differ in unittests
        new_game.team = game.teams[new_game.team]
        new_game.enemyTeam = game.teams[new_game.enemyTeam]
        for b in new_game.bots.values():
            fixupReferences(b, game)
        for t in new_game.teams.values():
            fixupReferences(t, game)
        for f in new_game.flags.values():
            fixupReferences(f, game)
        fixupReferences(new_game.match, game)

    elif isinstance(obj, TeamInfo):
        team = obj
        team.members = [game.bots[b] for b in team.members]
        team.flag = game.flags[team.flag]

    elif isinstance(obj, FlagInfo):
        flag = obj
        flag.team = game.teams[flag.team]
        flag.carrier = game.bots[flag.carrier] if flag.carrier else None

    elif isinstance(obj, BotInfo):
        bot = obj
        bot.team = game.teams[bot.team]
        bot.flag = game.flags[bot.flag] if bot.flag else None
        bot.visibleEnemies = [game.bots[b] for b in bot.visibleEnemies]
        bot.seenBy = [game.bots[b] for b in bot.seenBy]

    elif isinstance(obj, MatchInfo):
        match = obj
        for e in match.combatEvents:
            fixupReferences(e, game)

    elif isinstance(obj, MatchCombatEvent):
        combatEvent = obj
        if combatEvent.type == MatchCombatEvent.TYPE_KILLED:
            combatEvent.instigator = game.bots[combatEvent.instigator]
            combatEvent.subject = game.bots[combatEvent.subject]
            assert combatEvent.subject is not None
            assert combatEvent.instigator is not None
        elif combatEvent.type == MatchCombatEvent.TYPE_FLAG_PICKEDUP:
            combatEvent.instigator = game.bots[combatEvent.instigator]
            combatEvent.subject = game.flags[combatEvent.subject]
            assert combatEvent.subject is not None
            assert combatEvent.instigator is not None
        elif combatEvent.type == MatchCombatEvent.TYPE_FLAG_DROPPED:
            combatEvent.instigator = game.bots[combatEvent.instigator]
            combatEvent.subject = game.flags[combatEvent.subject]
            assert combatEvent.subject is not None
            assert combatEvent.instigator is not None
        elif combatEvent.type == MatchCombatEvent.TYPE_FLAG_CAPTURED:
            combatEvent.instigator = game.bots[combatEvent.instigator]
            combatEvent.subject = game.flags[combatEvent.subject]
            assert combatEvent.subject is not None
            assert combatEvent.instigator is not None
        elif combatEvent.type == MatchCombatEvent.TYPE_FLAG_RESTORED:
            assert combatEvent.instigator is None
            combatEvent.subject = game.flags[combatEvent.subject]
            assert combatEvent.subject is not None
        elif combatEvent.type == MatchCombatEvent.TYPE_RESPAWN:
            assert combatEvent.instigator is None
            combatEvent.subject = game.bots[combatEvent.subject]
            assert combatEvent.subject is not None
        else:
            assert False, "Unknown event type"

def fixupGameInfoReferences(obj):
    fixupReferences(obj, obj)

def mergeFlagInfo(gameInfo, newFlagInfo):
    flagInfo = gameInfo.flags[newFlagInfo.name]
    flagInfo.team         = newFlagInfo.team
    flagInfo.position     = newFlagInfo.position
    flagInfo.carrier      = newFlagInfo.carrier
    flagInfo.respawnTimer = newFlagInfo.respawnTimer
    fixupReferences(flagInfo, gameInfo)

def mergeBotInfo(gameInfo, newBotInfo):
    botInfo = gameInfo.bots[newBotInfo.name]
    botInfo.team            = newBotInfo.team
    botInfo.health          = newBotInfo.health
    botInfo.state           = newBotInfo.state
    botInfo.position        = newBotInfo.position
    botInfo.facingDirection = newBotInfo.facingDirection
    botInfo.seenlast        = newBotInfo.seenlast
    botInfo.flag            = newBotInfo.flag
    botInfo.visibleEnemies  = newBotInfo.visibleEnemies
    botInfo.seenBy          = newBotInfo.seenBy
    fixupReferences(botInfo, gameInfo)

def mergeMatchInfo(gameInfo, newMatchInfo):
    matchInfo = gameInfo.match
    matchInfo.scores            = newMatchInfo.scores
    matchInfo.timeRemaining     = newMatchInfo.timeRemaining
    matchInfo.timeToNextRespawn = newMatchInfo.timeToNextRespawn
    matchInfo.timePassed        = newMatchInfo.timePassed
    fixupReferences(newMatchInfo, gameInfo)
    matchInfo.combatEvents.extend(newMatchInfo.combatEvents)

def mergeGameInfo(gameInfo, newGameInfo):
    for newFlag in newGameInfo.flags.values():
        mergeFlagInfo(gameInfo, newFlag)

    for newBot in newGameInfo.bots.values():
        mergeBotInfo(gameInfo, newBot)

    mergeMatchInfo(gameInfo, newGameInfo.match)


