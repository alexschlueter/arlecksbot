#!/usr/bin/env python2

# Name:  SleekoCommander
# Author:  Nick Caplinger (SleekoNiko)
# Dependencies:  numpy, pypng

# Ideas:
# control the midfield with gankers
  #1. Ambush flag carriers by predicting their path to the flag stand and whether or not they can intercept
  #2. Camp the enemy spawn
  #3. Actively search around points of interest to gain map awareness

# Import AI Sandbox API:
from api import Commander
from api import commands
from api import Vector2

# Import other modules
import random
#import png # for writing debug pngs
import networkx as nx # for graphs
import itertools
import math

#TODO Make bots more aggressive when time is running out and losing
#TODO Make bots more defensive when time is running out and winning

class SleekoCommander(Commander):
    """
    Runners are responsible for infiltrating the enemy's defenses by flanking.
    Defenders watch the flag stand for intruders and flankers by positioning themselves accordingly.
    Midfielders try to provide map control by ganking and performing midfield objectives such as escorting and interception.  They may fall into other roles when needed.

    """

    def initialize(self):
        """
        Assign each bot a role.  Runners and defenders should default to 40%, and midfielders should default to 20%.
        Role counts should adapt throughout the game depending on how aggressive or defensive the enemy commander is.
        """
        self.verbose = True    # display the command descriptions next to the bot labels
        
        self.lastEventCount = 0
        self.numAllies = len(self.game.team.members)
        self.botDeathLocations = [] # stores a list of Vector2 objects of where bots died

        self.makeRunnerGraph()
        
        self.runners = [] # 40%
        self.defenders = [] # 40%
        self.midfielders = [] # 20%

        ourSpawn = self.game.team.botSpawnArea[0]
        theirSpawn = self.game.enemyTeam.botSpawnArea[0]
        # if their spawn is closer to our flag than ours is
        # attacking will probably be easy, so get more defenders
        if distTo(theirSpawn, self.game.team.flag.position) < distTo(ourSpawn, self.game.team.flag.position):
            # roughly half attackers/defenders
            self.desiredRunners = math.ceil(self.numAllies * .5)
            self.desiredDefenders = math.ceil(self.numAllies * .5)            
        else:
            # Few defenders and the rest are attackers
            defPercent = .20
            self.desiredDefenders = math.ceil(self.numAllies * defPercent)
            self.desiredRunners = math.ceil(self.numAllies * (1 - defPercent))

        # Assign roles
        for bot in self.game.team.members:
            if len(self.runners) < self.desiredRunners:
                self.runners.append(bot)
            else:
                self.defenders.append(bot)

        # TODO calculate for more than 2 flags
        self.midPoint = (self.game.team.botSpawnArea[0] + self.game.enemyTeam.flag.position) / 2.0

        dirToFlag = (self.game.enemyTeam.flag.position - self.game.team.flag.position)
        self.frontFlank = Vector2(dirToFlag.x, dirToFlag.y).normalized()
        self.leftFlank = Vector2(dirToFlag.y,-dirToFlag.x).normalized()
        self.rightFlank = Vector2(-dirToFlag.y,dirToFlag.x).normalized()
        
        # Create behavior tree
        self.behaviorTree = BotBehaviorTree(
            Selector([
                    Sequence([
                            BotIsRunner(),
                            Selector([
                                    Sequence([
                                            BotHasFlag(),
                                            RunToScoreZone()
                                            ]),
                                    Sequence([
                                            AllyHasFlag(),
                                            SecureEnemyFlagObjective()
                                            ]),
                                    Sequence([ 
                                            Inverter(TeamHasEnemyFlag()), 
                                            #SmartApproachFlag()
                                            Selector([
                                                    Sequence([
                                                            NearEnemyFlag(),
                                                            Selector([
                                                                    Sequence([
                                                                            EnemiesAreAlive(),
                                                                            AttackFlag()
                                                                            ]),
                                                                    ChargeFlag()
                                                                    ])
                                                            ]),
                                                    ChargeToFlagFlank()
                                                    ])
                                            ])
                                    ])
                            ]),
                    Sequence([
                            BotIsDefender(),
                            Selector([
                                    Sequence([
                                            BotHasFlag(),
                                            RunToScoreZone()
                                            ]),
                                    Sequence([
                                            OurFlagIsInBase(),
                                            SecureOurFlagStand()
                                            ]),
                                    Sequence([
                                            OurFlagIsOnOurHalf(),
                                            SecureOurFlag()
                                            ]),
                                    Sequence([
                                            SecureOurFlagStand()
                                            ])
                                    ])
                            ])
                    ])
        )

        # Set some blackboard data
        self.behaviorTree.root.blackboard = {}
        self.behaviorTree.root.blackboard['commander'] = self

        # I was using a png file for output
        #bt = getVonNeumannNeighborhood((int(self.game.team.flagSpawnLocation.x), int(self.game.team.flagSpawnLocation.y)), self.level.blockHeights, int(self.level.firingDistance))
        #createPngFromBlockTuples(bt, (self.level.width, self.level.height))
        #createPngFromMatrix(bt, (self.level.width, self.level.height))

        # Determine safest positions for flag defense
        self.secureFlagDefenseLocs = self.getMostSecurePositions(Vector2(self.game.team.flagSpawnLocation.x, self.game.team.flagSpawnLocation.y))
        self.secureEnemyFlagLocs = self.getMostSecurePositions(Vector2(self.game.enemyTeam.flagSpawnLocation.x, self.game.enemyTeam.flagSpawnLocation.y))

    def tick(self):
        """
        Listen for events and run the bot's behavior tree.
        """
        
        # listen for events
        if len(self.game.match.combatEvents) > self.lastEventCount:
            lastCombatEvent = self.game.match.combatEvents[-1]
            #self.log.info('event:'+str(lastCombatEvent.type))
            # if lastCombatEvent.instigator is not None:
            #     print "event:%d %f %s %s" % (lastCombatEvent.type,lastCombatEvent.time,lastCombatEvent.instigator.name,lastCombatEvent.subject.name)
            # else:
            #     print "event:%d %f" % (lastCombatEvent.type,lastCombatEvent.time)

            if lastCombatEvent.type == lastCombatEvent.TYPE_KILLED:
                if lastCombatEvent.subject in self.game.team.members:
                    self.botDeathLocations.append(lastCombatEvent.subject.position)
                    #self.updateRunnerGraph()
            self.lastEventCount = len(self.game.match.combatEvents)


        # run behavior tree
        for bot in self.game.bots_alive:
            self.behaviorTree.root.blackboard['bot'] = bot
            self.behaviorTree.run()



    def shutdown(self):
        scoreDict = self.game.match.scores
        myScore = scoreDict[self.game.team.name]
        theirScore = scoreDict[self.game.enemyTeam.name]

        if myScore < theirScore:
            self.log.info("We lost! Final score: " + str(myScore) + "-" + str(theirScore))
        
    """
    Returns most secure positions by using von Neumann neighborhood where r = firingDistance + 2
    """
    def getMostSecurePositions(self,secLoc):
        levelSize = (self.level.width, self.level.height)
        width, height = levelSize
        potPosits = [[0 for y in xrange(height)] for x in xrange(width)]
        neighbors = getVonNeumannNeighborhood((int(secLoc.x), int(secLoc.y)), self.level.blockHeights, int(self.level.firingDistance)+2)
        securePositions = []
        
        for n in neighbors:
            # use raycasting to test whether or not this position can see the flag
            # if it can't, automatically set it to 0
            x,y = n

            if self.level.blockHeights[x][y] >= 2:
                potPosits[x][y] = 50
            else:
                potPosits[x][y] = 255
                
            if potPosits[x][y] == 255:
                numWallCells = numAdjCoverBlocks(n, self.level.blockHeights)
                numWallCells += numAdjMapWalls(n, levelSize)
                #print numWallCells
                if numWallCells == 0:
                    potPosits[x][y] = 128
                if potPosits[x][y] == 255:
                    # make sure they have LOS with the flag
                    goodLOS = True
                    lookVec = Vector2(x+0.5,y+0.5) - (secLoc + Vector2(.5,.5))
                    lookVecNorm = lookVec.normalized()
                    vecInc = .1
                    while vecInc < lookVec.length():
                        testPos = secLoc + lookVecNorm * vecInc
                        #print str(testPos)
                        if self.level.blockHeights[int(testPos.x)][int(testPos.y)] >= 2:
                            goodLOS = False
                            break
                        vecInc += .1
                    if not goodLOS:
                        potPosits[x][y] = 128
                    else:
                        securePositions.append(n)
        #createPngFromMatrix(potPosits, levelSize)
        
        return sorted(securePositions, key = lambda p: numAdjMapWalls(p, levelSize)*4 + numAdjCoverBlocksWeighted(p, self) + distTo(Vector2(p[0],p[1]), secLoc)/self.level.firingDistance, reverse = True)
                            
                            
    def getFlankingPosition(self, bot, target):
        flanks = [target + f * self.level.firingDistance for f in [self.leftFlank, self.rightFlank]]
        options = map(lambda f: self.level.findNearestFreePosition(f), flanks)
        #return sorted(options, key = lambda p: (bot.position - p).length())[0]
        return random.choice(options)

    # return number of living enemies
    def numAliveEnemies(self):
        livingEnemies = 0
        for bot in self.game.enemyTeam.members:
            if bot.health != None and bot.health > 0:
                livingEnemies += 1
        return livingEnemies

    def makeRunnerGraph(self):
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
    
        self.runnerGraph = g

    def updateRunnerGraph(self):
        blocks = self.level.blockHeights
        width, height = len(blocks), len(blocks[0])

        # update the weights based on the distance

        for j in range(0, height):
            for i in range(0, width -1):
                a = self.terrain[j][i]
                b = self.terrain[j][i+1]
                if a and b:
                    w = max(255 - 4*(self.distances[a] + self.distances[b]), 0)
                    self.graph[a][b]['weight'] = w

        for j in range(0, height-1):
            for i in range(0, width):
                a = self.terrain[j][i]
                b = self.terrain[j+1][i]
                if a and b:
                    w = max(255 - 4*(self.distances[a] + self.distances[b]), 0)
                    self.graph[a][b]['weight'] = w
    
    def getNodeIndex(self, position):
        i = int(position.x)
        j = int(position.y)
        width = self.runnerGraph.graph["map_width"]
        return i+j*width

