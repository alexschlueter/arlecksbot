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
from api.gameinfo import BotInfo
from api.gameinfo import MatchCombatEvent

# Import other modules
import random
#import png # for writing debug pngs
import networkx as nx # for graphs
import itertools
import math
import sys
import copy

#TODO Make bots more aggressive when time is running out and losing
#TODO Make bots more defensive when time is running out and winning

class ArlecksCommander(Commander):
    """
    Runners are responsible for infiltrating the enemy's defenses by flanking.
    Defenders watch the flag stand for intruders and flankers by positioning themselves accordingly.
    Midfielders try to provide map control by ganking and performing midfield objectives such as escorting and interception.  They may fall into other roles when needed.

    """
    
    def feq(self, f, s):
        return math.fabs(f - s) < 0.00000001
    
    def veq(self, f, s):
        return self.feq(f.x, s.x) and self.feq(f.y, s.y)
    
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

    def initialize(self):
        """
        Assign each bot a role.  Runners and defenders should default to 40%, and midfielders should default to 20%.
        Role counts should adapt throughout the game depending on how aggressive or defensive the enemy commander is.
        """
        self.verbose = True    # display the command descriptions next to the bot labels
        
        self.lastEventCount = 0
        self.numAllies = len(self.game.team.members)
        self.botDeathLocations = [] # stores a list of Vector2 objects of where bots died
        
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
        self.midEnemySpawn = self.game.enemyTeam.botSpawnArea[0].midPoint(self.game.enemyTeam.botSpawnArea[1])
        self.midOurSpawn = self.game.team.botSpawnArea[0].midPoint(self.game.team.botSpawnArea[1])

        dirToFlag = (self.game.enemyTeam.flag.position - self.game.team.flag.position)
        self.frontFlank = Vector2(dirToFlag.x, dirToFlag.y).normalized()
        self.leftFlank = Vector2(dirToFlag.y,-dirToFlag.x).normalized()
        self.rightFlank = Vector2(-dirToFlag.y,dirToFlag.x).normalized()
        
        # Create behavior tree   
        self.behaviorTrees = {}
        for bot in self.game.team.members:
            self.behaviorTrees[bot.name] = BotBehaviorTree(
                Selector([
                          Sequence([
                                    BotHasFlag(),
                                    Selector([
                                              Sequence([
                                                        EnemiesAreAlive(),
                                                        NotScoringOrFarAway(),
                                                        SneakToScore()
                                                        ]),
                                              RunToScore()
                                              ])
                                    ]),
                          Sequence([
                                    EnemiesAreAlive(),
                                    Selector([
                                              BlockingSequence([
                                                        BotIsHolding(),
                                                        AntiHold()
                                                        ]),
                                              ChooseAndApproachTarget(),
                                              BlockingSequence([
                                                        FirstTick(),
                                                        Spread()
                                                        ]),
                                              Selector([
                                                        Sequence([
                                                                  WeHaveFlag(),
                                                                  ChargeRandom()
                                                                  ]),
                                                        Selector([
                                                                  Sequence([
                                                                            AreMajority(),
                                                                            ChargeEnemyFlag()
                                                                            ]),
                                                                  AttackEnemyFlag()
                                                                  ])
                                                        ])
                                              ])
                                    ]),
                          BlockingSequence([
                                            NeedWaiter(),
                                            NearestToFlagSpawn(),
                                            WaitForFlag()
                                            ]),
                          Camp()
                          ]), 
                self,
                bot
            )

        self.makeGraph()
        self.sneakGraph.add_node("enemy_base")
        self.positions["enemy_base"] = None
        start, finish = self.level.botSpawnAreas[self.game.enemyTeam.name]
        for i, j in itertools.product(range(int(start.x), int(finish.x)), range(int(start.y), int(finish.y))):
            self.sneakGraph.add_edge("enemy_base", self.terrain[j][i], weight = 1.0)

        self.sneakGraph.add_node("base")
        self.positions["base"] = None
        start, finish = self.level.botSpawnAreas[self.game.team.name]
        for i, j in itertools.product(range(int(start.x), int(finish.x)), range(int(start.y), int(finish.y))):
            self.sneakGraph.add_edge("base", self.terrain[j][i], weight = 1.0)

        self.node_EnemyFlagIndex = self.getNodeIndex(self.game.team.flag.position)
        self.node_EnemyScoreIndex = self.getNodeIndex(self.game.enemyTeam.flagScoreLocation)

        # self.node_Bases = self.graph.add_vertex()
        # e = self.graph.add_edge(self.node_Bases, self.node_MyBase)
        # e = self.graph.add_edge(self.node_Bases, self.node_EnemyBase)

        vb2f = nx.shortest_path(self.sneakGraph, source="enemy_base", target=self.node_EnemyFlagIndex)
        try:
            if self.node_EnemyFlagIndex != self.node_EnemyScoreIndex:
                vf2s = nx.shortest_path(self.sneakGraph, source=self.node_EnemyFlagIndex, target=self.node_EnemyScoreIndex)
            else:
                vf2s = None
        except IndexError as e:
            vf2s = None
            sys.stdout.write(str(e) + '\n')
        #vb2s = nx.shortest_path(self.graph, source="enemy_base", target=self.node_EnemyScoreIndex)

        self.node_EnemyBaseToFlagIndex = "enemy_base_to_flag"
        self.sneakGraph.add_node(self.node_EnemyBaseToFlagIndex)
        self.positions["enemy_base_to_flag"] = None
        for vertex in vb2f:
            self.sneakGraph.add_edge(self.node_EnemyBaseToFlagIndex, vertex, weight = 1.0)
        
        if vf2s:
            self.node_EnemyFlagToScoreIndex = "enemy_flag_to_score" 
            self.sneakGraph.add_node(self.node_EnemyFlagToScoreIndex)
            self.positions["enemy_flag_to_score"] = None
            for vertex in vf2s:
                self.sneakGraph.add_edge(self.node_EnemyFlagToScoreIndex, vertex, weight = 1.0)
        
        self.node_EnemyBaseToScoreIndex = "enemy_base_to_score"
        self.sneakGraph.add_node(self.node_EnemyBaseToScoreIndex)
        self.positions["enemy_base_to_score"] = None
       # for vertex in vb2s:
       #     self.graph.add_edge(self.node_EnemyBaseToScoreIndex, vertex, weight = 1.0)

        ## node = self.makeNode(self.game.enemyTeam.flag.position)
        if vf2s:
            self.distances = nx.single_source_shortest_path_length(self.sneakGraph, self.node_EnemyFlagToScoreIndex)
        else:
            self.distances = nx.single_source_shortest_path_length(self.sneakGraph, self.node_EnemyBaseToFlagIndex)

        self.sneakGraph.remove_node("base")
        self.sneakGraph.remove_node("enemy_base")
        self.sneakGraph.remove_node(self.node_EnemyBaseToFlagIndex)
        if vf2s:
            self.sneakGraph.remove_node(self.node_EnemyFlagToScoreIndex)
        self.sneakGraph.remove_node(self.node_EnemyBaseToScoreIndex)
        self.updateEdgeWeights()
        
        spawnConnection = (self.midEnemySpawn - self.midOurSpawn)
        anker = self.midOurSpawn + spawnConnection / 2.5
        ambushVec = Vector2(spawnConnection.y, -1 * spawnConnection.x).normalized() + anker
        sys.stdout.write(str(spawnConnection) + ' ' + str(anker) + ' ' + str(ambushVec) + '\n')
        start = 100 * Vector2(spawnConnection.y, -1 * spawnConnection.x).normalized() + anker
        end = -100 * Vector2(spawnConnection.y, -1 * spawnConnection.x).normalized() + anker
        intersections = []
        intersect = self.lineIntersection(start, end, Vector2(0, 0), Vector2(0, self.level.height))
        if intersect:
            intersections.append(intersect)
        intersect = self.lineIntersection(start, end, Vector2(0, 0), Vector2(self.level.width, 0))
        if intersect:
            intersections.append(intersect)
        intersect = self.lineIntersection(start, end, Vector2(0, self.level.height), Vector2(self.level.width, self.level.height))
        if intersect:
            intersections.append(intersect)
        intersect = self.lineIntersection(start, end, Vector2(self.level.width, 0), Vector2(self.level.width, self.level.height))
        if intersect:
            intersections.append(intersect)
            
        sys.stdout.write(str(intersections) + '\n')
            
        self.spreadPositions = []
        for i in range(1, len(self.game.team.members) + 1):
            #sys.stdout.write(str(intersections[0] + (i / 10.0) * (intersections[1] - intersections[0])))
            self.spreadPositions.append(self.level.findNearestFreePosition(intersections[0] + (i / 10.0) * (intersections[1] - intersections[0])))
        sys.stdout.write(str(self.spreadPositions)+ '\n')

        self.rcampers = []
        tries = 0
        while tries < 2000 and len(self.rcampers) <= len(self.game.team.members):
            tries += 1
            #sys.stdout.write('rc ' + str(tries) + '\n')
            pos = self.level.findRandomFreePositionInBox((Vector2(self.game.enemyTeam.botSpawnArea[0].x - self.level.firingDistance * 2, self.game.enemyTeam.botSpawnArea[0].y - self.level.firingDistance * 2), Vector2(self.game.enemyTeam.botSpawnArea[1].x + self.level.firingDistance * 2, self.game.enemyTeam.botSpawnArea[1].y + self.level.firingDistance * 2)))
            if pos.distance(self.midEnemySpawn) > self.level.firingDistance and self.freeLoS(pos, (self.midEnemySpawn - pos).normalized() * self.level.firingDistance / 4.0):
                self.rcampers.append(pos)

        self.cmds = {}
        self.aliveEnemies = 0
        self.index = 0
        self.firstTick = True
        self.waiter = None
        self.botByFlagSpawnDistance = []

    def smartIssue(self, cmd, bot, pos, desc, lookAt = None):
        if bot in self.cmds and self.cmds[bot][0] is cmd and self.cmds[bot][1].distance(pos) < 10 * self.level.characterRadius and (cmd is commands.Charge or (not lookAt and not self.cmds[bot][2]) or (lookAt and self.cmds[bot][2] and self.cmds[bot][2].distance(lookAt) < 6 * self.level.characterRadius)):
            #sys.stdout.write(str(bot) + '\n')
            return
        else:
            self.cmds[bot] = (cmd, pos, lookAt)
            if cmd is commands.Attack:
                self.issue(cmd, bot, pos, lookAt, desc)
            else:
                self.issue(cmd, bot, pos, desc)
                
    def sneakTo(self, bot, dst, message = ''):
        # calculate the shortest path between the bot and the target using our weights
        srcIndex = self.getNodeIndex(bot.position)
        dstIndex = self.getNodeIndex(dst)
        pathNodes = nx.shortest_path(self.sneakGraph, srcIndex, dstIndex, 'weight')
    
        pathLength = len(pathNodes)
        if pathLength > 0:
            path = [self.positions[p] for p in pathNodes if self.positions[p]]
            if len(path) > 0:
                orderPath = path[::10]
                orderPath.append(path[-1]) # take every 10th point including last point
                self.issue(commands.Charge, bot, orderPath, description = message) 
                #self.paths[bot] = path    # store the path for visualization
    
    def freeLoS(self, start, end):
        vec = (end - start).normalized()
        vecInc = 0.5
        while (vec * vecInc).length() < (end - start).length():
            testPos = start + vec * vecInc 
            #print str(testPos)
            if self.level.blockHeights[int(testPos.x)][int(testPos.y)] >= 2:
                return False
            vecInc += 0.5
        return True
    
    def speedMods(self, state):
        if state is BotInfo.STATE_ATTACKING:
            return self.level.walkingSpeed
        elif state is BotInfo.STATE_CHARGING or state is BotInfo.STATE_MOVING:
            return self.level.runningSpeed
        else:
           return 0.0
    
    def tick(self):
        """
        Listen for events and run the bot's behavior tree.
        """
        for e in self.game.match.combatEvents[self.index:]:
            if e.type == MatchCombatEvent.TYPE_RESPAWN and e.subject in self.game.enemyTeam.members:
                self.aliveEnemies += 1
                self.waiter = None
                sys.stdout.write('enemies alive: ' + str(self.aliveEnemies) + '\n')
            elif e.type == MatchCombatEvent.TYPE_KILLED:
                if e.subject in self.game.enemyTeam.members:
                    self.aliveEnemies -= 1
                    if self.aliveEnemies is 0:
                        justAllDead = True
                    sys.stdout.write('enemies alive: ' + str(self.aliveEnemies) + '\n')
                elif e.subject in self.game.team.members:
                    self.behaviorTrees[e.subject.name].killed()
        self.index = len(self.game.match.combatEvents)
        
        for bot in copy.copy(self.cmds):
            if bot.state == BotInfo.STATE_DEAD:
                del self.cmds[bot]
        
        self.targets = set()
        if self.game.team.flag.carrier and self.game.team.flag.carrier.position:
            self.targets.add((self.game.team.flag.position, 0.0))
        if self.level.respawnTime - self.game.match.timeToNextRespawn <= 4.0:
            self.targets.add((self.midEnemySpawn, 0.0))
        for enemy in self.game.enemyTeam.members:
            if enemy.position is not None and enemy.health > 0:
                if enemy.facingDirection is not None and enemy.seenlast is not None and enemy.state is not None:
                    pos = self.level.findNearestFreePosition(enemy.position + enemy.facingDirection * (enemy.seenlast * self.speedMods(enemy.state) + 3))
                    if pos is not None:
                        self.targets.add((pos, enemy.seenlast))
                    else:
                        self.targets.add((enemy.position, enemy.seenlast))
                else:
                    #sys.stdout.write('dumb\n')
                    self.targets.add((enemy.position, 0.0))
        
        self.botByFlagSpawnDistance = sorted(self.game.bots_alive, key = lambda f: f.position.distance(self.game.enemyTeam.flagSpawnLocation))
        
        # run behavior tree
        for bot in self.game.bots_alive:
            if bot.state != BotInfo.STATE_SHOOTING and bot.state != BotInfo.STATE_TAKINGORDERS:
                self.behaviorTrees[bot.name].tick()

        self.firstTick = False


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

    def makeGraph(self):
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
    
        self.sneakGraph = g

    def updateEdgeWeights(self):
        blocks = self.level.blockHeights
        width, height = len(blocks), len(blocks[0])

        # update the weights in the graph based on the distance to the shortest path between the enemy flag and enemy score location

        for j in range(0, height):
            for i in range(0, width -1):
                a = self.terrain[j][i]
                b = self.terrain[j][i+1]
                if a and b:
                    #w = max(99999999 - (self.distances[a] + self.distances[b]), 0)
                    w = max(255 - 4.0 * (self.distances[a] + self.distances[b]), 0)
                    #sys.stdout.write(str(w) + ' ')
                    self.sneakGraph[a][b]['weight'] = w

        for j in range(0, height-1):
            for i in range(0, width):
                a = self.terrain[j][i]
                b = self.terrain[j+1][i]
                if a and b:
                    #w = max(99999999 - (self.distances[a] + self.distances[b]), 0)
                    w = max(255 - 4.0 * (self.distances[a] + self.distances[b]), 0)
                    #sys.stdout.write(str(w) + ' ')
                    self.sneakGraph[a][b]['weight'] = w

    def getNodeIndex(self, position):
        i = int(position.x)
        j = int(position.y)
        width = self.sneakGraph.graph["map_width"]
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

