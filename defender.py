# Your AI for CTF must inherit from the base Commander class.  See how this is
# implemented by looking at the commander.py in the ./api/ folder.
from api import Commander

# The commander can send 'Commands' to individual bots.  These are listed and
# documented in commands.py from the ./api/ folder also.
from api import commands

# The maps for CTF are layed out along the X and Z axis in space, but can be
# effectively be considered 2D.
from api import Vector2
import math
import sys


class ArlecksCommander(Commander):
    """
    Rename and modify this class to create your own commander and add mycmd.Placeholder
    to the execution command you use to run the competition.
    """

    def zeropoint(self, a, b, c):
        root = math.sqrt(math.pow(b, 2) - 4 * a * c)
        return [(-b + root) / (2 * a), (-b - root) / (2 * a)]


    def angledVector(self, vec, angle):
        normalAngle = angle + math.atan2(vec.y, vec.x)
        return Vector2(math.cos(normalAngle), math.sin(normalAngle))
    
    def initialize(self):
        """Use this function to setup your bot before the game starts."""
        self.verbose = True    # display the command descriptions next to the bot labels
        self.defenders = []

        # Calculate flag positions and store the middle.
        self.ours = self.game.team.flag.position
        self.theirs = self.game.enemyTeam.flag.position
        self.middle = (self.theirs + self.ours) / 2.0

        # Now figure out the flaking directions, assumed perpendicular.
        d = (self.ours - self.theirs)
        self.left = Vector2(-d.y, d.x).normalized()
        self.right = Vector2(d.y, -d.x).normalized()
        self.front = Vector2(d.x, d.y).normalized()
        self.defendAngle = self.level.FOVangle[self.level.fieldOfViewAngles[BotInfo.STATE_DEFENDING]]

        if self.game.team.flagSpawnLocation.x - self.level.firingDistance <= 0:
            intersect = math.sqrt(self.level.firingDistance ** 2 - self.game.team.flagSpawnLocation.x ** 2)
            outerVec = Vector2(self.game.team.flagSpawnLocation.x * -1, intersect)
            xVec = Vector2(-1, 0)
            angle = math.atan2(outerVec.x * xVec.y - outerVec.y * xVec.x, outerVec.x * xVec.x + outerVec.y * xVec.y)
            sys.stdout.write(str(self.level.firingDistance) + ' ' + str(self.game.team.flagSpawnLocation.x) + ' ' + str(self.level.FOVangle) + ' ' + str(angle))
            #lookDir = outerVec.length() * math.cos(self.level.FOVangle / 2) / outerVec
            circle = 2 * (math.pi - angle)
            while circle > 0:
                sys.stdout.write('\n' + str(outerVec) + '\n')
                self.defenders += [[None, self.angledVector(outerVec, self.defendAngle / -2)]]
                outerVec = self.angledVector(outerVec, -1 * self.defendAngle)
                circle -= self.defendAngle
            #sys.stdout.write(str(self.defenders[0][1]) + ' ' + str(self.defenders[1][1]) + ' ' + str(self.defenders[2][1]))
        elif self.game.team.flagSpawnLocation.x + self.level.firingDistance >= self.level.width:
            intersect = math.sqrt(self.level.firingDistance ** 2 - (self.level.width - self.game.team.flagSpawnLocation.x) ** 2)
            outerVec = Vector2(self.level.width - self.game.team.flagSpawnLocation.x, intersect)
            xVec = Vector2(1, 0)
            angle = math.atan2(outerVec.x * xVec.y - outerVec.y * xVec.x, outerVec.x * xVec.x + outerVec.y * xVec.y)
            sys.stdout.write(str(self.level.FOVangle) + ' ' + str(angle))
            #lookDir = outerVec.length() * math.cos(self.level.FOVangle / 2) / outerVec
            circle = 2 * (math.pi - angle)
            while circle > 0:
                sys.stdout.write('\n' + str(outerVec) + '\n')
                self.defenders += [[None, self.angledVector(outerVec, self.defendAngle / 2)]]
                outerVec = self.angledVector(outerVec, self.defendAngle)
                circle -= self.defendAngle
        """elif self.game.team.flagSpawnLocation.y - self.level.firingDistance <= 0:
            intersect = math.sqrt(self.level.firingDistance ** 2 - self.game.team.flagSpawnLocation.y ** 2)
            outerVec = Vector2(intersect, self.game.team.flagSpawnLocation.y * -1)
            lookDir = outerVec.length() * math.cos(self.level.FOVangle / 2) / outerVec
            self.issue(commands.Defend, bot, lookDir, description = "3")
        elif self.game.team.flagSpawnLocation.y - self.level.firingDistance >= self.level.height:
            intersect = math.sqrt(self.level.firingDistance ** 2 - self.game.team.flagSpawnLocation.y ** 2)
            outerVec = Vector2(self.game.team.flagSpawnLocation.x * -1, intersect)
            lookDir = outerVec.length() * math.cos(self.level.FOVangle / 2) / outerVec
            self.issue(commands.Defend, bot, lookDir, description = "4")"""

    def captured(self):
        """Did this team cature the enemy flag?"""
        return self.game.enemyTeam.flag.carrier != None

    def enemyCaptured(self):
        """Did this enemy cature our flag?"""
        return self.game.team.flag.carrier != None

    def getFlankingPosition(self, bot, target):
        flanks = [target + f * 16.0 for f in [self.left, self.right]]
        options = map(lambda f: self.level.findNearestFreePosition(f), flanks)
        return sorted(options, key = lambda p: (bot.position - p).length())[0]

    def tick(self):
        for defender in self.defenders:
            if defender[0] and (defender[0].health <= 0 or defender[0].flag):
                # the defender is dead we'll pick another when available
                defender[0] = None

        for bot in self.game.bots_available:
            if bot.flag:
                self.issue(commands.Charge, bot, self.game.team.flagScoreLocation, description = "score")
            else:
                defending = False
                for defender in self.defenders:
                    if (defender[0] == None or defender[0] == bot) and not bot.flag:
                        defender[0] = bot
                        defending = True
    
                        # Stand on a random position in a box of 4m around the flag.
                        if (bot.position - self.game.team.flagSpawnLocation).length() > 3.0:
                            self.issue(commands.Attack, bot, self.game.team.flagSpawnLocation, description = "move", 
                                lookAt = self.game.team.flagSpawnLocation)
                        else:
                            sys.stdout.write("bot look:" + str(defender[1]));
                            self.issue(commands.Defend, bot, defender[1], description = 'defending')
                        break
                            
                if not defending:
                    self.issue(commands.Charge, bot, self.theirs, description = 'attacking', lookAt = self.theirs)

    def shutdown(self):
        """Use this function to teardown your bot after the game is over, or perform an
        analysis of the data accumulated during the game."""

        pass