# Helper functions
def distTo(pos1, pos2):
    return (pos1 - pos2).length()

# used for intercepting enemy flag runners
def canInterceptTarget(bot, target, targetGoal):  
    return distTo(bot, targetGoal) < distTo(target, targetGoal)

# Returns number of blocks that are adjacent that can be used as cover at a given position
def numAdjCoverBlocks(cell, blockHeights):
    adjCells = getVonNeumannNeighborhood(cell, blockHeights, 1)
    numWallCells = 0
    for aCell in adjCells:
        aCellX, aCellY = aCell
        if blockHeights[aCellX][aCellY] >= 2:
            numWallCells += 1
    return numWallCells

# prioritize cells that have cover from their spawn
def numAdjCoverBlocksWeighted(cell, cmdr):
    adjCells = getVonNeumannNeighborhood(cell, cmdr.level.blockHeights, 1)
    # get distances of cells to their spawn
    spawnPoint = cmdr.game.enemyTeam.botSpawnArea[0]
    cellDistances = [distTo(spawnPoint, Vector2(x[0] + .5, x[1] + .5)) for x in adjCells]
    cellDistData = sorted(zip(adjCells, cellDistances), key = lambda x: x[1], reverse = True)
    
    wallScore = 0
    for i, aCell in enumerate([x[0] for x in cellDistData]):
        if not aCell == cell:
            aCellX, aCellY = aCell
            if cmdr.level.blockHeights[aCellX][aCellY] >= 2:
                wallScore += i
    return wallScore

