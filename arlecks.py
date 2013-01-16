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
                    
                """if topLeft:
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
                        nEdges.add((Vector2(x, y + 1.25), self.BOTTOMRIGHT))"""
                if topLeft:
                    nEdges.add((Vector2(x - 0.25, y + 0.5), self.LEFTUP))
                    nEdges.add((Vector2(x + 0.5, y - 0.25), self.TOPLEFT))
                if bottomLeft:
                    nEdges.add((Vector2(x - 0.25, y + 0.5), self.LEFTDOWN))
                    nEdges.add((Vector2(x + 0.5, y + 1.25), self.BOTTOMLEFT))
                if topRight:
                    nEdges.add((Vector2(x + 1.25, y + 0.5), self.RIGHTUP))
                    nEdges.add((Vector2(x + 0.5, y - 0.25), self.TOPRIGHT))
                if bottomRight:
                    nEdges.add((Vector2(x + 1.25, y + 0.5), self.RIGHTDOWN))
                    nEdges.add((Vector2(x + 0.5, y + 1.25), self.BOTTOMRIGHT))
                    
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
    
        self.graphSneak = g.copy()
        self.graphNormal = g.copy()
        
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
                                
    def initialize(self):
        self.verbose = True
        sys.stdout.write(str(self.game.enemyTeam.botSpawnArea[1]) + ' ' + str(self.level.characterRadius) + '\n')
        self.midEnemySpawn = self.game.enemyTeam.botSpawnArea[0].midPoint(self.game.enemyTeam.botSpawnArea[1])
        self.midMySpawn = self.game.team.botSpawnArea[0].midPoint(self.game.team.botSpawnArea[1])
        visited, islandEdges, islandOuter = [], [], []
        for x in range(0, len(self.level.blockHeights)):
            for y in range(0, len(self.level.blockHeights[x])):
                _, edges, island = self.recurseNeighbours(x, y, visited)
                if edges:
                    islandEdges.append(edges)
                    islandOuter.append(island)
                    
                    
        sys.stdout.write(str(islandEdges) + '\n' + str(islandOuter) + '\n')
                   
        blocked = [item for sublist in islandOuter for item in sublist]
        blockedOrSpawn = blocked[:]
        spawn = []
        for x in range(int(self.game.enemyTeam.botSpawnArea[0].x), int(self.game.enemyTeam.botSpawnArea[1].x)):
            for y in range(int(self.game.enemyTeam.botSpawnArea[0].y), int(self.game.enemyTeam.botSpawnArea[1].y)):
                spawn.append(Vector2(x, y))
        blockedOrSpawn += spawn
                
        self.deadlines = dict()
        for i in range(len(islandEdges)):
            for coord, orientation in islandEdges[i]:
                """if orientation is self.TOPLEFT:
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
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.24 * self.level.firingDistance / 1.0283968, coord.y + self.level.firingDistance / 1.0283968))"""
                
                magixcs = 0.554616985
                if orientation is self.TOPLEFT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.5 * self.level.firingDistance / magixcs, coord.y + 0.24 * self.level.firingDistance / magixcs))
                elif orientation is self.BOTTOMLEFT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.5 * self.level.firingDistance / magixcs, coord.y - 0.24 * self.level.firingDistance / magixcs))
                elif orientation is self.LEFTUP:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + 0.24 * self.level.firingDistance / magixcs, coord.y - 0.5 * self.level.firingDistance / magixcs))
                elif orientation is self.RIGHTUP:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.24 * self.level.firingDistance / magixcs, coord.y - 0.5 * self.level.firingDistance / magixcs))
                elif orientation is self.TOPRIGHT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + 0.5 * self.level.firingDistance / magixcs, coord.y + 0.24 * self.level.firingDistance / magixcs))
                elif orientation is self.BOTTOMRIGHT:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + 0.5 * self.level.firingDistance / magixcs, coord.y - 0.24 * self.level.firingDistance / magixcs))
                elif orientation is self.LEFTDOWN:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x + 0.24 * self.level.firingDistance / magixcs, coord.y + 0.5 * self.level.firingDistance / magixcs))
                elif orientation is self.RIGHTDOWN:
                    self.deadlineFromLine(blocked, spawn, coord, Vector2(coord.x - 0.24 * self.level.firingDistance / magixcs, coord.y + 0.5 * self.level.firingDistance / magixcs))
                
        sys.stdout.write(str(self.deadlines) + '\n')
        
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

        """vb2f = nx.shortest_path(self.graphSneak, source="enemy_base", target=self.node_EnemyFlagIndex)
        vf2s = nx.shortest_path(self.graphSneak, source=self.node_EnemyFlagIndex, target=self.node_EnemyScoreIndex)
        vb2s = nx.shortest_path(self.graph, source="enemy_base", target=self.node_EnemyScoreIndex)

        self.node_EnemyBaseToFlagIndex = "enemy_base_to_flag"
        self.graphSneak.add_node(self.node_EnemyBaseToFlagIndex)
        self.positions["enemy_base_to_flag"] = None
        for vertex in vb2f:
            self.graphSneak.add_edge(self.node_EnemyBaseToFlagIndex, vertex, weight = 1.0)
        
        self.node_EnemyFlagToScoreIndex = "enemy_flag_to_score" 
        self.graphSneak.add_node(self.node_EnemyFlagToScoreIndex)
        self.positions["enemy_flag_to_score"] = None
        for vertex in vf2s:
            self.graphSneak.add_edge(self.node_EnemyFlagToScoreIndex, vertex, weight = 1.0)"""
        
        vb2s = nx.shortest_path(self.graphSneak, source="enemy_base", target=self.node_EnemyFlagIndex) + nx.shortest_path(self.graphSneak, source=self.node_EnemyFlagIndex, target=self.node_EnemyScoreIndex)
        self.node_EnemyBaseToScoreIndex = "enemy_base_to_score"
        self.graphSneak.add_node(self.node_EnemyBaseToScoreIndex)
        self.positions["enemy_base_to_score"] = None
        for vertex in vb2s:
            self.graphSneak.add_edge(self.node_EnemyBaseToScoreIndex, vertex, weight = 1.0)

        ## node = self.makeNode(self.game.enemyTeam.flag.position)
        self.distances = nx.single_source_shortest_path_length(self.graphSneak, self.node_EnemyBaseToScoreIndex)
        self.graphSneak.remove_node("base")
        self.graphSneak.remove_node("enemy_base")
        #self.graphSneak.remove_node(self.node_EnemyBaseToFlagIndex)
        #self.graphSneak.remove_node(self.node_EnemyFlagToScoreIndex)
        self.graphSneak.remove_node(self.node_EnemyBaseToScoreIndex)
        self.updateEdgeWeights()
        """midOurSpawn = self.game.team.botSpawnArea[0].midPoint(self.game.team.botSpawnArea[1])
        spawnConnection = (midEnemySpawn - midOurSpawn)
        anker = midOurSpawn + spawnConnection / 3
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
            
        pointsAndLinesByEdge = dict()
        for i in range(1, 11):
            sys.stdout.write(str(intersections[0] + (i / 10.0) * (intersections[1] - intersections[0])))
            path = nx.shortest_path(self.graph, source = self.getNodeIndex(self.level.findNearestFreePosition(intersections[0] + (i / 10.0) * (intersections[1] - intersections[0]))), target = self.getNodeIndex(self.game.team.flagSpawnLocation))
            sys.stdout.write(str(path) + '\n')
            cutoff = False
            for node in path:
                p = Vector2(node % self.graph.graph["map_width"], int(node / self.graph.graph["map_width"]))
                for edge, contacts in self.deadlines.iteritems():
                    for contact in contacts:
                        line = (edge, contact)
                        
                        if self.intersects(edge, contact, p):
                            if edge in pointsAndLinesByEdge:
                                pointsAndLinesByEdge[edge].append((p, contact))
                            else:
                                pointsAndLinesByEdge[edge] = [(p, contact)]
                            cutoff = True
                            break
                        if cutoff:
                            break
                    if cutoff:
                        break
                if cutoff:
                    break
                #recalc= []
                for edge in self.deadlines.keys():
                    if p.distance(edge) <= self.level.firingDistance and not self.whoBlocks(blocked, p, edge):
                        sys.stdout.write('removed: ' + str(p) + ' '  + str(edge) + '\n')
                        del self.deadlines[edge]
                        if edge in pointsAndLinesByEdge:
                            #for pointAndLine in pointsAndLinesByEdge[edge]:
                                #recalc.append(pointAndLine[0])
                                #visited.remove(pointAndLine[0])
                            del pointsAndLinesByEdge[edge]
                #for re in recalc:
                    #self.recursePaths(re, blocked, deadlines, visited, pointsAndLinesByEdge)"""
        pointsAndLinesByEdge = dict()
        if self.midEnemySpawn.distance(self.game.team.flagSpawnLocation) < self.midMySpawn:
            path = nx.shortest_path(self.graphNormal, source = self.getNodeIndex(self.game.team.flagSpawnLocation), target = self.getNodeIndex(self.game.enemyTeam.flagScoreLocation))
        else:
            path = nx.shortest_path(self.graphNormal, source = self.getNodeIndex(self.midEnemySpawn), target = self.getNodeIndex(self.game.team.flagSpawnLocation))
        #sys.stdout.write(str(len(paths)) + '\n')
        #cutoff = False
        """"i = 0
        for path in paths:
            if i == 5:
                break
            i += 1"""
        for node in path:
            p = Vector2(node % self.graphNormal.graph["map_width"], int(node / self.graphNormal.graph["map_width"]))
            for edge in self.deadlines.keys():
                if p.distance(edge) <= self.level.firingDistance and not self.whoBlocks(blocked, p, edge):
                    #sys.stdout.write('removed: ' + str(p) + ' '  + str(edge) + '\n')
                    del self.deadlines[edge]
                    #if edge in pointsAndLinesByEdge:
                        #for pointAndLine in pointsAndLinesByEdge[edge]:
                            #recalc.append(pointAndLine[0])
                            #visited.remove(pointAndLine[0])
                        #del pointsAndLinesByEdge[edge]
            for edge, contacts in self.deadlines.iteritems():
                for contact in contacts:
                    #line = (edge, contact)
                    
                    if self.intersects(edge, contact, p):
                        if edge in pointsAndLinesByEdge:
                            pointsAndLinesByEdge[edge].append((p, contact))
                        else:
                            pointsAndLinesByEdge[edge] = [(p, contact)]
                        #cutoff = True
                        #break
                    #if cutoff:
                        #break
                #if cutoff:
                    #break
            #if cutoff:
                #break
            #recalc= []
                
        
        """pointsAndLinesByEdge = dict()
        try:
            self.recursePaths(midEnemySpawn, blocked, self.deadlines, [], pointsAndLinesByEdge)
        except RuntimeError as e:
            sys.stdout.write(str(e) + '\n')"""
        camplines = set()
        for edge, pls in pointsAndLinesByEdge.iteritems():
            for _, contact in pls:
                camplines.add((edge, contact))
        sys.stdout.write('\n' + str(camplines))
        
        self.campers = []
        for cl in camplines:
            self.campers.append([[], cl])
        self.attacker = None
        self.index = 0
        self.aliveEnemies = 0
        self.knownDefenders = []
        
    def gIssue(self, graph, command, bot, dst, message = ''):
        # calculate the shortest path between the bot and the target using our weights
        srcIndex = self.getNodeIndex(bot.position)
        dstIndex = self.getNodeIndex(dst)
        pathNodes = nx.shortest_path(graph, srcIndex, dstIndex, 'weight')
    
        pathLength = len(pathNodes)
        if pathLength > 0:
            path = [self.positions[p] for p in pathNodes if self.positions[p]]
            if len(path) > 0:
                orderPath = path[::10]
                orderPath.append(path[-1]) # take every 10th point including last point
                self.issue(command, bot, orderPath, description = message) 
                #self.paths[bot] = path    # store the path for visualization
                
    def updateWeights(self, bot, sneakW, normalW):
        first = bot.position + self.level.firingDistance * self.angledVector(bot.facingDirection, self.level.fieldOfViewAngles[BotInfo.STATE_DEFENDING] / 2)
        second = bot.position + self.level.firingDistance * self.angledVector(bot.facingDirection, self.level.fieldOfViewAngles[BotInfo.STATE_DEFENDING] / -2)
        nodes = []
        for box in line(bot.position, first):
            nodes.append(self.getNodeIndex(Vector2(box[0], box[1])))
                #sys.stdout.write(str(box) + '\n')
                
        for box in line(bot.position, second):
            nodes.append(self.getNodeIndex(Vector2(box[0], box[1])))
        for box in line(first, second):
            nodes.append(self.getNodeIndex(Vector2(box[0], box[1])))
                
        for a, b in self.graphSneak.edges_iter(nodes):
            #sys.stdout.write(str(edge) + ' ')
            #sys.stdout.write(str(Vector2(a % self.graphNormal.graph["map_width"], int(a / self.graphNormal.graph["map_width"]))) + ' ' + str(Vector2(b % self.graphNormal.graph["map_width"], int(b / self.graphNormal.graph["map_width"]))) + '\n')
            self.graphSneak[a][b]['weight'] = sneakW
        for a, b in self.graphNormal.edges_iter(nodes):
            #sys.stdout.write(str(edge) + ' ')
            #sys.stdout.write(str(Vector2(a % self.graphNormal.graph["map_width"], int(a / self.graphNormal.graph["map_width"]))) + ' ' + str(Vector2(b % self.graphNormal.graph["map_width"], int(b / self.graphNormal.graph["map_width"]))) + '\n')
            self.graphNormal[a][b]['weight'] = normalW
        return nodes
            
    def tick(self):
        newAttacker = False
        for e in self.game.match.combatEvents[self.index:]:
            if e.type == MatchCombatEvent.TYPE_RESPAWN and e.subject in self.game.enemyTeam.members:
                self.aliveEnemies += 1
                sys.stdout.write(str(self.aliveEnemies) + '\n')
            elif e.type == MatchCombatEvent.TYPE_KILLED and e.subject in self.game.enemyTeam.members:
                self.aliveEnemies -= 1
                sys.stdout.write(str(self.aliveEnemies) + '\n')
            elif e.type == MatchCombatEvent.TYPE_KILLED and e.subject in self.game.team.members:
                self.updateWeights(e.instigator, 999, 20)
            elif e.type == MatchCombatEvent.TYPE_FLAG_CAPTURED and e.subject is self.game.enemyTeam.flag:
                newAttacker = True
                
        self.index = len(self.game.match.combatEvents)
        
        bots_available_unused = self.game.bots_available[:]
        visibleEnemies = set()
        heldBy = dict()
        for bot in self.game.bots_alive:
            for enemy in bot.visibleEnemies:
                visibleEnemies.add(enemy)
            if bot.state is BotInfo.STATE_HOLDING:
                #self.gIssue(self.graphNormal, commands.Charge, bot, self.game.team.botSpawnArea[1].midPoint(self.game.team.botSpawnArea[0]))
                heldBy[bot] = []
                for enemy in bot.seenBy:
                    if enemy.position.distance(bot.position) <= self.level.firingDistance:
                        heldBy[bot].append(enemy)
                
        dangerNodes = []
        for bot in visibleEnemies:
            if bot.state is BotInfo.STATE_DEFENDING and not bot.position in self.knownDefenders:
                self.knownDefenders.append(bot.position)
                dangerNodes = self.updateWeights(bot, 999, 255)
                
        
        if self.game.enemyTeam.flag.carrier:
            self.attacker = self.game.enemyTeam.flag.carrier
            if self.attacker.state is not BotInfo.STATE_SHOOTING and self.attacker.state is not BotInfo.STATE_CHARGING and self.attacker.state is not BotInfo.STATE_TAKINGORDERS:
                self.gIssue(self.graphSneak, commands.Charge, self.attacker, self.game.team.flagScoreLocation, 'score')
        elif newAttacker or not self.attacker or self.attacker.health <= 0:
            candidates = []
            for bot in self.game.bots_alive:
                if not bot.state is BotInfo.STATE_SHOOTING and not bot.state is BotInfo.STATE_HOLDING:
                    candidates.append(bot)
            if candidates:
                self.attacker = sorted(candidates, key = lambda f: f.position.distance(self.game.enemyTeam.flag.position))[0]
                self.gIssue(self.graphSneak, commands.Move, self.attacker, self.game.enemyTeam.flag.position, 'capture')
            else:
                self.attacker = None
        elif self.attacker.state is BotInfo.STATE_IDLE:
            self.gIssue(self.graphSneak, commands.Move, self.attacker, self.game.enemyTeam.flag.position, 'capture')
            

        for c in self.campers:
            for derp in c[0][:]:
                if derp[0].health <= 0 or derp[0] is self.attacker:
                    c[0].remove(derp)
        
        if self.attacker in bots_available_unused:
            bots_available_unused.remove(self.attacker)
            
        for bot in bots_available_unused:
            handled = False
            for c in self.campers:
                for b in c[0]:
                    if bot is b[0]:
                        if not b[1]:
                            if bot.position.distance(c[1][0]) < 1:
                                self.issue(commands.Defend, bot, c[1][1] - bot.position)
                                b[1] = True
                            else:
                                self.gIssue(self.graphNormal, commands.Attack, bot, c[1][0])
                        handled = True
                        break
                if handled:
                    break
            if not handled:
                myplace = sorted(self.campers, key = lambda f: len(f[0]))[0]
                myplace[0].append([bot, False]) 
                sys.stdout.write(str(myplace[1][0]) + '\n')     
                self.gIssue(self.graphNormal, commands.Attack, bot, myplace[1][0])
                #sys.stdout.write(bot.name + '\n')