def botStateToStr(state):
    if state == BotInfo.STATE_ATTACKING:
        return 'attacking'
    elif state == BotInfo.STATE_CHARGING:
        return 'charging'
    elif state == BotInfo.STATE_DEFENDING:
        return 'defending'
    elif state == BotInfo.STATE_HOLDING:
        return 'holding'
    elif state == BotInfo.STATE_IDLE:
        return 'idle'
    elif state == BotInfo.STATE_MOVING:
        return 'moving'
    elif state == BotInfo.STATE_SHOOTING:
        return 'shooting'
    elif state == BotInfo.STATE_TAKINGORDERS:
        return 'taking orders'
    elif state == BotInfo.STATE_UNKNOWN:
        return 'unknown'

# Base class for bot behavior tree 
class BotBehaviorTree:
    def __init__(self, child=None, commander = None, bot = None):
        self.root = child
        self.root.parent = self
        self.commander_ = commander
        self.bot_ = bot

    def tick(self):
        self.root.tick()
        self.root.reset()
        
    def killed(self):
        if self.root.state == Node.STATE_RUNNING:
            self.root.cancel()
        
    def commander(self):
        return self.commander_
    
    def bot(self):
        return self.bot_

# Base Node classes
class Node:
    STATE_READY = 0
    STATE_RUNNING = 1
    STATE_SUCCEEDED = 2
    STATE_FAILED = 3
    STATE_ERROR = 4
    
    def __init__(self, children=[], parent=None):
        self.children = children
        self.parent = parent
        self.state = Node.STATE_READY

        for c in self.children:
            c.parent = self
    
    def tick(self):
        raise NotImplementedError("Can't call Node.run() without defining behavior.")

    def reset(self):
        if self.state != Node.STATE_RUNNING:
            self.state = Node.STATE_READY
        for c in self.children:
            c.reset()
    
    def cancel(self):
        self.state = Node.STATE_READY
        for c in self.children:
            if c.state is Node.STATE_RUNNING:
                c.cancel()
    
    def commander(self):
        return self.parent.commander()
    
    def bot(self):
        return self.parent.bot()

