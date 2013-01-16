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

class ArlecksCommander(Commander):
    
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
    
    def vecAngle(self, a, b):
        return math.atan2( a.x*b.y - a.y*b.x, a.x*b.x + a.y*b.y )
    
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
    
    def freeLoS(self, start, end):
        vec = (end - start).normalized()
        vecInc = 0.5
        while (vec * vecInc).length() < (end - start).length():
            testPos = start + vec * vecInc 
            #print str(testPos)
            if self.level.blockHeights[int(testPos.x)][int(testPos.y)] >= 2:
                #sys.stdout.write(str(start) + ' ' + str(end) + ' ' + (str(testPos)) + '\n')
                return False
            vecInc += 0.5
        return True
                        
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
                        
    def recursePaths(self, p, blocked, deadlines, visited = [], pointsAndLinesByEdge = dict(), depth = 0):
        if depth > 300:
            raise RuntimeError
        if p.x >= 0 and p.y >= 0 and p.x < self.level.width and p.y < self.level.height and not p in visited:
            visited.append(p)
            for block in blocked:
                if p.x >= block.x and p.x <= block.x + 1 and p.y >= block.y and p.y <= block.y + 1:
                    return
            for edge, contacts in deadlines.iteritems():
                for contact in contacts:
                    if self.intersects(edge, contact, p):
                        if edge in pointsAndLinesByEdge:
                            pointsAndLinesByEdge[edge].append((p, contact))
                        else:
                            pointsAndLinesByEdge[edge] = [(p, contact)]
                        return
            recalc= []
            for edge in deadlines.keys():
                if p.distance(edge) <= self.level.firingDistance and not self.whoBlocks(blocked, p, edge):
                    #sys.stdout.write('removed: ' + str(p) + ' '  + str(edge) + '\n')
                    del deadlines[edge]
                    if edge in pointsAndLinesByEdge:
                        for pointAndLine in pointsAndLinesByEdge[edge]:
                            recalc.append(pointAndLine[0])
                            visited.remove(pointAndLine[0])
                        del pointsAndLinesByEdge[edge]
            for re in recalc:
                self.recursePaths(re, blocked, deadlines, visited, pointsAndLinesByEdge, depth + 1)
                    
            
            
            self.recursePaths(Vector2(p.x - 1, p.y), blocked, deadlines, visited, pointsAndLinesByEdge, depth + 1)
            self.recursePaths(Vector2(p.x, p.y - 1), blocked, deadlines, visited, pointsAndLinesByEdge, depth + 1)
            self.recursePaths(Vector2(p.x + 1, p.y), blocked, deadlines, visited, pointsAndLinesByEdge, depth + 1)
            self.recursePaths(Vector2(p.x, p.y + 1), blocked, deadlines, visited, pointsAndLinesByEdge, depth + 1)
            sys.stdout.write(str(depth) + '\n')
                        
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
                        #w = max(99999999 - (self.distances[a] + self.distances[b]), 0)
                        w = max(255 - 4.0 * (self.distances[a] + self.distances[b]), 0)
                        #sys.stdout.write(str(w) + ' ')
                        self.graphSneak[a][b]['weight'] = w
    
            for j in range(0, height-1):
                for i in range(0, width):
                    a = self.terrain[j][i]
                    b = self.terrain[j+1][i]
                    if a and b:
                        #w = max(99999999 - (self.distances[a] + self.distances[b]), 0)
                        w = max(255 - 4.0 * (self.distances[a] + self.distances[b]), 0)
                        #sys.stdout.write(str(w) + ' ')
                        self.graphSneak[a][b]['weight'] = w
                                
    def initialize(self):
        self.verbose = True
        #sys.stdout.write(str(self.game.enemyTeam.botSpawnArea[1]) + ' ' + str(self.level.characterRadius) + '\n')
        self.midEnemySpawn = self.game.enemyTeam.botSpawnArea[0].midPoint(self.game.enemyTeam.botSpawnArea[1])
        self.midMySpawn = self.game.team.botSpawnArea[0].midPoint(self.game.team.botSpawnArea[1])
        visited, islandEdges, islandOuter = [], [], []
        for x in range(0, len(self.level.blockHeights)):
            for y in range(0, len(self.level.blockHeights[x])):
                _, edges, island = self.recurseNeighbours(x, y, visited)
                if edges:
                    islandEdges.append(edges)
                    islandOuter.append(island)
                    
                    
        #sys.stdout.write(str(islandEdges) + '\n' + str(islandOuter) + '\n')
                   
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
        
        self.makeGraphs()
        self.graphSneak.add_node("enemy_base")
        self.positions["enemy_base"] = None
        start, finish = self.level.botSpawnAreas[self.game.enemyTeam.name]
        for i, j in itertools.product(range(int(start.x), int(finish.x)), range(int(start.y), int(finish.y))):
            self.graphSneak.add_edge("enemy_base", self.terrain[j][i], weight = 1.0)

        self.graphSneak.add_node("base")
        self.positions["base"] = None
        start, finish = self.level.botSpawnAreas[self.game.team.name]
        for i, j in itertools.product(range(int(start.x), int(finish.x)), range(int(start.y), int(finish.y))):
            self.graphSneak.add_edge("base", self.terrain[j][i], weight = 1.0)

        self.node_EnemyFlagIndex = self.getNodeIndex(self.game.team.flag.position)
        self.node_EnemyScoreIndex = self.getNodeIndex(self.game.enemyTeam.flagScoreLocation)

        # self.node_Bases = self.graph.add_vertex()
        # e = self.graph.add_edge(self.node_Bases, self.node_MyBase)
        # e = self.graph.add_edge(self.node_Bases, self.node_EnemyBase)

        vb2f = nx.shortest_path(self.graphSneak, source="enemy_base", target=self.node_EnemyFlagIndex)
        #vf2s = nx.shortest_path(self.graphSneak, source=self.node_EnemyFlagIndex, target=self.node_EnemyScoreIndex)
        #vb2s = nx.shortest_path(self.graph, source="enemy_base", target=self.node_EnemyScoreIndex)

        self.node_EnemyBaseToFlagIndex = "enemy_base_to_flag"
        self.graphSneak.add_node(self.node_EnemyBaseToFlagIndex)
        self.positions["enemy_base_to_flag"] = None
        for vertex in vb2f:
            self.graphSneak.add_edge(self.node_EnemyBaseToFlagIndex, vertex, weight = 1.0)
        
        """self.node_EnemyFlagToScoreIndex = "enemy_flag_to_score" 
        self.graphSneak.add_node(self.node_EnemyFlagToScoreIndex)
        self.positions["enemy_flag_to_score"] = None
        for vertex in vf2s:
            self.graphSneak.add_edge(self.node_EnemyFlagToScoreIndex, vertex, weight = 1.0)"""
        
        self.node_EnemyBaseToScoreIndex = "enemy_base_to_score"
        self.graphSneak.add_node(self.node_EnemyBaseToScoreIndex)
        self.positions["enemy_base_to_score"] = None
       # for vertex in vb2s:
       #     self.graph.add_edge(self.node_EnemyBaseToScoreIndex, vertex, weight = 1.0)

        ## node = self.makeNode(self.game.enemyTeam.flag.position)
        self.distances = nx.single_source_shortest_path_length(self.graphSneak, self.node_EnemyBaseToFlagIndex)

        self.graphSneak.remove_node("base")
        self.graphSneak.remove_node("enemy_base")
        self.graphSneak.remove_node(self.node_EnemyBaseToFlagIndex)
        #self.graphSneak.remove_node(self.node_EnemyFlagToScoreIndex)
        self.graphSneak.remove_node(self.node_EnemyBaseToScoreIndex)
        self.updateEdgeWeights()

                
        
        pointsAndLinesByEdge = dict()
        try:
            self.recursePaths(self.midEnemySpawn, blocked, self.deadlines, [], pointsAndLinesByEdge)
        except RuntimeError as e:
            sys.stdout.write(str(e) + '\n')
        self.camplines = set()
        for edge, pls in pointsAndLinesByEdge.iteritems():
            for _, contact in pls:
                self.camplines.add((edge, contact))
        #sys.stdout.write('\n' + str(self.camplines))
        
        self.campers = []
        for cl in self.camplines:
            self.campers.append([None, cl])
        self.attacker = None
        self.combats = dict()
        self.index = 0
        self.aliveEnemies = len(self.game.enemyTeam.members)
        self.waiter = None
        self.firstTick = True
        self.respawnTime = 0
        self.rcampers = []
        self.cmds = dict()
        tries = 0
        while tries < 10000 and len(self.rcampers) <= len(self.game.team.members):
            tries += 1
            sys.stdout.write('rc ' + str(tries) + '\n')
            pos = self.level.findRandomFreePositionInBox((Vector2(self.game.enemyTeam.botSpawnArea[0].x - self.level.firingDistance * 2, self.game.enemyTeam.botSpawnArea[0].y - self.level.firingDistance * 2), Vector2(self.game.enemyTeam.botSpawnArea[1].x + self.level.firingDistance * 2, self.game.enemyTeam.botSpawnArea[1].y + self.level.firingDistance * 2)))
            if pos.distance(self.midEnemySpawn) > self.level.firingDistance and self.freeLoS(pos, (self.midEnemySpawn - pos).normalized() * self.level.firingDistance / 3):
                self.rcampers.append(pos)

    def speedMods(self, state):
        if state is BotInfo.STATE_ATTACKING:
            return self.level.walkingSpeed
        elif state is BotInfo.STATE_CHARGING or state is BotInfo.STATE_MOVING:
            return self.level.runningSpeed
        else:
            return 0.0
        
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
            
    def sIssue(self, cmd, bot, pos, desc, lookAt = None):
        if bot in self.cmds and self.cmds[bot][0] is cmd and self.cmds[bot][1].distance(pos) < 10 * self.level.characterRadius and (cmd is commands.Charge or (not lookAt and not self.cmds[bot][2]) or (lookAt and self.cmds[bot][2] and self.cmds[bot][2].distance(lookAt) < 10 * self.level.characterRadius)):
            return
        else:
            self.cmds[bot] = (cmd, pos, lookAt)
            if cmd is commands.Attack:
                self.issue(cmd, bot, pos, lookAt, desc)
            else:
                self.issue(cmd, bot, pos, desc)
            
    
    def tick(self): 
        bots_available_unused = self.game.bots_available[:]
        bots_alive_unused = []
        for bot in self.game.bots_alive:
            if bot.state is not BotInfo.STATE_SHOOTING and bot.state is not BotInfo.STATE_TAKINGORDERS:
                bots_alive_unused.append(bot)
        knownTargets = dict()
             
        justAllDead = False
        if self.firstTick:
            self.respawnTime = self.game.match.timeToNextRespawn
            self.firstTick = False
        else:
            for e in self.game.match.combatEvents[self.index:]:
                if e.type == MatchCombatEvent.TYPE_RESPAWN and e.subject in self.game.enemyTeam.members:
                    self.aliveEnemies += 1
                    self.waiter = None
                    sys.stdout.write(str(self.aliveEnemies) + ' ')
                elif e.type == MatchCombatEvent.TYPE_KILLED and e.subject in self.game.enemyTeam.members:
                    self.aliveEnemies -= 1
                    if self.aliveEnemies is 0:
                        justAllDead = True
                    sys.stdout.write(str(self.aliveEnemies) + ' ')
        self.index = len(self.game.match.combatEvents)
        
        if self.aliveEnemies != 0:
            if self.game.team.flag.carrier:
                #if self.flagPos:
                    #knownTargets[self.game.team.flag.carrier] = (self.game.team.flag.position + (self.game.team.flag.position - self.flagPos).midPoint(self.game.enemyTeam.flagScoreLocation - self.game.team.flag.position).normalized() * 4.0, 0.0)
                #else:
                    #self.flagPos = self.game.team.flag.position
                knownTargets[self.game.team.flag.carrier] = (self.level.findNearestFreePosition(self.game.team.flag.position + (self.game.enemyTeam.flagScoreLocation - self.game.team.flag.position).normalized() * 4.0), 0.0)
                sys.stdout.write(str(self.game.team.flag.position + (self.game.enemyTeam.flagScoreLocation - self.game.team.flag.position).normalized() * 4.0) + '\n')
            for enemy in self.game.enemyTeam.members:
                if enemy.position is not None and enemy.health > 0:
                    if enemy.facingDirection is not None and enemy.seenlast is not None and enemy.state is not None:
                        pos = self.level.findNearestFreePosition(enemy.position + enemy.facingDirection * (enemy.seenlast * self.speedMods(enemy.state) + 3))
                        if pos is not None:
                            knownTargets[enemy] = (pos, enemy.seenlast)
                        else:
                            knownTargets[enemy] = (enemy.position, enemy.seenlast)
                    else:
                        #sys.stdout.write('dumb\n')
                        knownTargets[enemy] = (enemy.position, 0.0)
                        
        #sys.stdout.write(str(knownTargets) + '\n')
        
        for bot in copy.copy(self.cmds):
            if bot.health <= 0:
                del self.cmds[bot]            
        
        visibleEnemies = set()
        for bot in self.game.bots_alive:
            visibleEnemies |= set(bot.visibleEnemies)
                    
        for k, v in self.combats.items():
            if v[0] not in knownTargets:
                del self.combats[k]
                if k.state is not BotInfo.STATE_SHOOTING:
                    bots_available_unused.append(k)
                    bots_alive_unused.append(k)
                
        if self.attacker and not self.game.enemyTeam.flag.carrier:
            sys.stdout.write('noattack\n')
            self.attacker = None
            
        if self.aliveEnemies is 0 or self.respawnTime - self.game.match.timeToNextRespawn <= 4:
            for c in self.campers:
                if c[0] in bots_alive_unused:
                    bots_alive_unused.remove(c[0])
                
        if self.waiter in bots_alive_unused:
            bots_alive_unused.remove(self.waiter)
            
        for bot in self.game.bots_alive:
            if bot.flag and (self.attacker is not bot or (bot.state is not BotInfo.STATE_CHARGING and bot.state is not BotInfo.STATE_SHOOTING and bot.state is not BotInfo.STATE_TAKINGORDERS)):
                self.attacker = bot
                if self.aliveEnemies > 0:
                    sys.stdout.write('scorecmd\n')
                    self.sneakTo(bot, self.game.team.flagScoreLocation, 'score')
                else:
                    self.sIssue(commands.Charge, bot, self.game.team.flagScoreLocation, 'score fast')
                    
        if self.attacker in bots_available_unused:
            bots_available_unused.remove(self.attacker)
        if self.attacker in bots_alive_unused:
            bots_alive_unused.remove(self.attacker)
                
        """for bot in bots_alive_unused:
            escapeVec = Vector2(0, 0)
            hostility = 0
            for enemy in bot.seenBy:
                if enemy.position.distance(bot.position) < self.level.firingDistance + 2:
                    escapeVec = escapeVec.midPoint(enemy.facingDirection)
                    hostility += 1
            for friend in bots_alive_unused:
                if bot.position.distance(friend.position) < self.level.firingDistance:
                    hostility -= 1
                    
            if hostility > 0:
                self.issue(commands.Attack, bot, self.level.findNearestFreePosition(bot.position + escapeVec.normalized() * 3), lookAt = escapeVec * -1, description = 'flee')
            
            if knownTargets:
                # and (bot not in self.combats or self.combats[bot][1] + 4 < self.game.match.timePassed)
                kill = sorted(knownTargets.iteritems(), key = lambda f : f[1][0].distance(bot.position) + f[1][1] ** 2)[0]

                if (bot not in self.combats or self.combats[bot][0] is not kill[0]) and kill[1][0].distance(bot.position) + kill[1][1] ** 2 < 1.5 * self.level.firingDistance:
                    self.combats[bot] = (kill[0], self.game.match.timePassed)
                    if bot in bots_available_unused:
                        bots_available_unused.remove(bot)
                    if kill[1][0].distance(bot.position) > self.level.runningSpeed * 5.0:
                        #and (len(self.game.bots_alive) >= 2 * self.aliveEnemies or (len(knownTargets) >= self.aliveEnemies and len(self.game.bots_alive) >= self.aliveEnemies))
                        self.sIssue(commands.Charge, bot, kill[1][0], 'charge target', kill[1][0])
                    else:
                        self.sIssue(commands.Attack, bot, kill[1][0], 'attack target', kill[1][0])"""
               
        for target in knownTargets.iteritems():
            if not bots_alive_unused:
                break
            bots = sorted(bots_alive_unused, key = lambda f: target[1][0].distance(f.position) + target[1][1])
            assigned = 0
            # and target[1][0].distance(bots[assigned].position) + target[1][1] < 1.5 * self.level.firingDistance
            while assigned <= 3 and assigned < len(bots): 
                self.combats[bots[assigned]] = (target[0], self.game.match.timePassed)
                if target[1][0].distance(bots[assigned].position) > self.level.runningSpeed * 5.0:
                    #and (len(self.game.bots_alive) >= 2 * self.aliveEnemies or (len(knownTargets) >= self.aliveEnemies and len(self.game.bots_alive) >= self.aliveEnemies))
                    self.sIssue(commands.Charge, bots[assigned], target[1][0], 'charge target', target[1][0])
                else:
                    self.sIssue(commands.Attack, bots[assigned], target[1][0], 'attack target', target[1][0])
                bots_alive_unused.remove(bots[assigned])
                assigned += 1   
            
        if self.aliveEnemies is 0:
            if not self.waiter:
                for bot in bots_alive_unused:
                    if not self.waiter or bot.position.distance(self.game.enemyTeam.flagSpawnLocation) < self.waiter.position.distance(self.game.enemyTeam.flagSpawnLocation):
                        self.waiter = bot
                if self.waiter:
                    self.sIssue(commands.Charge, self.waiter, self.game.enemyTeam.flagSpawnLocation, 'wait')
                    bots_alive_unused.remove(self.waiter)
            for c in self.campers:
                if c[0] and c[0].state is not BotInfo.STATE_DEFENDING and c[0].state is not BotInfo.STATE_TAKINGORDERS and c[0].position.distance(c[1][0]) < 1:
                    self.issue(commands.Defend, c[0], c[1][1] - c[0].position, description = 'def campline')
             
        if self.waiter in bots_available_unused:
            bots_available_unused.remove(self.waiter)
            
        if justAllDead and self.game.match.timeToNextRespawn >= 6:
            for c in self.campers:
                if not bots_alive_unused:
                    break
                minBot = None
                for bot in bots_alive_unused:
                    if not minBot or minBot.position.distance(c[1][0]) > bot.position.distance(c[1][0]):
                        minBot = bot
                c[0] = minBot
                self.sIssue(commands.Charge, minBot, c[1][0], 'to campline')
                bots_alive_unused.remove(minBot)
                
        if self.aliveEnemies is 0 or self.respawnTime - self.game.match.timeToNextRespawn <= 4:
            for c in self.campers:
                if c[0] in bots_available_unused:
                    bots_available_unused.remove(c[0])
                                
        holding = len(self.game.bots_holding)
        for bot in self.game.bots_holding:
            if bot.state is not BotInfo.STATE_SHOOTING and bot.state is not BotInfo.STATE_TAKINGORDERS:
                target = self.level.findRandomFreePositionInBox((bot.position-5.0, bot.position+5.0))
                self.sIssue(commands.Attack, bot, target, 'antihold', random.choice([b.position for b in bot.visibleEnemies]))
        
        for bot in bots_available_unused:
            if bot.flag:
                sys.stdout.write('wat')
            if self.aliveEnemies is 0 and self.rcampers:
                if bot.position.distance(self.midEnemySpawn) > self.level.firingDistance and bot.position.distance(self.midEnemySpawn) <= self.level.firingDistance * 2:
                    if bot.state is not BotInfo.STATE_DEFENDING and bot.state is not BotInfo.STATE_TAKINGORDERS:
                        self.issue(commands.Defend, bot, self.midEnemySpawn - bot.position, description = 'rand camp')
                else:
                    self.sIssue(commands.Charge, bot, random.choice(self.rcampers), 'to rand camp')
            else:
                dest = None
                if self.attacker:
                    dest = random.choice([self.game.team.flagScoreLocation, self.game.enemyTeam.flagSpawnLocation])
                else:
                    dest = self.game.enemyTeam.flag.position
                #if len(self.game.bots_alive) >= 2 * self.aliveEnemies or (not knownTargets and self.game.enemyTeam.flag.position.distance(self.midMySpawn) < self.midEnemySpawn.distance(self.midMySpawn)):
                self.sIssue(commands.Charge, bot, dest, 'charge flag')
                #else:
                    #self.sIssue(commands.Attack, bot, dest, 'attack flag', random.choice([self.midEnemySpawn, self.game.team.flag.position]))