# Tests to see approx. how far we can go in a direction until hitting a wall
def unblockedDistInDir(startPos, direction, commander):
    testPos = startPos
    while withinLevelBounds(testPos, (commander.level.width, commander.level.height)):
        if commander.level.blockHeights[int(testPos.x)][int(testPos.y)] < 2:
            testPos = testPos + direction/2
        else:
            break

    return distTo(startPos, testPos)

# Returns true if the cell position is within level bounds, false otherwise
def withinLevelBounds(pos, levelSize):
    return pos.x >= 0 and pos.y >= 0 and pos.x < levelSize[0] and pos.y < levelSize[1]

# Returns the number of adjacent map walls
def numAdjMapWalls(cell, mapSize):
    adjWalls = 0
    x,y = cell
    width,height = mapSize

    if x == 0 or x == width-1:
        adjWalls += 1
    if y == 0 or y == height-1:
        adjWalls += 1
    return adjWalls
    
# Returns the von Neumann Neighborhood of the cell of specified range as a list of tuples (x,y)
# http://mathworld.wolfram.com/vonNeumannNeighborhood.html
def getVonNeumannNeighborhood(cell, cells, r): # where cell is a tuple, cells is a 2D list, and r is the range
    newCells = [] # list of tuples
    for x, cx in enumerate(cells):
        for y, cy in enumerate(cx):
            if abs(x - cell[0]) + abs(y - cell[1]) <= r:
                newCells.append((x,y))
    return newCells

