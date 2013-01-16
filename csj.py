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
import random
import copy
from api.gameinfo import BotInfo
from api.gameinfo import MatchCombatEvent
import networkx as nx
import itertools
from visibility import Wave
from visibility import line

class CSJCommander(Commander):
    
    def feq(self, f, s):
        return math.fabs(f - s) < 0.00000001
    
    def veq(self, f, s):
        return self.feq(f.x, s.x) and self.feq(f.y, s.y)
    
    def lineEq(self, start, end, x, y):
        return (end.y - start.y) * x + (start.x - end.x) * y + end.x * start.y - start.x * end.y
    
    def angledVector(self, vec, angle):
        normalAngle = angle + math.atan2(vec.y, vec.x)
        return Vector2(math.cos(normalAngle), math.sin(normalAngle))
    
    def initialize(self):
        self.verbose = True
        self.midEnemySpawn = self.game.enemyTeam.botSpawnArea[0].midPoint(self.game.enemyTeam.botSpawnArea[1])
        self.combats = dict()
        self.places = []
        self.attacker = None
        self.index = 0
        self.aliveEnemies = 0
        self.cStd = commands.Attack
        
    def smartIssue(self, bot, pos, lookAt = None, description = ''):
        if self.cStd is commands.Attack:
            self.issue(commands.Attack, bot, pos, lookAt, description)
        else:
            self.issue(commands.Charge, bot, pos, description)
        
    def tick(self):
        visibleEnemies = [enemy for bot in self.game.bots_alive for enemy in bot.visibleEnemies]
        for e in self.game.match.combatEvents[self.index:]:
            if e.type == MatchCombatEvent.TYPE_RESPAWN and e.subject in self.game.enemyTeam.members:
                self.aliveEnemies += 1
                sys.stdout.write(str(self.aliveEnemies) + '\n')
            elif e.type == MatchCombatEvent.TYPE_KILLED and e.subject in self.game.enemyTeam.members:
                self.aliveEnemies -= 1
                sys.stdout.write(str(self.aliveEnemies) + '\n')
        self.index = len(self.game.match.combatEvents)
                
        if self.game.bots_alive >= 2 * self.aliveEnemies:
            cStd = commands.Charge

        if self.game.enemyTeam.flag.carrier:
            self.attacker = self.game.enemyTeam.flag.carrier
            if self.attacker.state is not BotInfo.STATE_SHOOTING and self.attacker.state is not BotInfo.STATE_CHARGING and self.attacker.state is not BotInfo.STATE_TAKINGORDERS:
                self.issue(commands.Charge, self.attacker, self.game.team.flagScoreLocation, description = 'score')
        elif not self.attacker or self.attacker.health <= 0:
            candidates = []
            for bot in self.game.bots_alive:
                if not bot.state is BotInfo.STATE_SHOOTING and not bot.state is BotInfo.STATE_HOLDING:
                    candidates.append(bot)
            if candidates:
                self.attacker = sorted(candidates, key = lambda f: f.position.distance(self.game.enemyTeam.flag.position))[0]
                self.smartIssue(self.attacker, self.game.enemyTeam.flag.position, description = 'capture')
            else:
                self.attacker = None
        elif self.attacker.state is BotInfo.STATE_IDLE:
            self.smartIssue(self.attacker, self.game.enemyTeam.flag.position, description = 'capture')

        if visibleEnemies:
            for bot in self.game.bots_alive:
                if not bot.flag and  bot.state is not BotInfo.STATE_SHOOTING and bot.state is not BotInfo.STATE_TAKINGORDERS and (bot not in self.combats or self.combats[bot][0].health <= 0 or self.combats[bot][1] + 4 < self.game.match.timePassed):
                    kill = sorted(visibleEnemies, key = lambda f: f.position.distance(bot.position))[0]
                    if (bot not in self.combats or self.combats[bot][0] is not kill) and (bot is not self.attacker or kill.position.distance(bot.position) < self.level.firingDistance * 2):
                        self.combats[bot] = (kill, self.game.match.timePassed)
                        if kill.position.distance(bot.position) > self.level.firingDistance * 3:
                            self.issue(commands.Charge, bot, kill.position, description = 'charge ' + kill.name)
                        else:
                            self.smartIssue(bot, kill.position, description = 'attack ' + kill.name)
        else:
            for bot in self.game.bots_available:
                if bot is not self.attacker:
                    self.smartIssue(bot, self.level.findRandomFreePositionInBox(self.level.area), lookAt = random.choice([self.midEnemySpawn, self.game.team.flag.position, self.game.enemyTeam.flagScoreLocation]), description = 'come at me')
                    
        for bot in self.game.bots_alive:
            if bot.state is BotInfo.STATE_HOLDING:
                enemies = []
                friends = []
                for enemy in bot.visibleEnemies:
                    if enemy.state is BotInfo.STATE_HOLDING or enemy.state is BotInfo.STATE_DEFENDING and bot.position.distance(enemy.position) < self.level.firingDistance + 2:
                        enemies.append(enemy)
                for friend in self.game.bots_alive:
                    if friend is not bot and friend.state is BotInfo.STATE_HOLDING and friend.position.distance(bot.position) < self.level.firingDistance + 2:
                        same_boat = False
                        friendEnemies = []
                        for enemy in friend.visibleEnemies:
                            if enemy.state is BotInfo.STATE_HOLDING or enemy.state is BotInfo.STATE_DEFENDING and friend.position.distance(enemy.position) < self.level.firingDistance + 2:
                                if enemy in enemies:
                                    same_boat = True
                                else:
                                    friendEnemies.append(enemy)
                        if same_boat:
                            friends.append(friend)
                            enemies += friendEnemies
                if len(friends) > len(enemies) * 1.5:
                    sys.stdout.write('enemies: ' + str([e.name for e in enemies]) + '\nfriends: ' + str([f.name for f in friends]) + '\n')
                    for friend in friends:
                        self.issue(commands.Attack, friend, enemies[0].position, description = 'antihold')
                
            