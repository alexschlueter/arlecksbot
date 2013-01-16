import random
import os

from api import gameinfo
from api import Commander
from api import commands
from api.vector2 import Vector2

def contains(area, position):
    start, finish = area
    return position.x >= start.x and position.y >= start.y and position.x <= finish.x and position.y <= finish.y


class RandomCommander(Commander):
    """
    Sends everyone to randomized positions or a random choice of flag location.  The behavior of returning the flag
    to the home base after capturing it is purely emergent!
    """

    def tick(self):
        """Process all the bots that are done with their orders and available for taking commands."""

        # The 'bots_available' list is a dynamically calculated list of bots that are done with their commands.
        for bot in self.game.bots_available:
            # Determine a place to run randomly...
            target = random.choice(
                          # 1) Either a random choice of *current* flag locations, ours or theirs.
                          [f.position for f in self.game.flags.values()]
                          # 2) Or a random choice of the goal locations for returning flags.
                        + [s for s in self.level.flagScoreLocations.values()]
                          # 3) Or a random position in the entire level, one that's not blocked.
                        + [self.level.findRandomFreePositionInBox(self.level.area)]
            )
            # Pick random movement style between going fast or moving carefully.
            cmd = random.choice([commands.Attack, commands.Charge])
            if target:
                self.issue(cmd, bot, target, description = 'random')


        # These bots were given an Attack order, but encountered defensive resistance and are waiting...
        for bot in self.game.bots_holding:
            cmd = random.choice([commands.Attack, commands.Charge, None])
            params = {'description': 'random (after holding)'}

            # If attacking, pick an enemy and strafe around a bit to break the holding pattern. 
            if cmd == commands.Attack:
                params['lookAt'] = random.choice([b.position for b in bot.visibleEnemies])
                target = self.level.findRandomFreePositionInBox((bot.position-5.0, bot.position+5.0))

            # Can also charge one of the visible enemies to try to break the pattern...
            elif cmd == commands.Charge:
                target = random.choice([b.position for b in bot.visibleEnemies])

            if cmd:
                self.issue(cmd, bot, target, **params)


class GreedyCommander(Commander):
    """
    Always sends everyone to the flag of the enemy and the guy carrying the flag back again
    """

    def initialize(self):
        self.verbose = False

    def captured(self):
        """Did this team cature the enemy flag?"""
        return self.game.enemyTeam.flag.carrier != None

    def tick(self):
        """Process the bots that are waiting for orders, either send them all to attack or all to defend."""
        captured = self.captured()

        our_flag = self.game.team.flag.position
        their_flag = self.game.enemyTeam.flag.position
        their_base = self.level.botSpawnAreas[self.game.enemyTeam.name][0]

        # First process bots that are done with their orders...
        for bot in self.game.bots_available:

            # If this team has captured the flag, then tell this bot...
            if captured:
                target = self.game.team.flagScoreLocation
                # 1) Either run home, if this bot is the carrier or otherwise randomly.
                if bot.flag is not None or (random.choice([True, False]) and (target - bot.position).length() > 8.0):
                    self.issue(commands.Charge, bot, target, description = 'scrambling home')
                # 2) Run to the exact flag location, effectively escorting the carrier.
                else:
                    self.issue(commands.Attack, bot, self.game.enemyTeam.flag.position, description = 'defending flag carrier',
                               lookAt = random.choice([their_flag, our_flag, their_flag, their_base]))

            # In this case, the flag has not been captured yet so have this bot attack it!
            else:
                path = [self.game.enemyTeam.flag.position]
                if contains(self.level.botSpawnAreas[self.game.team.name], bot.position) and random.choice([True, False]):
                    path.insert(0, self.game.team.flagScoreLocation)
                self.issue(commands.Attack, bot, path, description = 'attacking enemy flag',
                                lookAt = random.choice([their_flag, our_flag, their_flag, their_base]))

        # Second process bots that are in a holding attack pattern.
        holding = len(self.game.bots_holding)
        for bot in self.game.bots_holding:
            if holding > 1:
                self.issue(commands.Charge, bot, random.choice([b.position for b in bot.visibleEnemies]))
            else:
                target = self.level.findRandomFreePositionInBox((bot.position-5.0, bot.position+5.0))
                self.issue(commands.Attack, bot, target, lookAt = random.choice([b.position for b in bot.visibleEnemies]))


