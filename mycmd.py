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
from PySide import QtGui, QtCore
import networkx as nx
import itertools
from visibility import Wave
from visibility import line

from visualizer import VisualizerApplication

class ArlecksCommander(Commander):
    
    LEFTUP = 0
    LEFTDOWN = 1
    RIGHTUP = 2
    RIGHTDOWN = 3
    TOPLEFT = 4
    TOPRIGHT = 5
    BOTTOMLEFT = 6
    BOTTOMRIGHT = 7

    def zeropoint(self, a, b, c):
        root = math.sqrt(math.pow(b, 2) - 4 * a * c)
        return [(-b + root) / (2 * a), (-b - root) / (2 * a)]


    def angledVector(self, vec, angle):
        normalAngle = angle + math.atan2(vec.y, vec.x)
        return Vector2(math.cos(normalAngle), math.sin(normalAngle))
    
    def feq(self, f, s):
        return math.fabs(f - s) < 0.00000001
    
    def veq(self, f, s):
        return self.feq(f.x, s.x) and self.feq(f.y, s.y)
    
    def lineEq(self, start, end, x, y):
        return (end.y - start.y) * x + (start.x - end.x) * y + end.x * start.y - start.x * end.y
    
    def intersects(self, start, end, p, length = 0):
        if length is 0:
            length = start.distance(end)
        if p.distance(start) <= length and p.distance(end) <= length:
            topLeft = self.lineEq(start, end, p.x, p.y)
            topRight = self.lineEq(start, end, p.x + 1, p.y)
            bottomRight = self.lineEq(start, end, p.x + 1, p.y + 1)
            bottomLeft = self.lineEq(start, end, p.x, p.y + 1)
            if self.feq(topLeft, 0) or self.feq(topRight, 0) or self.feq(bottomRight, 0) or self.feq(bottomLeft, 0) or not ((topLeft > 0) is (topRight > 0) is (bottomRight > 0) is (bottomLeft > 0)):
                return True
        return False
    
    def lineIntersection(self, start1, end1, start2, end2):
        denom = ((end1.x - start1.x) * (end2.y - start2.y)) - ((end1.y - start1.y) * (end2.x - start2.x))
 
        if denom is 0:
            return None

        numer = ((start1.y - start2.y) * (end2.x - start2.x)) - ((start1.x - start2.x) * (end2.y - start2.y));
    
        r = numer / denom;
    
        numer2 = ((start1.y - start2.y) * (end1.x - start1.x)) - ((start1.x - start2.x) * (end1.y - start1.y));
    
        s = numer2 / denom;
    
        if r < 0 or r > 1 or s < 0 or s > 1:
            return None
        
        return Vector2(start1.x + (r * (end1.x - start1.x)), start1.y + (r * (end1.y - start1.y)))

    def intersectsWhere(self, start, end, p):
        intersections = []
        intersection = self.lineIntersection(start, end, p, Vector2(p.x + 1, p.y))
        if intersection:
            intersections.append(intersection)
        intersection = self.lineIntersection(start, end, p, Vector2(p.x, p.y + 1))
        if intersection:
            intersections.append(intersection)
        intersection = self.lineIntersection(start, end, Vector2(p.x + 1, p.y), Vector2(p.x + 1, p.y + 1))
        if intersection:
            intersections.append(intersection)
        intersection = self.lineIntersection(start, end, Vector2(p.x, p.y + 1), Vector2(p.x + 1, p.y + 1))
        if intersection:
            intersections.append(intersection)
        
        if not intersections:
            return None
        else:
            return sorted(intersections, key = lambda f: f.distance(start))[0]
    
    def whoBlocks(self, blocked, start, end, length = 0):
        for p in blocked:
            if self.intersects(start, end, p, length):
                return p
        return None
    
    def whoBlocksWhere(self, blocked, start, end):
        for p in blocked:
            intersection = self.intersectsWhere(start, end, p)
            if intersection:
                return intersection
        return None
    
    def freeLoS(self, blocked, start, end):
        return not self.whoBlocks(blocked, start, end)
                        
    def recurseNeighbours(self, x, y, visited):
        if x >= 0 and x < self.level.width and y >= 0 and y < self.level.height:
            if self.level.blockHeights[x][y] < 2:
                return False, set(), set()
            elif not Vector2(x, y) in visited:
                visited.append(Vector2(x, y))
                nEdges, island = set(), set()
                topLeft, topRight, bottomLeft, bottomRight, top, left, right, bottom = True, True, True, True, True, True, True, True
                for i in range(-1, 2):
                    for j in range(-1, 2):
                        if not (i is 0 and j is 0):
                            isBlocked, neighbourRes, islandRes = self.recurseNeighbours(x + i, y + j, visited)
                            nEdges |= neighbourRes
                            island |= islandRes
                            if isBlocked:
                                if i is -1:
                                    if j is 0:
                                        topLeft, bottomLeft, left = False, False, False
                                    elif j is -1:
                                        topLeft = False
                                    else:
                                        bottomLeft = False
                                elif i is 0:
                                    if j is -1:
                                        topLeft, topRight, top = False, False, False
                                    else:
                                        bottomLeft, bottomRight, bottom = False, False, False
                                else:
                                    if j is 0:
                                        topRight, bottomRight, right = False, False, False
                                    elif j is -1:
                                        topRight = False
                                    else:
                                        bottomRight = False
                    
                if topLeft:
                    if x - 0.25 > 0 and y + 1 < self.level.height:
                        nEdges.add((Vector2(x - 0.25, y + 1), self.LEFTUP))
                    if x + 1 < self.level.width and y - 0.25 > 0:
                        nEdges.add((Vector2(x + 1, y - 0.25), self.TOPLEFT))
                if bottomLeft:
                    if x - 0.25 > 0:
                        nEdges.add((Vector2(x - 0.25, y), self.LEFTDOWN))
                    if x + 1 < self.level.width and y + 1.25 < self.level.height:
                        nEdges.add((Vector2(x + 1, y + 1.25), self.BOTTOMLEFT))
                if topRight:
                    if x + 1.25 < self.level.width and y + 1 < self.level.height:
                        nEdges.add((Vector2(x + 1.25, y + 1), self.RIGHTUP))
                    if y - 0.25 > 0:
                        nEdges.add((Vector2(x, y - 0.25), self.TOPRIGHT))
                if bottomRight:
                    if x + 1.25 < self.level.width:
                        nEdges.add((Vector2(x + 1.25, y), self.RIGHTDOWN))
                    if y + 1.25 < self.level.height:
                        nEdges.add((Vector2(x, y + 1.25), self.BOTTOMRIGHT))
                    
                if top or bottom or right or left:
                    island.add(Vector2(x, y))
                            
                return True, nEdges, island
            else:
                return True, set(), set()
        else:
            return True, set(), set()
                        
    def recursePaths(self, p, blocked, deadlines, visited = [], pointsAndLinesByEdge = dict()):
        if p.x >= 0 and p.y >= 0 and p.x < self.level.width and p.y < self.level.height and not p in visited:
            visited.append(p)
            for block in blocked:
                if p.x >= block.x and p.x <= block.x + 1 and p.y >= block.y and p.y <= block.y + 1:
                    return
            for edge, contacts in deadlines.iteritems():
                for contact in contacts:
                    """line = (edge, contact)
                    if p.distance(line[0]) <= line[0].distance(line[1]) and p.distance(line[1]) <= line[0].distance(line[1]) and not (self.veq(line[0], p) or self.veq(line[1], p)):
                        topLeft = self.lineEq(line, p.x, p.y)
                        topRight = self.lineEq(line, p.x + 1, p.y)
                        bottomRight = self.lineEq(line, p.x + 1, p.y + 1)
                        bottomLeft = self.lineEq(line, p.x, p.y + 1)
                        if self.feq(topLeft, 0) or self.feq(topRight, 0) or self.feq(bottomRight, 0) or self.feq(bottomLeft, 0) or not ((topLeft > 0) is (topRight > 0) is (bottomRight > 0) is (bottomLeft > 0)):"""
                    if self.intersects(edge, contact, p):
                        if edge in pointsAndLinesByEdge:
                            pointsAndLinesByEdge[edge].append((p, contact))
                        else:
                            pointsAndLinesByEdge[edge] = [(p, contact)]
                        return
            recalc= []
            for edge in deadlines.keys():
                if p.distance(edge) <= self.level.firingDistance and not self.whoBlocks(blocked, p, edge):
                    sys.stdout.write('removed: ' + str(p) + ' '  + str(edge) + '\n')
                    del deadlines[edge]
                    if edge in pointsAndLinesByEdge:
                        for pointAndLine in pointsAndLinesByEdge[edge]:
                            recalc.append(pointAndLine[0])
                            visited.remove(pointAndLine[0])
                        del pointsAndLinesByEdge[edge]
            for re in recalc:
                self.recursePaths(re, blocked, deadlines, visited, pointsAndLinesByEdge)
                    
            
            
            self.recursePaths(Vector2(p.x - 1, p.y), blocked, deadlines, visited, pointsAndLinesByEdge)
            self.recursePaths(Vector2(p.x, p.y - 1), blocked, deadlines, visited, pointsAndLinesByEdge)
            self.recursePaths(Vector2(p.x + 1, p.y), blocked, deadlines, visited, pointsAndLinesByEdge)
            self.recursePaths(Vector2(p.x, p.y + 1), blocked, deadlines, visited, pointsAndLinesByEdge)
                        
    def newDeadline(self, edge, contact):
        if edge in self.deadlines:
            self.deadlines[edge].add(contact)
        else:
            self.deadlines[edge] = set([contact])
            
    def deadlineFromLine(self, blocked, spawn, start, end):
        intersect = self.whoBlocksWhere(blocked, start, end)
        spawnIntersect = self.whoBlocks(spawn, start, end)
        if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
            self.newDeadline(start, intersect)
        else:
            intersect = self.lineIntersection(start, end, Vector2(0, 0), Vector2(0, self.level.height))
            if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
                self.newDeadline(start, intersect)
            else:
                intersect = self.lineIntersection(start, end, Vector2(0, 0), Vector2(self.level.width, 0))
                if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
                    self.newDeadline(start, intersect)
                else:
                    intersect = self.lineIntersection(start, end, Vector2(0, self.level.height), Vector2(self.level.width, self.level.height))
                    if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
                        self.newDeadline(start, intersect)
                    else:
                        intersect = self.lineIntersection(start, end, Vector2(self.level.width, 0), Vector2(self.level.width, self.level.height))
                        if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
                            self.newDeadline(start, intersect)
    
    def initialize(self):
        """Use this function to setup your bot before the game starts."""
        self.verbose = True    # display the command descriptions next to the bot labels
        self.carrier = None
        self.interceptors = []
        self.assassins = dict()
        self.defenders = []
        self.camper = None
        self.attackers = []
        self.spawnCampers = []
        self.aliveEnemies = 0
        self.lastEventIndex = -1
        
        

        # Calculate flag positions and store the middle.
        self.ours = self.game.team.flag.position
        self.theirs = self.game.enemyTeam.flag.position
        self.middle = (self.theirs + self.ours) / 2.0

        # Now figure out the flanking directions, assumed perpendicular.
        d = (self.ours - self.theirs)
        self.left = Vector2(-d.y, d.x).normalized()
        self.right = Vector2(d.y, -d.x).normalized()
        self.front = Vector2(d.x, d.y).normalized()
        self.defendAngle = self.level.fieldOfViewAngles[BotInfo.STATE_DEFENDING]
        self.midEnemySpawn = self.game.enemyTeam.botSpawnArea[0].midPoint(self.game.enemyTeam.botSpawnArea[1])
        
        """circle = 2 * math.pi
        outerVec = self.game.enemyTeam.botSpawnArea[0] - self.game.enemyTeam.flagSpawnLocation
        while circle > 0:
                self.defenders += [[None, self.angledVector(outerVec, self.defendAngle / 2)]]
                outerVec = self.angledVector(outerVec, self.defendAngle)
                circle -= self.defendAngle
        
        campPos = []
        campPos.append(Vector2(self.game.enemyTeam.botSpawnArea[0].x - self.level.firingDistance, self.game.enemyTeam.botSpawnArea[0].y + 0.5 * (self.game.enemyTeam.botSpawnArea[1].y - self.game.enemyTeam.botSpawnArea[0].y)))
        campPos.append(Vector2(self.game.enemyTeam.botSpawnArea[0].x + 0.5 * (self.game.enemyTeam.botSpawnArea[1].x  - self.game.enemyTeam.botSpawnArea[0].x ), self.game.enemyTeam.botSpawnArea[1].y + self.level.firingDistance))
        campPos.append(Vector2(self.game.enemyTeam.botSpawnArea[1].x + self.level.firingDistance, self.game.enemyTeam.botSpawnArea[0].y + 0.5 * (self.game.enemyTeam.botSpawnArea[1].y - self.game.enemyTeam.botSpawnArea[0].y)))
        campPos.append(Vector2(self.game.enemyTeam.botSpawnArea[0].x + 0.5 * (self.game.enemyTeam.botSpawnArea[1].x  - self.game.enemyTeam.botSpawnArea[0].x ), self.game.enemyTeam.botSpawnArea[0].y - self.level.firingDistance))

        for cp in campPos:
            free = self.level.findNearestFreePosition(cp)
            if free:
                sys.stdout.write(str(free) + '\n')
                self.spawnCampers.append([None, free, False])
        """
        sys.stdout.write(str(self.game.enemyTeam.botSpawnArea[1]) + ' ' + str(self.level.characterRadius) + '\n')
        visited, islandEdges, islandOuter = [], [], []
        for x in range(0, len(self.level.blockHeights)):
            for y in range(0, len(self.level.blockHeights[x])):
                _, edges, island = self.recurseNeighbours(x, y, visited)
                if edges:
                    islandEdges.append(edges)
                    islandOuter.append(island)
                    
                    
        sys.stdout.write(str(islandEdges) + '\n' + str(islandOuter) + '\n')
                   
        blocked = [item for sublist in islandOuter for item in sublist]
        #blockedOrSpawn = blocked[:]
        spawn = []
        for x in range(int(self.game.enemyTeam.botSpawnArea[0].x), int(self.game.enemyTeam.botSpawnArea[1].x)):
            for y in range(int(self.game.enemyTeam.botSpawnArea[0].y), int(self.game.enemyTeam.botSpawnArea[1].y)):
                spawn.append(Vector2(x, y))
        #blockedOrSpawn += spawn
                
        self.deadlines = dict()
        for i in range(len(islandEdges)):
            for coord, orientation in islandEdges[i]:
                if orientation is self.TOPLEFT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - self.level.firingDistance / 1.0283968, coord.y + 0.24 * self.level.firingDistance / 1.0283968))
                elif orientation is self.BOTTOMLEFT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - self.level.firingDistance / -1.0283968, coord.y - 0.24 * self.level.firingDistance / 1.0283968))
                elif orientation is self.LEFTUP:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + 0.24 * self.level.firingDistance / 1.0283968, coord.y - self.level.firingDistance / 1.0283968))
                elif orientation is self.RIGHTUP:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.24 * self.level.firingDistance / 1.0283968, coord.y - self.level.firingDistance / 1.0283968))
                elif orientation is self.TOPRIGHT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + self.level.firingDistance / 1.0283968, coord.y + 0.24 * self.level.firingDistance / 1.0283968))
                elif orientation is self.BOTTOMRIGHT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + self.level.firingDistance / 1.0283968, coord.y - 0.24 * self.level.firingDistance / 1.0283968))
                elif orientation is self.LEFTDOWN:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + 0.24 * self.level.firingDistance / 1.0283968, coord.y + self.level.firingDistance / 1.0283968))
                elif orientation is self.RIGHTDOWN:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.24 * self.level.firingDistance / 1.0283968, coord.y + self.level.firingDistance / 1.0283968))
                
        sys.stdout.write(str(self.deadlines) + '\n')
        pointsAndLinesByEdge = dict()
        try:
            self.recursePaths(self.midEnemySpawn, blocked, self.deadlines, [], pointsAndLinesByEdge)
        except RuntimeError as e:
            sys.stdout.write(str(e) + '\n')
        camplines = set()
        for edge, pls in pointsAndLinesByEdge.iteritems():
            for _, contact in pls:
                camplines.add((self.level.findNearestFreePosition(edge), contact))
        sys.stdout.write('\n' + str(camplines))
        
        for cl in camplines:
            self.spawnCampers.append([[], cl])

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
        for self.lastEventIndex in range(self.lastEventIndex + 1, len(self.game.match.combatEvents)):
            if self.game.match.combatEvents[self.lastEventIndex].type is MatchCombatEvent.TYPE_RESPAWN and self.game.match.combatEvents[self.lastEventIndex].subject in self.game.enemyTeam.members:
                self.aliveEnemies += 1
                sys.stdout.write(str(self.aliveEnemies) + self.game.match.combatEvents[self.lastEventIndex].subject.name + '\n')
            elif self.game.match.combatEvents[self.lastEventIndex].type is MatchCombatEvent.TYPE_KILLED and self.game.match.combatEvents[self.lastEventIndex].subject in self.game.enemyTeam.members:
                self.aliveEnemies -= 1
                sys.stdout.write(str(self.aliveEnemies) + ' ' + self.game.match.combatEvents[self.lastEventIndex].subject.name + '\n')
        
        
        bots_unused = self.game.bots_available
        bots_alive_unused = []
        for bot in self.game.bots_alive:
            if bot.state is not BotInfo.STATE_SHOOTING:
                bots_alive_unused.append(bot)
        
        enemies = []
        
        if not self.enemyCaptured():
            for interceptor in self.interceptors:
                bots_unused.append(interceptor[0])
                self.interceptors.remove(interceptor)
        else:
            for interceptor in self.interceptors:
                if interceptor[0] < self.game.match.timePassed + 3:
                    #if self.game.team.flag.carrier in interceptor.visibleEnemies and self.game.team.flag.position.distance(interceptor.position) < self.level.firingDistance + 3:
                        #self.issue(commands.Defend, interceptor, )
                    self.issue(commands.Charge, interceptor, interceptor.position.midPoint(self.game.team.flag.position), description = "kill carrier")
                
        if self.carrier and not self.game.enemyTeam.flag.carrier:
            self.carrier = None
            
        for assassin in self.assassins.keys():
            if self.assassins[assassin][0].health <= 0:
                bots_unused.append(assassin)
                del self.assassins[assassin]
                
        for c in self.spawnCampers:
            for derp in c[0][:]:
                if derp[0].health <= 0:
                    c[0].remove(derp)
                
        if self.camper and (self.camper.health <= 0 or self.camper.flag):
            self.camper = None
                
        if self.aliveEnemies is 0:
            for bot in bots_alive_unused:
                if bot.flag:
                    self.issue(commands.Charge, bot, self.game.team.flagScoreLocation, description = 'straight home')
                else:
                    handled = False
                    for c in self.spawnCampers:
                        for b in c[0]:
                            if bot is b[0]:
                                if not b[1]:
                                    if bot.position.distance(c[1][0]) < 1:
                                        self.issue(commands.Defend, bot, c[1][1] - bot.position)
                                        b[1] = True
                                    else:
                                        self.issue(commands.Charge, bot, c[1][0])
                                handled = True
                                break
                        if handled:
                            break
                    if not handled:
                        myplace = sorted(self.spawnCampers, key = lambda f: len(f[0]))[0]
                        myplace[0].append([bot, False])      
                        self.issue(commands.Charge, bot, myplace[1][0])
        else:
            for bot in bots_alive_unused:
                for enemy in bot.visibleEnemies:
                    if enemy.health > 0 and not enemy in enemies:
                        enemies.append(enemy)
                if bot.flag:
                    if bot in bots_unused:
                            bots_unused.remove(bot)
                    bots_alive_unused.remove(bot)
                    if not self.carrier is bot:
                        self.issue(commands.Charge, bot, [self.level.findNearestFreePosition(self.getFlankingPosition(bot, self.game.team.flagScoreLocation)), self.game.team.flagScoreLocation], description = "score")
                        self.carrier = bot    
    
                    
            """for enemy in enemies:
                if not bots_alive_unused:
                    break
                
                closest = sorted(bots_alive_unused, key = lambda i: i.position.distance(enemy.position))[0]
                
                if (closest in enemy.seenBy or  and enemy.position.distance(closest.position) < self.level.firingDistance + 3:
                    if closest not in self.assassins or self.assassins[closest] is not enemy or closest.state is BotInfo.STATE_CHARGING:
                        self.issue(commands.Defend, closest, (enemy.position - bot.position), description = 'comeAtMe ' + enemy.name)
                else:
                    if closest not in self.assassins or self.assassins[closest] is not enemy or closest.state is BotInfo.STATE_DEFENDING:
                        self.issue(commands.Charge, closest, enemy.position, description = 'charge ' + enemy.name)
                    
                self.assassins[closest] = enemy
                bots_alive_unused.remove(closest)
                if closest in bots_unused:
                    bots_unused.remove(closest)"""
                
            """if enemies:
                for bot in bots_alive_unused:
                    closest = sorted(enemies, key = lambda i: i.position.distance(bot.position))[0]
                    if bot not in self.assassins or (self.assassins[bot][0] is not closest and self.assassins[bot][1] + 4 < self.game.match.timePassed):
                        lookDirs = []
                        for otherbot in self.game.bots_alive:
                            if otherbot.position.distance(bot) < 5:
                                lookDirs[]
                        self.issue(commands.Attack, bot, closest.position, description = 'attack ' + closest.name)
                        self.assassins[bot] = (closest, self.game.match.timePassed)
                    if bot in bots_unused:
                        bots_unused.remove(bot)"""
                    
                    
            for bot in bots_unused:
                if self.enemyCaptured() and (self.captured() or bot.position.distance(self.game.enemyTeam.flag.position) > bot.position.distance(self.game.team.flag.position)):
                    self.issue(commands.Charge, bot, bot.position.midPoint(self.game.team.flag.position), description = "kill carrier")
                    self.interceptors.append([bot, self.game.match.timePassed])
                elif self.captured() and bot.position.distance(self.game.enemyTeam.flagSpawnLocation) < 3 and self.camper is None:
                    self.camper = bot
                    directVec = self.game.enemyTeam.botSpawnArea[0] - bot.position
                    self.issue(commands.Defend, bot, [[directVec, 1], [self.angledVector(directVec, self.defendAngle), 1], [self.angledVector(directVec, -1 * self.defendAngle), 1]])
                else:
                    #if bot.position.distance(self.middle) > bot.position.distance(self.game.enemyTeam.flag.position):
                    self.issue(commands.Attack, bot, self.game.enemyTeam.flag.position, lookAt = random.choice([self.game.enemyTeam.flag.position, self.game.enemyTeam.botSpawnArea[0], self.game.enemyTeam.flagSpawnLocation, self.game.team.flag.position]), description = 'attack')
                    #else:
                        #self.issue(commands.Attack, bot, [self.level.findNearestFreePosition(self.middle), self.game.enemyTeam.flag.position], description = 'attac

        

    def shutdown(self):
        """Use this function to teardown your bot after the game is over, or perform an
        analysis of the data accumulated during the game."""

        pass
    