def createPngFromBlockTuples(tupleList, levelSize, name='pngtest.png'): # where tupleList is a list of block position tuples, levelSize is a tuple of x,y level size
    width, height = levelSize
    pngList = [[0 for y in xrange(height)] for x in xrange(width)]
    for t in tupleList: # I could probably use list comprehensions here
        print str(t)
        x,y = t
        column = pngList[y]
        column[x] = 255
    image = png.from_array(pngList, mode='L') # grayscale
    image.save(name)

def createPngFromMatrix(matrix, levelSize, name='pngtest.png'):
    width, height = levelSize
    transposedMatrix = [[row[i] for row in matrix] for i in xrange(height)]
    image = png.from_array(transposedMatrix, mode='L')
    image.save(name)


# Base class for bot behavior tree 
class BotBehaviorTree:
    def __init__(self, child=None):
        self.root = child

    def run(self):
        self.root.run()

# Base task classes
class Task:
    def __init__(self, children=None, parent=None, blackboard=None):
        #holds the children of task
        self.children = children
        self.blackboard = blackboard
        self.parent = parent

        if self.children != None:
            for c in self.children:
                c.parent = self
    
    # returns True for success and False for failure
    def run(self):
        raise NotImplementedError("Can't call Task.run() without defining behavior.")

    # Get data from the dict blackboard
    def getData(self, name):
        if self.blackboard == None or (self.blackboard != None and not name in blackboard):
            testParent = self.parent
            while testParent != None:
                if testParent.blackboard != None and name in testParent.blackboard:
                    return testParent.blackboard[name]
                else:
                    testParent = testParent.parent
            # We went through the parents and didn't find anything, so return None
            return None
        else:
            return blackboard[name]

class Selector (Task):
    def run(self):
        for c in self.children:
            if c.run():
                return True

        return False

class Sequence (Task):
    def run(self):
        for c in self.children:
            if not c.run():
                return False

        return True

# Decorators

class Decorator (Task):
    def __init__(self, child=None,parent=None,blackboard=None):
        self.child = child
        self.parent = parent
        self.blackboard = blackboard

        self.child.parent = self

class Inverter (Decorator):
    def run(self):
        return not self.child.run()

# Now onto tasks specific to our program:
class BotIsRunner(Task):
    def run(self):
        return self.getData('bot') in self.getData('commander').runners

class BotIsDefender(Task):
    def run(self):
        return self.getData('bot') in self.getData('commander').defenders

class TeamHasEnemyFlag(Task):
    def run(self):
        commander = self.getData('commander')
        return commander.game.enemyTeam.flag.carrier != None

class BotHasFlag(Task):
    def run(self):
        return self.getData('bot') == self.getData('commander').game.enemyTeam.flag.carrier

class LookRandom(Task):
    def run(self):
        self.getData('commander').issue(commands.Defend, self.getData('bot'), Vector2(random.random()*2 - 1, random.random()*2 - 1), description = 'Looking in random direction')
        return True

class ChargeFlag(Task):
    def run(self):
        bot = self.getData('bot')
        level = self.getData('commander').level
        if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_CHARGING and bot.state != bot.STATE_TAKINGORDERS:
            self.getData('commander').issue(commands.Charge, self.getData('bot'), self.getData('commander').game.enemyTeam.flag.position, description = 'Rushing enemy flag')
        return True

class SmartApproachFlag(Task):
    def run(self):
        bot = self.getData('bot')
        cmdr = self.getData('commander')

        if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_CHARGING and bot.state != bot.STATE_TAKINGORDERS:
            dst = cmdr.game.enemyTeam.flag.position
            message = "Intelligently approaching flag?"
            # calculate the shortest path between the bot and the target using our weights
            srcIndex = cmdr.getNodeIndex(bot.position)
            dstIndex = cmdr.getNodeIndex(dst)
            pathNodes = nx.shortest_path(cmdr.runnerGraph, srcIndex, dstIndex, 'weight')

            pathLength = len(pathNodes)
            if pathLength > 0:
                path = [cmdr.positions[p] for p in pathNodes if cmdr.positions[p]]
                if len(path) > 0:
                    orderPath = path[::10]
                    orderPath.append(path[-1]) # take every 10th point including last point
                    cmdr.issue(commands.Charge, bot, orderPath, description = message) 