class Selector(Node):
    def tick(self):
        for c in range(len(self.children)):
            self.children[c].tick()
            if self.children[c].state is Node.STATE_RUNNING or self.children[c].state is Node.STATE_SUCCEEDED:
                for c2 in self.children[c + 1:len(self.children)]:
                    if c2.state is Node.STATE_RUNNING:
                        c2.cancel()
                self.state = self.children[c].state
                return

        self.state = Node.STATE_FAILED

class Sequence(Node):
    def tick(self):
        for c in range(len(self.children)):
            self.children[c].tick()
            if self.children[c].state is Node.STATE_RUNNING or self.children[c].state is Node.STATE_FAILED:
                for c2 in self.children[c + 1:len(self.children)]:
                    if c2.state is Node.STATE_RUNNING:
                        c2.cancel()
                self.state = self.children[c].state
                return
            
        self.state = Node.STATE_SUCCEEDED
        
class BlockingSequence(Node):
    def tick(self):
        self.state = Node.STATE_SUCCEEDED
        for c in self.children:
            if c.state is Node.STATE_RUNNING:
                c.tick()
                self.state = Node.STATE_RUNNING
                return
        for c in range(len(self.children)):
            self.children[c].tick()
            if self.children[c].state is Node.STATE_RUNNING or self.children[c].state is Node.STATE_FAILED:
                for c2 in self.children[c + 1:len(self.children)]:
                    if c2.state is Node.STATE_RUNNING:
                        c2.cancel()
                self.state = self.children[c].state
                return
        self.state = Node.STATE_SUCCEEDED
    