class IdiotCommander(Commander):
    def tick(self):
        for bot in self.game.bots_available:
            self.issue(commands.Move, bot, self.level.findNearestFreePosition(Vector2(0,0)))
            
class RetardCommander(Commander):
    def tick(self):
        for bot in self.game.bots_available:
            self.issue(commands.Move, bot, self.level.findNearestFreePosition(Vector2(self.level.width / 2, self.level.height / 2)))
                
class Spawn2Commander(Commander):
    
    LEFTUP = 0
    LEFTDOWN = 1
    RIGHTUP = 2
    RIGHTDOWN = 3
    TOPLEFT = 4
    TOPRIGHT = 5
    BOTTOMLEFT = 6
    BOTTOMRIGHT = 7
    
    def feq(self, f, s):
        return math.fabs(f - s) < 0.00000001
    
    def veq(self, f, s):
        return self.feq(f.x, s.x) and self.feq(f.y, s.y)
    
    def lineEq(self, start, end, x, y):
        return (end.y - start.y) * x + (start.x - end.x) * y + end.x * start.y - start.x * end.y
    
    def angledVector(self, vec, angle):
        normalAngle = angle + math.atan2(vec.y, vec.x)
        return Vector2(math.cos(normalAngle), math.sin(normalAngle))
    
    def intersects(self, start, end, p, length = 0):
        if length is 0:
            length = start.distance(end)
        if p.distance(start) <= length and p.distance(end) <= length:
            topLeft = self.lineEq(start, end, p.x, p.y)
            topRight = self.lineEq(start, end, p.x + 1, p.y)
            bottomRight = self.lineEq(start, end, p.x + 1, p.y + 1)
            bottomLeft = self.lineEq(start, end, p.x, p.y + 1)
            if self.feq(topLeft, 0) or self.feq(topRight, 0) or self.feq(bottomRight, 0) or self.feq(bottomLeft, 0) or not ((topLeft > 0) is (topRight > 0) is (bottomRight > 0) is (bottomLeft > 0)):
                return True
        return False
    
    def lineIntersection(self, start1, end1, start2, end2):
        denom = ((end1.x - start1.x) * (end2.y - start2.y)) - ((end1.y - start1.y) * (end2.x - start2.x))
 
        if self.feq(denom, 0):
            return None

        numer = ((start1.y - start2.y) * (end2.x - start2.x)) - ((start1.x - start2.x) * (end2.y - start2.y));
    
        r = numer / denom;
    
        numer2 = ((start1.y - start2.y) * (end1.x - start1.x)) - ((start1.x - start2.x) * (end1.y - start1.y));
    
        s = numer2 / denom;
    
        if r < 0 or r > 1 or s < 0 or s > 1:
            return None
        
        return Vector2(start1.x + (r * (end1.x - start1.x)), start1.y + (r * (end1.y - start1.y)))

    def intersectsWhere(self, start, end, p):
        intersections = []
        intersection = self.lineIntersection(start, end, p, Vector2(p.x + 1, p.y))
        if intersection:
            intersections.append(intersection)
        intersection = self.lineIntersection(start, end, p, Vector2(p.x, p.y + 1))
        if intersection:
            intersections.append(intersection)
        intersection = self.lineIntersection(start, end, Vector2(p.x + 1, p.y), Vector2(p.x + 1, p.y + 1))
        if intersection:
            intersections.append(intersection)
        intersection = self.lineIntersection(start, end, Vector2(p.x, p.y + 1), Vector2(p.x + 1, p.y + 1))
        if intersection:
            intersections.append(intersection)
        
        if not intersections:
            return None
        else:
            return sorted(intersections, key = lambda f: f.distance(start))[0]
    
    def whoBlocks(self, blocked, start, end, length = 0):
        for p in blocked:
            if self.intersects(start, end, p, length):
                return p
        return None
    
    def whoBlocksWhere(self, blocked, start, end):
        for p in blocked:
            intersection = self.intersectsWhere(start, end, p)
            if intersection:
                return intersection
        return None
    
    def freeLoS(self, blocked, start, end):
        return not self.whoBlocks(blocked, start, end)
                        
    def recurseNeighbours(self, x, y, visited):
        if x >= 0 and x < self.level.width and y >= 0 and y < self.level.height:
            if self.level.blockHeights[x][y] < 2:
                return False, set(), set()
            elif not Vector2(x, y) in visited:
                visited.append(Vector2(x, y))
                nEdges, island = set(), set()
                leftUp, topLeft, leftDown, bottomLeft, rightUp, topRight, rightDown, bottomRight, top, left, right, bottom = True, True, True, True, True, True, True, True, True, True, True, True
                for i in range(-1, 2):
                    for j in range(-1, 2):
                        if not (i is 0 and j is 0):
                            isBlocked, neighbourRes, islandRes = self.recurseNeighbours(x + i, y + j, visited)
                            nEdges |= neighbourRes
                            island |= islandRes
                            if isBlocked:
                                if i is -1:
                                    if j is 0:
                                        leftUp, leftDown, bottomLeft, topLeft, left = False, False, False, False, False
                                    elif j is -1:
                                        leftUp, topLeft, topRight, leftDown = False, False, False, False
                                    else:
                                        bottomLeft, bottomRight, leftDown, leftUp = False, False, False, False
                                elif i is 0:
                                    if j is -1:
                                        topLeft, topRight, leftUp, rightUp, top = False, False, False, False, False
                                    else:
                                        bottomLeft, bottomRight, leftDown, rightDown, bottom = False, False, False, False, False
                                else:
                                    if j is 0:
                                        topRight, bottomRight, rightUp, rightDown, right = False, False, False, False, False
                                    elif j is -1:
                                        topRight, topLeft, rightUp, rightDown = False, False, False, False
                                    else:
                                        bottomRight, bottomLeft, rightDown, rightUp = False, False, False, False
                    
                if leftUp:
                    nEdges.add((Vector2(x - 0.26, y + 1), self.LEFTUP))
                if topLeft:
                    nEdges.add((Vector2(x + 1, y - 0.26), self.TOPLEFT))
                if leftDown:
                    nEdges.add((Vector2(x - 0.26, y), self.LEFTDOWN))
                if bottomLeft:
                    nEdges.add((Vector2(x + 1, y + 1.26), self.BOTTOMLEFT))
                if rightUp:
                    nEdges.add((Vector2(x + 1.26, y + 1), self.RIGHTUP))
                if topRight:
                    nEdges.add((Vector2(x, y - 0.26), self.TOPRIGHT))
                if rightDown:
                    nEdges.add((Vector2(x + 1.26, y), self.RIGHTDOWN))
                if bottomRight:
                    nEdges.add((Vector2(x, y + 1.26), self.BOTTOMRIGHT))
                    
                if top or bottom or right or left:
                    island.add(Vector2(x, y))
                            
                return True, nEdges, island
            else:
                return True, set(), set()
        else:
            return True, set(), set()
                        
    def recursePaths(self, p, blocked, deadlines, visited = [], pointsAndLinesByEdge = dict()):
        if p.x >= 0 and p.y >= 0 and p.x < self.level.width and p.y < self.level.height and not p in visited:
            visited.append(p)
            for block in blocked:
                if p.x >= block.x and p.x <= block.x + 1 and p.y >= block.y and p.y <= block.y + 1:
                    return
            for edge, contacts in deadlines.iteritems():
                for contact in contacts:
                    """line = (edge, contact)
                    if p.distance(line[0]) <= line[0].distance(line[1]) and p.distance(line[1]) <= line[0].distance(line[1]) and not (self.veq(line[0], p) or self.veq(line[1], p)):
                        topLeft = self.lineEq(line, p.x, p.y)
                        topRight = self.lineEq(line, p.x + 1, p.y)
                        bottomRight = self.lineEq(line, p.x + 1, p.y + 1)
                        bottomLeft = self.lineEq(line, p.x, p.y + 1)
                        if self.feq(topLeft, 0) or self.feq(topRight, 0) or self.feq(bottomRight, 0) or self.feq(bottomLeft, 0) or not ((topLeft > 0) is (topRight > 0) is (bottomRight > 0) is (bottomLeft > 0)):"""
                    if self.intersects(edge, contact, p):
                        if edge in pointsAndLinesByEdge:
                            pointsAndLinesByEdge[edge].append((p, contact))
                        else:
                            pointsAndLinesByEdge[edge] = [(p, contact)]
                        return
            recalc= []
            for edge in deadlines.keys():
                if p.distance(edge) <= self.level.firingDistance and not self.whoBlocks(blocked, p, edge):
                    sys.stdout.write('removed: ' + str(p) + ' '  + str(edge) + '\n')
                    del deadlines[edge]
                    if edge in pointsAndLinesByEdge:
                        for pointAndLine in pointsAndLinesByEdge[edge]:
                            recalc.append(pointAndLine[0])
                            visited.remove(pointAndLine[0])
                        del pointsAndLinesByEdge[edge]
            for re in recalc:
                self.recursePaths(re, blocked, deadlines, visited, pointsAndLinesByEdge)
                    
            
            
            self.recursePaths(Vector2(p.x - 1, p.y), blocked, deadlines, visited, pointsAndLinesByEdge)
            self.recursePaths(Vector2(p.x, p.y - 1), blocked, deadlines, visited, pointsAndLinesByEdge)
            self.recursePaths(Vector2(p.x + 1, p.y), blocked, deadlines, visited, pointsAndLinesByEdge)
            self.recursePaths(Vector2(p.x, p.y + 1), blocked, deadlines, visited, pointsAndLinesByEdge)
                        
    def newDeadline(self, edge, contact):
        if edge in self.deadlines:
            self.deadlines[edge].add(contact)
        else:
            self.deadlines[edge] = set([contact])
            
    def deadlineFromLine(self, blocked, spawn, start, end):
        intersect = self.whoBlocksWhere(blocked, start, end)
        spawnIntersect = self.whoBlocks(spawn, start, end)
        if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
            self.newDeadline(start, intersect)
        else:
            intersect = self.lineIntersection(start, end, Vector2(0, 0), Vector2(0, self.level.height))
            if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
                self.newDeadline(start, intersect)
            else:
                intersect = self.lineIntersection(start, end, Vector2(0, 0), Vector2(self.level.width, 0))
                if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
                    self.newDeadline(start, intersect)
                else:
                    intersect = self.lineIntersection(start, end, Vector2(0, self.level.height), Vector2(self.level.width, self.level.height))
                    if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
                        self.newDeadline(start, intersect)
                    else:
                        intersect = self.lineIntersection(start, end, Vector2(self.level.width, 0), Vector2(self.level.width, self.level.height))
                        if intersect and (not spawnIntersect or spawnIntersect.distance(start) > intersect.distance(start)):
                            self.newDeadline(start, intersect)
    
    def makeGraphs(self):
        blocks = self.level.blockHeights
        width, height = len(blocks), len(blocks[0])

        g = nx.Graph(directed=False, map_height = height, map_width = width)
        #self.positions = g.new_vertex_property('vector<float>')
        #self.weights = g.new_edge_property('float')
    
        #g.vertex_properties['pos'] = self.positions
        #g.edge_properties['weight'] = self.weights
    
        self.terrain = []
        self.positions = {}
        for j in range(0, height):
            row = []
            for i in range(0,width):
                if blocks[i][j] == 0:
                    g.add_node(i+j*width, position = (float(i)+0.5, float(j)+0.5) )
                    self.positions[i+j*width] = Vector2(float(i) + 0.5, float(j) + 0.5)
                    row.append(i+j*width)
                else:
                    row.append(None)
            self.terrain.append(row)
        
        for i, j in itertools.product(range(0, width), range(0, height)):
            p = self.terrain[j][i]
            if not p: continue
    
            if i < width-1:
                q = self.terrain[j][i+1]
                if q:
                    e = g.add_edge(p, q, weight = 1.0)
    
            if j < height-1:
                r = self.terrain[j+1][i]
                if r:
                    e = g.add_edge(p, r, weight = 1.0)
    
        self.graphSneak = g
        self.graphNormal = g
        
    def getNodeIndex(self, position):
        i = int(position.x)
        j = int(position.y)
        width = self.graphNormal.graph["map_width"]
        return i+j*width
    
    def updateEdgeWeights(self):
            blocks = self.level.blockHeights
            width, height = len(blocks), len(blocks[0])
    
            # update the weights in the graph based on the distance to the shortest path between the enemy flag and enemy score location
    
            for j in range(0, height):
                for i in range(0, width -1):
                    a = self.terrain[j][i]
                    b = self.terrain[j][i+1]
                    if a and b:
                        w = max(255 - 4*(self.distances[a] + self.distances[b]), 0)
                        self.graphSneak[a][b]['weight'] = w
    
            for j in range(0, height-1):
                for i in range(0, width):
                    a = self.terrain[j][i]
                    b = self.terrain[j+1][i]
                    if a and b:
                        w = max(255 - 4*(self.distances[a] + self.distances[b]), 0)
                        self.graphSneak[a][b]['weight'] = w
            
    def drawPreBots(self, visualizer):
        for p, q in self.camplines:
            visualizer.drawCircle(p, QtGui.qRgb(255,0,0), 1)
            visualizer.drawRay(p, q - p, QtGui.qRgb(0,255,0))
                                
    def initialize(self):
        self.visualizer = VisualizerApplication(self)
        self.visualizer.setDrawHookPreBots(self.drawPreBots)

        self.verbose = True
        sys.stdout.write(str(self.game.enemyTeam.botSpawnArea[1]) + ' ' + str(self.level.characterRadius) + '\n')
        midEnemySpawn = self.game.enemyTeam.botSpawnArea[0].midPoint(self.game.enemyTeam.botSpawnArea[1])
        visited, islandEdges, islandOuter = [], [], []
        for x in range(0, len(self.level.blockHeights)):
            for y in range(0, len(self.level.blockHeights[x])):
                _, edges, island = self.recurseNeighbours(x, y, visited)
                if edges:
                    islandEdges.append(edges)
                    islandOuter.append(island)
                    
                    
        sys.stdout.write(str(islandEdges) + '\n' + str(islandOuter) + '\n')
                   
        blocked = []
        for i in range(len(self.level.blockHeights)):
            for j in range(len(self.level.blockHeights[0])):
                if self.level.blockHeights[i][j] > 0:
                    blocked.append(Vector2(i, j))
        blockedOrSpawn = blocked[:]
        spawn = []
        for x in range(int(self.game.enemyTeam.botSpawnArea[0].x), int(self.game.enemyTeam.botSpawnArea[1].x)):
            for y in range(int(self.game.enemyTeam.botSpawnArea[0].y), int(self.game.enemyTeam.botSpawnArea[1].y)):
                spawn.append(Vector2(x, y))
        blockedOrSpawn += spawn
        
        magicxs = 1.030776406
        self.deadlines = dict()
        for i in range(len(islandEdges)):
            for coord, orientation in islandEdges[i]:
                if orientation is self.TOPLEFT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - self.level.firingDistance / magicxs, coord.y + 0.25 * self.level.firingDistance / magicxs))
                elif orientation is self.BOTTOMLEFT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + self.level.firingDistance / magicxs, coord.y - 0.25 * self.level.firingDistance / magicxs))
                elif orientation is self.LEFTUP:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + 0.25 * self.level.firingDistance / magicxs, coord.y - self.level.firingDistance / magicxs))
                elif orientation is self.RIGHTUP:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.25 * self.level.firingDistance / magicxs, coord.y - self.level.firingDistance / magicxs))
                elif orientation is self.TOPRIGHT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + self.level.firingDistance / magicxs, coord.y + 0.25 * self.level.firingDistance / magicxs))
                elif orientation is self.BOTTOMRIGHT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + self.level.firingDistance / magicxs, coord.y - 0.25 * self.level.firingDistance / magicxs))
                elif orientation is self.LEFTDOWN:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + 0.25 * self.level.firingDistance / magicxs, coord.y + self.level.firingDistance / magicxs))
                elif orientation is self.RIGHTDOWN:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.25 * self.level.firingDistance / magicxs, coord.y + self.level.firingDistance / magicxs))
                
        sys.stdout.write(str(self.deadlines) + '\n')
        
 
        pointsAndLinesByEdge = dict()
        try:
            self.recursePaths(midEnemySpawn, blocked, self.deadlines, [], pointsAndLinesByEdge)
        except RuntimeError as e:
            sys.stdout.write(str(e) + '\n')
        self.camplines = set()
        for edge, pls in pointsAndLinesByEdge.iteritems():
            for _, contact in pls:
                self.camplines.add((edge, contact))
        sys.stdout.write('\n' + str(self.camplines))
        
        self.campers = []
        for cl in self.camplines:
            self.campers.append([None, cl])
        self.attacker = None
        
    def sneakTo(self, bot, dst, message = ''):
        # calculate the shortest path between the bot and the target using our weights
        srcIndex = self.getNodeIndex(bot.position)
        dstIndex = self.getNodeIndex(dst)
        pathNodes = nx.shortest_path(self.graphSneak, srcIndex, dstIndex, 'weight')
    
        pathLength = len(pathNodes)
        if pathLength > 0:
            path = [self.positions[p] for p in pathNodes if self.positions[p]]
            if len(path) > 0:
                orderPath = path[::10]
                orderPath.append(path[-1]) # take every 10th point including last point
                self.issue(commands.Charge, bot, orderPath, description = message) 
                #self.paths[bot] = path    # store the path for visualization
            
    def tick(self):
        for c in self.campers:
            if c[0] and c[0].health <= 0:
                c[0] = None
        
            
        for bot in self.game.bots_available:
            handled = False
            for c in self.campers:
                if bot is c[0]:
                    if bot.position.distance(c[1][0]) < 1:
                        self.issue(commands.Defend, bot, c[1][1] - bot.position)
                    handled = True
                    break
            if not handled:
                for c in self.campers:
                    if not c[0]:
                        c[0] = bot
                        self.issue(commands.Move, bot, c[1][0])
                        break
        self.visualizer.tick()
                
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
        if self.game.match.timePassed < 25:
            return
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
        if self.game.match.timePassed < 20:
            return
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
                #if contains(self.level.botSpawnAreas[self.game.team.name], bot.position) and random.choice([True, False]):
                    #path.insert(0, self.game.team.flagScoreLocation)
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