class ChargeToFlagFlank(Task):
    def run(self):
        bot = self.getData('bot')
        level = self.getData('commander').level
        if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_CHARGING and bot.state != bot.STATE_TAKINGORDERS:
            flankPos = self.getData('commander').getFlankingPosition(bot, self.getData('commander').game.enemyTeam.flag.position)
            self.getData('commander').issue(commands.Charge, self.getData('bot'), flankPos, description = 'Rushing enemy flag via flank')
        return True


class AttackFlag(Task):
    def run(self):
        bot = self.getData('bot')
        cmdr = self.getData('commander')
        if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_ATTACKING and bot.state != bot.STATE_TAKINGORDERS:
            cmdr.issue(commands.Attack, bot, cmdr.game.enemyTeam.flag.position, description = 'Attacking enemy flag')
        return True    

class WithinShootingDistance(Task):
    def __init__(self):
        self.shootingDistance = self.getData('commander').level.firingDistance

    def run(self):
        return distTo(self.getData('bot').position, self.getData('targetPos')) < self.shootingDistance

class RunToScoreZone(Task):
    def run(self):
        bot = self.getData('bot')
        if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_CHARGING and bot.state != bot.STATE_TAKINGORDERS:        
            self.getData('commander').issue(commands.Charge, self.getData('bot'), self.getData('commander').game.team.flagScoreLocation, description = 'Taking their flag home')
        return True

class AllyHasFlag(Task):
    def run(self):
        for b in self.getData('commander').game.bots_alive:
            if b == self.getData('commander').game.enemyTeam.flag.carrier:
                return True
        return False

class SecureEnemyFlagObjective(Task):
    def run(self):
        bot = self.getData('bot')
        cmdr = self.getData('commander')
        flagSpawnLoc = cmdr.game.enemyTeam.flagSpawnLocation
        flagScoreLoc = cmdr.game.enemyTeam.flagScoreLocation

        # secure their flag spawn or their flag capture zone; whichever is closer
        flagSpawnDist = distTo(bot.position, flagSpawnLoc)
        capZoneDist = distTo(bot.position, flagScoreLoc)

        secureLoc = None
        secureDist = flagSpawnDist
        if flagSpawnDist < capZoneDist:
            secureLoc = flagSpawnLoc
            secureDist = flagSpawnDist
        else:
            secureLoc = flagScoreLoc
            secureDist = capZoneDist
        
        if secureDist < 2:
            if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_DEFENDING and bot.state != bot.STATE_TAKINGORDERS:
                # TODO face direction(s) that the attackers will most likely come from
                direction = (cmdr.midPoint - bot.position).normalized() + (random.random() - 0.5)
                dirLeft = Vector2(-direction.y, direction.x)
                dirRight = Vector2(direction.y, -direction.x)
                cmdr.issue(commands.Defend, bot, [(direction, 1.0), (dirLeft, 1.0), (direction, 1.0), (dirRight, 1.0)], description = 'Keeping flag objective secure')
        else:
            enemiesAlive = False
            for b in cmdr.game.enemyTeam.members:
                if b.health != None and b.health > 0:
                    enemiesAlive = True
                    break

            if enemiesAlive:
                if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_ATTACKING and bot.state != bot.STATE_TAKINGORDERS:
                    cmdr.issue(commands.Attack, bot, secureLoc, description = 'Moving to secure enemy flag objective')
            else:
                if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_CHARGING and bot.state != bot.STATE_TAKINGORDERS:
                    cmdr.issue(commands.Charge, bot, secureLoc, description = 'Charging to secure enemy flag objective')                
        return True

class NearEnemyFlag(Task):
    def run(self):
        bot = self.getData('bot')
        return distTo(bot.position, self.getData('commander').game.enemyTeam.flag.position) < self.getData('commander').level.firingDistance * 1.5

class EnemiesAreAlive(Task):
    def run(self):
        for bot in self.getData('commander').game.enemyTeam.members:
            if bot.health != None and bot.health > 0:
                return True
        return False

# Defender bot code
class OurFlagIsInBase(Task):
    def run(self):
        ourFlag = self.getData('commander').game.team.flag
        ourFlagSpawnLoc = self.getData('commander').game.team.flagSpawnLocation
        return distTo(ourFlag.position, ourFlagSpawnLoc) < 3