class Condition(Node):
    def tick(self):
        if self.test():
            self.state = Node.STATE_SUCCEEDED
        else:
            self.state = Node.STATE_FAILED
    
    def test(self):
        raise NotImplementedError("Can't call Condition.test() without defining condition.")

class TeamHasEnemyFlag(Condition):
    def test(self):
        return self.commander().game.enemyTeam.flag.carrier != None

class BotHasFlag(Condition):
    def test(self):
        return self.bot().flag
    
class EnemiesAreAlive(Condition):
    def test(self):
        return self.commander().aliveEnemies != 0
    
class BotIsHolding(Condition):
    def test(self):
        return self.bot().state == BotInfo.STATE_HOLDING
    
class WeHaveFlag(Condition):
    def test(self):
        return self.commander().game.enemyTeam.flag.carrier
    
class FirstTick(Condition):
    def test(self):
        return self.commander().firstTick
    
class AreMajority(Condition):
    def test(self):
        return self.commander().aliveEnemies * 2 <= len(self.commander().game.bots_alive)
    
class NeedWaiter(Condition):
    def test(self):
        return not self.commander().waiter
    
class NearestToFlagSpawn(Condition):
    def test(self):
        sys.stdout.write('NearestToFlagSpawn would be ' + self.commander().botByFlagSpawnDistance[0].name + ' and I am ' + self.bot().name + '\n')
        return not self.bot() is self.commander().botByFlagSpawnDistance[0]

