from api import Vector2

class Defend(object):
    """
    Commands a bot to defend its current position.
    """

    def __init__(self, botId, facingDirection = None, description = ''):
        super(Defend, self).__init__()
        assert isinstance(botId, str)
        assert (facingDirection == None) or isinstance(facingDirection, Vector2) or (isinstance(facingDirection, list) and len(facingDirection) > 0)

        self.botId = botId
        """
        The name of the bot
        """

        if facingDirection:
            # convert the facingDirection into a list of (Vector2, time) pairs
            if isinstance(facingDirection, Vector2):
                facingDirection = [(facingDirection, 0.0)]
            else:
                # if it is already a list check the type
                for i,f in enumerate(facingDirection):
                    if isinstance(f, Vector2):
                        facingDirection[i] = (f, 0)
                    else:
                        # check the type is a type of Vector2, float?
                        pass

        self.facingDirection = facingDirection
        """
        The desired facing direction(s) of the bot.
        This parameter can be given in three forms:
        If facingDirection is None then the bot will remain facing in its current facing direction.
        If facingDirection is a Vector2 then the bot will turn to face the requested facing direction.
        If facingDirection is a list of (Vector2, float) pairs then the list is a series of directions in which the bot
        will look. For each element of the list the bot will face in that direction for the amount of time specified by
        the second element of the pair (with a minimum time of 1 second). Once the bot has been through all of the elements
        of the list it will continue iterating again from the beginning of the list.

        """
        self.description = description
        """
        A description of the intention of the bot. This is displayed automatically if the commander sets self.verbose = True
        """

    def __str__(self):
        return "Defend {} facingDirection={} {}".format(self.botId, self.facingDirection, self.description)

class Move(object):
    """
    Commands a bot to run to a specified position without attacking visible enemies.
    """

    def __init__(self, botId, target, description = ''):
        super(Move, self).__init__()
        if isinstance(target, Vector2):
            target = [target];
        assert isinstance(botId, str)
        assert isinstance(target, list) and len(target) > 0
        for t in target: assert isinstance(t, Vector2)

        self.botId = botId
        """
        The name of the bot
        """
        self.target = target
        """
        The target destination (Vector2) or list of destination waypoints ([Vector2])
        """
        self.description = description
        """
        A description of the intention of the bot. This is displayed automatically if the commander sets self.verbose = True
        """

    def __str__(self):
        return "Move {} target={} {}".format(self.botId, self.target, self.description)


class Attack(object):
    """
    Commands a bot to attack a specified position. If an enemy bot is seen by this bot, it will be attacked.
    """

    def __init__(self, botId, target, lookAt = None, description = ''):
        super(Attack, self).__init__()
        if isinstance(target, Vector2):
            target = [target];
        assert isinstance(botId, str)
        assert isinstance(target, list) and len(target) > 0
        for t in target: assert isinstance(t, Vector2)
        assert lookAt == None or isinstance(lookAt, Vector2)
        self.botId = botId 
        """
        The name of the bot
        """
        self.target = target
        """
        The target destination (Vector2) or list of destination waypoints ([Vector2])
        """
        self.lookAt = lookAt
        """
        An optional position (Vector2) which the bot should look at while moving
        """
        self.description = description
        """
        A description of the intention of the bot. This is displayed automatically if the commander sets self.verbose = True
        """

    def __str__(self):
        return "Attack {} target={} lookAt={} {}".format(self.botId, self.target, self.lookAt, self.description)


class Charge(object):
    """
    Commands a bot to attack a specified position at a running pace. This is faster than Attack but incurs an additional firing delay penalty.
    """

    def __init__(self, botId, target, description = ''):
        super(Charge, self).__init__()
        if isinstance(target, Vector2):
            target = [target];
        assert isinstance(botId, str)
        assert isinstance(target, list) and len(target) > 0
        for t in target: assert isinstance(t, Vector2)

        self.botId = botId 
        """
        The name of the bot
        """
        self.target = target
        """
        The target destination (Vector2) or list of destination waypoints ([Vector2])
        """
        self.description = description
        """
        A description of the intention of the bot. This is displayed automatically if the commander sets self.verbose = True
        """

    def __str__(self):
        return "Charge {} target={} {}".format(self.botId, self.target, self.description)


def toJSON(python_object):
    if isinstance(python_object, Vector2):
        v = python_object
        return [v.x, v.y]

    if isinstance(python_object, Defend):
        command = python_object
        return {'__class__': 'Defend',
                '__value__': { 'bot': command.botId, 'facingDirections': command.facingDirection, 'description': command.description }}   

    if isinstance(python_object, Move):
        command = python_object
        return {'__class__': 'Move',
                '__value__': { 'bot': command.botId, 'target': command.target, 'description': command.description }}   

    if isinstance(python_object, Attack):
        command = python_object
        return {'__class__': 'Attack',
                '__value__': { 'bot': command.botId, 'target': command.target, 'lookAt': command.lookAt, 'description': command.description }}   

    if isinstance(python_object, Charge):
        command = python_object
        return {'__class__': 'Charge',
                '__value__': { 'bot': command.botId, 'target': command.target, 'description': command.description }}   

    raise TypeError(repr(python_object) + ' is not JSON serializable')

def toVector2List(list):
    result = []
    for v in list:
        result.append(toVector2(v))
    return result

def toPairVector2FloatList(list):
    result = []
    for v, f in list:
        result.append((toVector2(v), f))
    return result

def toVector2(list):
    if not list:
        return None
    assert len(list) == 2
    return Vector2(list[0], list[1])


def fromJSON(dct):
    if '__class__' in dct:
        if dct['__class__'] == 'Defend':
            value = dct['__value__']
            facingDirections = toPairVector2FloatList(value['facingDirections']) if value['facingDirections'] else None
            return Defend(value['bot'].encode('utf-8'), facingDirections, description = value['description'].encode('utf-8'))

        if dct['__class__'] == 'Move':
            value = dct['__value__']
            target = toVector2List(value['target'])
            return Move(value['bot'].encode('utf-8'), target, description = value['description'].encode('utf-8'))

        if dct['__class__'] == 'Attack':
            value = dct['__value__']
            target = toVector2List(value['target'])
            lookAt = toVector2(value['lookAt']) if value['lookAt'] else None
            return Attack(value['bot'].encode('utf-8'), target, lookAt = lookAt, description = value['description'].encode('utf-8'))

        if dct['__class__'] == 'Charge':
            value = dct['__value__']
            target = toVector2List(value['target'])
            return Charge(value['bot'].encode('utf-8'), target, description = value['description'].encode('utf-8'))

    return dct