class DefenderCommander(Commander):
    """
    Leaves everyone to defend the flag except for one lone guy to grab the other team's flag.
    """

    def initialize(self):
        self.attacker = None
        self.verbose = False

    def tick(self):
        if self.attacker and self.attacker.health <= 0:
            self.attacker = None

        for bot in self.game.bots_available:
            if (not self.attacker or self.attacker == bot or bot.flag) and len(self.game.bots_alive) > 1:
                self.attacker = bot

                if bot.flag:
                    # Return the flag home relatively quickly!
                    targetLocation = self.game.team.flagScoreLocation
                    self.issue(commands.Charge, bot, targetLocation, description = 'returning enemy flag!')

                else:
                    # Find the enemy team's flag position and run to that.
                    enemyFlagLocation = self.game.enemyTeam.flag.position
                    self.issue(commands.Charge, bot, enemyFlagLocation, description = 'getting enemy flag!')

            else:
                if self.attacker == bot:
                    self.attacker = None

                # defend the flag!
                targetPosition = self.game.team.flag.position
                targetMin = targetPosition - Vector2(8.0, 8.0)
                targetMax = targetPosition + Vector2(8.0, 8.0)

                if (targetPosition - bot.position).length() > 9.0 and  (targetPosition - bot.position).length() > 3.0 :
                    while True:
                        position = self.level.findRandomFreePositionInBox((targetMin,targetMax))
                        if position and (targetPosition - position).length() > 3.0:
                            self.issue(commands.Charge, bot, position, description = 'defending around flag')
                            break
                else:
                    their_flag = self.game.enemyTeam.flag.position
                    their_base = self.level.botSpawnAreas[self.game.enemyTeam.name][0]
                    their_score = self.game.enemyTeam.flagScoreLocation
                    self.issue(commands.Defend, bot, [(p-bot.position, t) for p, t in [(targetPosition, 5.0), (their_flag, 2.5), (their_base, 2.5), (their_score, 2.5)]], description = 'defending by scanning')


class BalancedCommander(Commander):
    """An example commander that has one bot attacking, one defending and the rest randomly searching the level for enemies"""

    def initialize(self):
        self.attacker = None
        self.defender = None
        self.verbose = False

        # Calculate flag positions and store the middle.
        ours = self.game.team.flag.position
        theirs = self.game.enemyTeam.flag.position
        self.middle = (theirs + ours) / 2.0

        # Now figure out the flaking directions, assumed perpendicular.
        d = (ours - theirs)
        self.left = Vector2(-d.y, d.x).normalized()
        self.right = Vector2(d.y, -d.x).normalized()
        self.front = Vector2(d.x, d.y).normalized()

        self.panicMode = False

    # Add the tick function, called each update
    # This is where you can do any logic and issue new orders.
    def tick(self):
        if self.attacker and self.attacker.health <= 0:
            # the attacker is dead we'll pick another when available
            self.attacker = None

        if self.defender and (self.defender.health <= 0 or self.defender.flag):
            # the defender is dead we'll pick another when available
            self.defender = None

        if not self.game.team.flag.carrier:
            self.panicMode = False
        else:
            if not self.panicMode:
                self.panicMode = True
                
                targetPosition = (self.game.team.flag.position + self.game.enemyTeam.flagScoreLocation)/2.0
                targetMin = targetPosition - Vector2(6.0, 6.0)
                targetMax = targetPosition + Vector2(6.0, 6.0)
                goal = self.level.findRandomFreePositionInBox([targetMin, targetMax])

                for bot in self.game.bots_alive:           
                    if bot == self.defender or bot == self.attacker:
                        continue
                    
                    self.issue(commands.Attack, bot, goal, description = 'running to intercept', lookAt=targetPosition)
        
        # In this example we loop through all living bots without orders (self.game.bots_available)
        # All other bots will wander randomly
        for bot in self.game.bots_available:           
            if (self.defender == None or self.defender == bot) and not bot.flag:
                self.defender = bot

                # Stand on a random position in a box of 4m around the flag.
                targetPosition = self.game.team.flag.position
                targetMin = targetPosition - Vector2(2.0, 2.0)
                targetMax = targetPosition + Vector2(2.0, 2.0)
                goal = self.level.findRandomFreePositionInBox([targetMin, targetMax])
                
                if (goal - bot.position).length() > 8.0:
                    self.issue(commands.Charge, self.defender, goal, description = 'running to defend')
                else:
                    self.issue(commands.Defend, self.defender, (self.middle - bot.position), description = 'turning to defend')

            elif self.attacker == None or self.attacker == bot or bot.flag:
                self.attacker = bot

                if bot.flag:
                    # Tell the flag carrier to run home!
                    target = self.game.team.flagScoreLocation
                    self.issue(commands.Charge, bot, target, description = 'running home')
                else:
                    target = self.game.enemyTeam.flag.position
                    flank = self.getFlankingPosition(bot, target)
                    if (target - flank).length() > (bot.position - target).length():
                        self.issue(commands.Attack, bot, target, description = 'attack from flank', lookAt=target)
                    else:
                        flank = self.level.findNearestFreePosition(flank)
                        self.issue(commands.Charge, bot, flank, description = 'running to flank')

            else:
                # All our other (random) bots

                # pick a random position in the level to move to                               
                halfBox = 0.4 * min(self.level.width, self.level.height) * Vector2(1, 1)
                
                target = self.level.findRandomFreePositionInBox((self.middle + halfBox, self.middle - halfBox))

                # issue the order
                if target:
                    self.issue(commands.Attack, bot, target, description = 'random patrol')

        for bot in self.game.bots_holding:
            target = self.level.findRandomFreePositionInBox((bot.position-5.0, bot.position+5.0))
            self.issue(commands.Attack, bot, target, lookAt = random.choice([b.position for b in bot.visibleEnemies]))


    def getFlankingPosition(self, bot, target):
        flanks = [target + f * 16.0 for f in [self.left, self.right]]
        options = map(lambda f: self.level.findNearestFreePosition(f), flanks)
        return sorted(options, key = lambda p: (bot.position - p).length())[0]