class NotScoringOrFarAway(Condition):
    def test(self):
        return (self.bot() not in self.commander().cmds or self.commander().cmds[self.bot()][1] != self.commander().game.team.flagScoreLocation) or self.bot().position.distance(self.commander().game.team.flagScoreLocation) >= 2 * self.commander().level.firingDistance
    
"""class MultiTickBehavior(Node):
    def __init__(self, children=None, parent=None, blackboard=None):
        Node.__init__(self, children, parent, blackboard)
        self.patients = {}
        
    def tick(self):
        if self.bot() in self.patients:
            if self.finished():
                sys.stdout.write('fin mt ' + self.bot().name + '\n')
                del self.patients[self.bot()]
                return Node.STATE_SUCCEEDED
            else: 
                return Node.STATE_RUNNING
        elif self.treat():
            sys.stdout.write('treat mt ' + self.bot().name + '\n')
            if not self.bot() in self.patients:
                self.patients[self.bot()] = None
            return Node.STATE_RUNNING
        else:
            return Node.STATE_FAILED
        
    def cancel(self):
        if self.bot() in self.patients:
            del self.patients[self.bot()]
            
    def finished(self):
        raise NotImplementedError("Can't call MultiTickBehavior.finished() without definition")
    
    def treat(self):
        raise NotImplementedError("Can't call MultiTickBehavior.treat() without definition.")"""
    