class OurFlagIsOnOurHalf(Task):
    def run(self):
        cmdr = self.getData('commander')
        flagDistToSpawn = distTo(cmdr.game.team.flag.position, cmdr.game.team.flagSpawnLocation)
        flagDistToScore = distTo(cmdr.game.team.flag.position, cmdr.game.enemyTeam.flagScoreLocation)
        return flagDistToSpawn < flagDistToScore

class SecureOurFlag(Task):
    def run(self):
        cmdr = self.getData('commander')
        bot = self.getData('bot')
        secureLoc = cmdr.game.team.flag.position
        secureDist = distTo(bot.position, secureLoc)
        
        if secureDist < 2:
            if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_DEFENDING and bot.state != bot.STATE_TAKINGORDERS:
                # TODO face direction(s) that the attackers will most likely come from
                direction = (cmdr.midPoint - bot.position).normalized() + (random.random() - 0.5)
                dirLeft = Vector2(-direction.y, direction.x)
                dirRight = Vector2(direction.y, -direction.x)
                cmdr.issue(commands.Defend, bot, [(direction, 1.0), (dirLeft, 1.0), (direction, 1.0), (dirRight, 1.0)], description = 'Keeping our flag secure')
        else:
            enemiesAlive = False
            for b in cmdr.game.enemyTeam.members:
                if b.health != None and b.health > 0:
                    enemiesAlive = True
                    break

            if enemiesAlive:
                if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_ATTACKING and bot.state != bot.STATE_TAKINGORDERS:
                    cmdr.issue(commands.Attack, bot, secureLoc, description = 'Moving to secure our flag')
            else:
                if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_CHARGING and bot.state != bot.STATE_TAKINGORDERS:
                    cmdr.issue(commands.Charge, bot, secureLoc, description = 'Charging to secure our flag')

        return True

class SecureOurFlagStand(Task):
    def run(self):
        cmdr = self.getData('commander')
        bot = self.getData('bot')

        safeLocs = cmdr.secureFlagDefenseLocs
        secureLoc = None
        secureDist = None
        chosenLoc = None

        if len(safeLocs) == 0:
            secureLoc = cmdr.game.team.flagSpawnLocation
        else:
            #double check to make sure we have a good position; note that this shouldn't really be done here
            for i, sLoc in enumerate(safeLocs):
                if distTo(Vector2(sLoc[0] + .5, sLoc[1] + .5), cmdr.game.team.flagSpawnLocation + Vector2(.5,.5)) <= cmdr.level.firingDistance - 1:
                    chosenLoc = safeLocs[i]
                    break
            if chosenLoc == None:
                # Give up
                chosenLoc = secureLoc

            secureLoc = Vector2(chosenLoc[0] + 0.5, chosenLoc[1] + 0.5)
            secureDist = distTo(bot.position, secureLoc)

            if secureDist < .5:
                if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_DEFENDING and bot.state != bot.STATE_TAKINGORDERS:
                    # face away from adjacent walls
                    directions = []
                    secureLocCell = (int(secureLoc.x), int(secureLoc.y))

                    for aCell in getVonNeumannNeighborhood(secureLocCell, cmdr.level.blockHeights, 1):
                        if aCell != secureLocCell:
                            if cmdr.level.blockHeights[aCell[0]][aCell[1]] <= 1:
                                aimDir = Vector2(aCell[0], aCell[1]) - Vector2(secureLocCell[0], secureLocCell[1])
                                aimDist = unblockedDistInDir(secureLoc, aimDir, cmdr)
                                if aimDist > cmdr.level.firingDistance / 3:
                                    directions.append(aimDir.normalized())

                    if len(directions) > 0:
                        cmdr.issue(commands.Defend, bot, directions, description = 'Keeping our flag stand secure')
                    else:
                        cmdr.issue(commands.Defend, bot, (cmdr.game.team.flagSpawnLocation - bot.position).normalized(), description = 'Keeping our flag stand secure')    
            else:
                enemiesAlive = False
                for b in cmdr.game.enemyTeam.members:
                    if b.health != None and b.health > 0:
                        enemiesAlive = True
                        break

                if enemiesAlive:
                    if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_ATTACKING and bot.state != bot.STATE_TAKINGORDERS:
                        cmdr.issue(commands.Attack, bot, secureLoc, description = 'Moving to secure our flag stand')
                else:
                    if bot.state != bot.STATE_SHOOTING and bot.state != bot.STATE_CHARGING and bot.state != bot.STATE_TAKINGORDERS:
                        cmdr.issue(commands.Charge, bot, secureLoc, description = 'Charging to secure our flag stand')
        return True