class SneakToScore(Node):
    def tick(self):
        #sys.stdout.write('SneakToScore.tick(): bot ' + self.bot().name + ', flag ' + str(self.bot().flag) + '\n')
        if not self.bot().flag:
            sys.stdout.write(self.bot().name + ' scored\n')
            self.state = Node.STATE_SUCCEEDED
        elif self.state != Node.STATE_RUNNING or self.bot().state != BotInfo.STATE_CHARGING:
            self.commander().sneakTo(self.bot(), self.commander().game.team.flagScoreLocation, 'sneak score')
            self.state = Node.STATE_RUNNING
        
class RunToScore(Node):
    def tick(self):
        if not self.bot().flag:
            self.state = Node.STATE_SUCCEEDED
        elif self.state != Node.STATE_RUNNING or self.bot().state != BotInfo.STATE_CHARGING:
            self.commander().smartIssue(commands.Charge, self.bot(), self.commander().game.team.flagScoreLocation, 'fast score')
            self.state = Node.STATE_RUNNING
        
class AntiHold(Node):
    def __init__(self, children=[], parent=None):
        Node.__init__(self, children, parent)
        self.target, self.enemy = None, None
    
    def tick(self):
        if not self.target:
            if not self.bot().visibleEnemies:
                sys.stdout.write('fu')
            self.enemy = random.choice([b for b in self.bot().visibleEnemies])
            self.target = self.commander().level.findRandomFreePositionInBox((self.bot().position-5.0, self.bot().position+5.0))
            sys.stdout.write('anti hold: ' + str(self.bot().name) + ' with state ' + botStateToStr(self.bot().state) + ' held by ' + str(self.enemy.name) + '\n')
            self.commander().smartIssue(commands.Attack, self.bot(), self.target, 'anti hold', self.enemy.position)
            self.state = Node.STATE_RUNNING
        elif self.enemy.health <= 0 or self.bot().position.distance(self.target) < 1:
            sys.stdout.write('anti hold: ' + str(self.bot().name) + ' with state ' + botStateToStr(self.bot().state) + ' successfully broke hold by ' + str(self.enemy.name) + '\n')
            self.target, self.enemy = None, None
            self.state = Node.STATE_SUCCEEDED
        else:
            self.state = Node.STATE_RUNNING
            
    def cancel(self):
        Node.cancel(self)
        self.target, self.enemy = None, None
        
class ChooseAndApproachTarget(Node):
    def __init__(self, children=[], parent=None):
        Node.__init__(self, children, parent)
        self.target = None
    
    def tick(self):
        if not self.target:
            if self.commander().targets:
                bot = self.bot()
                # and (bot not in self.combats or self.combats[bot][1] + 4 < self.game.match.timePassed)
                kill = sorted(self.commander().targets, key = lambda f : f[0].distance(bot.position) + f[1])[0]
    
                if kill[0].distance(bot.position) + kill[1] < 1.5 * self.commander().level.firingDistance:
                    if kill[0].distance(bot.position) > self.commander().level.runningSpeed * 2.0:
                        #and (len(self.game.bots_alive) >= 2 * self.aliveEnemies or (len(knownTargets) >= self.aliveEnemies and len(self.game.bots_alive) >= self.aliveEnemies))
                        self.commander().smartIssue(commands.Charge, bot, kill[0], 'charge target')
                    else:
                        self.commander().smartIssue(commands.Attack, bot, kill[0], 'attack target')
                    self.target = kill
                    self.state = Node.STATE_RUNNING
                    return
            self.state = Node.STATE_FAILED
        elif self.target not in self.commander().targets:
            #sys.stdout.write(self.target[0].name + ' ' + str(self.target[0].health) + '\n')
            self.target = None
            self.state = Node.STATE_SUCCEEDED
        elif self.bot().position.distance(self.target[0]) < 1:
            self.commander().targets.remove(self.target)
            self.target = None
            self.state = Node.STATE_SUCCEEDED
        else:
            #sys.stdout.write(self.target[0].name + ' ' + str(self.target[0].health) + '\n')
            self.state = Node.STATE_RUNNING
 
    def cancel(self):
        Node.cancel(self)
        self.target = None
    
class ChargeRandom(Node):    
    def __init__(self, children=[], parent=None):
        Node.__init__(self, children, parent)
        self.target = None
        
    def tick(self):
        if not self.target or self.bot().state != BotInfo.STATE_CHARGING:
            self.target = self.commander().level.findRandomFreePositionInBox(self.commander().level.area)
            self.commander().smartIssue(commands.Charge, self.bot(), self.target, 'charge random')
            self.state = Node.STATE_RUNNING
        elif self.bot().position.distance(self.target) < 1:
            self.state = Node.STATE_SUCCEEDED
        else:
            self.state = Node.STATE_RUNNING
    
    def cancel(self):
        Node.cancel(self)
        self.target = None
    
class ChargeEnemyFlag(Node):    
    def tick(self):
        if self.commander().game.enemyTeam.flag.carrier:
            self.state = Node.STATE_SUCCEEDED
        elif self.state != Node.STATE_RUNNING or self.bot().state != BotInfo.STATE_CHARGING:
            self.commander().smartIssue(commands.Charge, self.bot(), self.commander().game.enemyTeam.flag.position, 'charge flag')
            self.state = Node.STATE_RUNNING
            
class AttackEnemyFlag(Node):    
    def tick(self):
        if self.commander().game.enemyTeam.flag.carrier:
            self.state = Node.STATE_SUCCEEDED
        elif self.state != Node.STATE_RUNNING or self.bot().state != BotInfo.STATE_ATTACKING:
            self.commander().smartIssue(commands.Attack, self.bot(), self.commander().game.enemyTeam.flag.position, 'attack flag')
            self.state = Node.STATE_RUNNING
    
class Camp(Node):
    def __init__(self, children=[], parent=None):
        Node.__init__(self, children, parent)
        self.target = None
    
    def tick(self):
        
        if self.target and self.bot().position.distance(self.target) < 2:
            if self.bot().state != BotInfo.STATE_DEFENDING:
                self.commander().issue(commands.Defend, self.bot(), self.commander().midEnemySpawn - self.bot().position, 'defend camp')
            self.state = Node.STATE_SUCCEEDED
        elif not self.target or self.bot().state != BotInfo.STATE_CHARGING:
            self.target = random.choice(self.commander().rcampers)
            self.commander().smartIssue(commands.Charge, self.bot(), self.target, 'charge camp')
            self.state = Node.STATE_RUNNING
        else:
            self.state = Node.STATE_RUNNING 
    
    def cancel(self):
        Node.cancel(self)
        self.target = None
        
class Spread(Node):
    def __init__(self, children=[], parent=None):
        Node.__init__(self, children, parent)
        self.target = None
    
    def tick(self):
        if not self.target:
            if not self.commander().spreadPositions:
                self.state = Node.STATE_FAILED
            else:
                self.target = self.commander().spreadPositions[0]
                del self.commander().spreadPositions[0]
                self.commander().smartIssue(commands.Charge, self.bot(), self.target, 'spread')
                self.state = Node.STATE_RUNNING
        elif self.bot().position.distance(self.target) < 1:
            self.state = Node.STATE_SUCCEEDED
            self.target = None
        else:
            self.state = Node.STATE_RUNNING 
    
    def cancel(self):
        Node.cancel(self)
        self.target = None
        
class WaitForFlag(Node):
    def tick(self):
        if self.bot().position.distance(self.commander().game.enemyTeam.flagSpawnLocation) < 1:
            self.state = Node.STATE_RUNNING
            self.commander().issue(commands.Defend, self.bot(), self.commander().midEnemySpawn - self.bot().position, description = 'wait for flag')
        else:
            if self.state != Node.STATE_RUNNING or self.bot().state != BotInfo.STATE_CHARGING:
                self.commander().smartIssue(commands.Charge, self.bot(), self.commander().game.enemyTeam.flagSpawnLocation, 'charge flag spawn')
            self.state = Node.STATE_RUNNING
        self.commander().waiter = self.bot()
        
    def cancel(self):
        Node.cancel(self)
        self.commander().waiter = None