import sys
import random
import itertools
import math
from visibility import Wave

from api import Commander, commands, gameinfo
from api.vector2 import Vector2


from PySide import QtGui, QtCore
import networkx as nx

from visualizer import VisualizerApplication

SCALE = 10

def square(x): return x*x
 


class AmbushCommander(Commander):
    """
        Display current state and predictions on the screen in a PyQT application.
    """
    MODE_VISIBILITY = 0 
    MODE_TRAVELLING = 1
    
    LEFTUP = 0
    LEFTDOWN = 1
    RIGHTUP = 2
    RIGHTDOWN = 3
    TOPLEFT = 4
    TOPRIGHT = 5
    BOTTOMLEFT = 6
    BOTTOMRIGHT = 7
    
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
    
    def drawPreWorld(self, visualizer):
       furthest = max([self.distances[n] for n in itertools.chain(*self.terrain) if n])
       brightest = max([self.visibilities.pixel(i,j) for i, j in itertools.product(range(88), range(50))])
        
        # visible = QtGui.QImage(88, 50, QtGui.QImage.Format_ARGB32)
        # visible.fill(0)

       for i, j in itertools.product(range(88), range(50)):            
            n = self.terrain[j][i]
            if n:
                if self.mode == self.MODE_TRAVELLING:
                    d = self.distances[n] * 255.0 / furthest
                if self.mode == self.MODE_VISIBILITY:
                    d = self.visibilities.pixel(i,j) * 255 / brightest
            else:                
                d = 32
            visualizer.drawPixel((i, j), QtGui.qRgb(d,d,d))
                
    def drawPreBots(self, visualizer):
        for p, o in self.ambushes:
            visualizer.drawCircle(p, QtGui.qRgb(255,255,0), 0.5)
            visualizer.drawRay(p, o, QtGui.qRgb(255,0,0))
        for island in self.islandEdges:
            for p, _ in island:
                visualizer.drawCircle(p, QtGui.qRgb(255,0,0), 0.5)
            
    def keyPressed(self, e):
        if e.key() == QtCore.Qt.Key_Space:
            self.mode = 1 - self.mode

    def initialize(self):
        self.midEnemySpawn = self.game.enemyTeam.botSpawnArea[0].midPoint(self.game.enemyTeam.botSpawnArea[1])
        visited, self.islandEdges, islandOuter = [], [], []
        for x in range(0, len(self.level.blockHeights)):
            for y in range(0, len(self.level.blockHeights[x])):
                _, edges, island = self.recurseNeighbours(x, y, visited)
                if edges:
                    self.islandEdges.append(edges)
                    islandOuter.append(island)
        blocked = [item for sublist in islandOuter for item in sublist]
        #blockedOrSpawn = blocked[:]
        spawn = []
        for x in range(int(self.game.enemyTeam.botSpawnArea[0].x), int(self.game.enemyTeam.botSpawnArea[1].x)):
            for y in range(int(self.game.enemyTeam.botSpawnArea[0].y), int(self.game.enemyTeam.botSpawnArea[1].y)):
                spawn.append(Vector2(x, y))
        
        self.campLines = []
        for island in self.islandEdges:
            for coord, orientation in island:
                if orientation is self.TOPLEFT:
                    self.campLines.append((coord, Vector2(-self.level.firingDistance / 1.0283968, 0.24 * self.level.firingDistance / 1.0283968)))
                elif orientation is self.BOTTOMLEFT:
                    self.campLines.append((coord, Vector2(-self.level.firingDistance / -1.0283968, -0.24 * self.level.firingDistance / 1.0283968)))
                elif orientation is self.LEFTUP:
                    self.campLines.append((coord, Vector2(0.24 * self.level.firingDistance / 1.0283968, -self.level.firingDistance / 1.0283968)))
                elif orientation is self.RIGHTUP:
                    self.campLines.append((coord, Vector2(-0.24 * self.level.firingDistance / 1.0283968, -self.level.firingDistance / 1.0283968)))
                elif orientation is self.TOPRIGHT:
                    self.campLines.append((coord, Vector2(self.level.firingDistance / 1.0283968, 0.24 * self.level.firingDistance / 1.0283968)))
                elif orientation is self.BOTTOMRIGHT:
                    self.campLines.append((coord, Vector2(self.level.firingDistance / 1.0283968, -0.24 * self.level.firingDistance / 1.0283968)))
                elif orientation is self.LEFTDOWN:
                    self.campLines.append((coord, Vector2(0.24 * self.level.firingDistance / 1.0283968, self.level.firingDistance / 1.0283968)))
                elif orientation is self.RIGHTDOWN:
                    self.campLines.append((coord, Vector2(-0.24 * self.level.firingDistance / 1.0283968, self.level.firingDistance / 1.0283968)))
        sys.stdout.write(str(self.campLines) + '\n')
        self.deadlines = dict()
        for i in range(len(self.islandEdges)):
            for coord, orientation in self.islandEdges[i]:
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
        self.spawnCamplines = set()
        for edge, pls in pointsAndLinesByEdge.iteritems():
            for _, contact in pls:
                self.spawnCamplines.add((self.level.findNearestFreePosition(edge), contact))
        sys.stdout.write('\n' + str(self.spawnCamplines))
        
        self.spawnCampers = []
        for cl in self.spawnCamplines:
            self.spawnCampers.append([[], cl])
        
        self.mode = self.MODE_VISIBILITY
        self.visualizer = VisualizerApplication(self)

        self.visualizer.setDrawHookPreWorld(self.drawPreWorld)
        self.visualizer.setDrawHookPreBots(self.drawPreBots)
        self.visualizer.setKeyboardHook(self.keyPressed)

        self.makeGraph()
        
        self.graph.add_node("enemy_base")
        start, finish = self.level.botSpawnAreas[self.game.enemyTeam.name]        
        for i, j in itertools.product(range(int(start.x), int(finish.x)), range(int(start.y), int(finish.y))):
            self.graph.add_edge("enemy_base", self.terrain[j][i], weight = 1.0)            


        self.graph.add_node("base")
        start, finish = self.level.botSpawnAreas[self.game.team.name]        
        for i, j in itertools.product(range(int(start.x), int(finish.x)), range(int(start.y), int(finish.y))):
            self.graph.add_edge("base", self.terrain[j][i],weight = 1.0)            


        self.node_EnemyFlagIndex = self.getNodeIndex(self.game.team.flag.position)
        self.node_EnemyScoreIndex = self.getNodeIndex(self.game.enemyTeam.flagScoreLocation)

        # self.node_Bases = self.graph.add_vertex()
        # e = self.graph.add_edge(self.node_Bases, self.node_MyBase)
        # e = self.graph.add_edge(self.node_Bases, self.node_EnemyBase)

        vb2f = nx.shortest_path(self.graph, source="enemy_base", target=self.node_EnemyFlagIndex)
        vf2s = nx.shortest_path(self.graph, source=self.node_EnemyFlagIndex, target=self.node_EnemyScoreIndex)
        #vb2s = nx.shortest_path(self.graph, source="enemy_base", target=self.node_EnemyScoreIndex)

        self.visibilities = QtGui.QImage(88, 50, QtGui.QImage.Format_ARGB32)
        self.visibilities.fill(0)
        path = vb2f+vf2s
        #path = vb2f = nx.shortest_path(self.graph, source="enemy_base", target=self.node_EnemyFlagIndex)
        edgesinpath=zip(path[0:],path[1:])        
        for vt, vf in edgesinpath[:-1]:
            if "position" not in self.graph.node[vf]:
                continue
            position = Vector2(*self.graph.node[vf]["position"])
            if "position" not in self.graph.node[vt]:
                continue
            next_position = Vector2(*self.graph.node[vt]["position"])
            if position == next_position:
                continue
            orientation = (next_position - position).normalized()

            def visible(p):
                delta = (p-position)
                l = delta.length()
                if l > 20.0:
                    return False
                if l < 2.5:
                    return True
                delta /= l
                return orientation.dotProduct(delta) >= 0.5

            cells = []
            w = Wave((88, 50), lambda x, y: self.level.blockHeights[x][y] > 1, lambda x, y: cells.append((x,y)))
            w.compute(position)

            for x, y in [c for c in cells if visible(Vector2(c[0]+0.5, c[1]+0.5))]:
                self.visibilities.setPixel(x, y, self.visibilities.pixel(x, y)+1)

        starte, finishe = self.level.botSpawnAreas[self.game.enemyTeam.name]
        startf, finishf = self.level.botSpawnAreas[self.game.team.name]
        points = [self.game.team.flag.position, self.game.enemyTeam.flag.position,
                  self.game.team.flagScoreLocation, self.game.enemyTeam.flagScoreLocation] * 4
        for i, j in list(itertools.product(range(int(starte.x), int(finishe.x)), range(int(starte.y), int(finishe.y)))) \
                    + list(itertools.product(range(int(startf.x), int(finishf.x)), range(int(startf.y), int(finishf.y)))) \
                    + [(int(p.x), int(p.y)) for p in points]:
            n = self.terrain[j][i]
            if not n: continue
            
            position = Vector2(*self.graph.node[n]["position"])
            def visible(p):
                delta = (p-position)
                l = delta.length()
                return l <= 15.0

            cells = []
            w = Wave((88, 50), lambda x, y: self.level.blockHeights[x][y] > 1, lambda x, y: cells.append((x,y)))
            w.compute(position)

            for x, y in [c for c in cells if visible(Vector2(c[0]+0.5, c[1]+0.5))]:
                self.visibilities.setPixel(x, y, self.visibilities.pixel(x, y)+1)


        self.node_EnemyBaseToFlagIndex = "enemy_base_to_flag"
        self.graph.add_node(self.node_EnemyBaseToFlagIndex)
        for vertex in vb2f:
            self.graph.add_edge(self.node_EnemyBaseToFlagIndex, vertex, weight = 1.0)
        
        self.node_EnemyFlagToScoreIndex = "enemy_flag_to_score" 
        self.graph.add_node(self.node_EnemyFlagToScoreIndex)
        for vertex in vf2s:
            self.graph.add_edge(self.node_EnemyFlagToScoreIndex, vertex, weight = 1.0)
        
        self.node_EnemyBaseToScoreIndex = "enemy_base_to_score"
        self.graph.add_node(self.node_EnemyBaseToScoreIndex)
       # for vertex in vb2s:
       #     self.graph.add_edge(self.node_EnemyBaseToScoreIndex, vertex, weight = 1.0)

        ## node = self.makeNode(self.game.enemyTeam.flag.position)"""
        self.distances = nx.single_source_shortest_path_length(self.graph, self.node_EnemyFlagToScoreIndex)
        #self.distances = nx.single_source_shortest_path_length(self.graph, self.node_EnemyBaseToFlagIndex)
        self.queue = {}
        self.index = 0
        print "Done with init. Calculating ambush spots"
        self.calculateAmbushes(self.campLines)
        self.aliveEnemies = 0

    def evaluate(self, position, orientation, callback):
        cells = []
        w = Wave((88, 50), lambda x, y: self.level.blockHeights[x][y] > 1, lambda x, y: cells.append((x,y)))
        w.compute(position)

        def visible(p):
            delta = (p-position)
            l = delta.length()
            if l > 15.0:
                return False
            if l < 2.5:
                return True
            delta /= l
            return orientation.dotProduct(delta) > 0.9238

        total = 0.0
        for x, y in [c for c in cells if visible(Vector2(c[0]+0.5, c[1]+0.5))]:
            total += callback(x,y)
        return total

    def findNearby(self, results, candidate, distance = 2.0):
        d = distance * distance
        s, (position, _) = candidate
        for _, (p, _) in results:
            if (p-position).squaredLength() < d:
                return True            
        return False

    def replaceInList(self, candidate, results, maximum = 40):
        results.append(candidate)

        if len(results) < 50:
            return

        copy = results[:]
        copy.sort(key=lambda s: -s[0])

        results[:] = []

        for i, c in enumerate(copy):
            if not self.findNearby(results, c):
                results.append(c)
            if len(results) >= maximum:
                break

    def calculateAmbushes(self, camps):        
        results = []
        for q, _ in camps:
            p = self.level.findNearestFreePosition(q)
            for i in range(10):
                o = self.angledVector(Vector2(1, 0), i * 36 * math.pi / 180)
                #o = Vector2(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5)).normalized()
    
                s = self.evaluate(p, o, lambda x, y: 25.0-square(self.getDistance(x, y))) - square(self.visibilities.pixel(int(p.x), int(p.y)) * 5.0)
                #s = self.evaluate(p, o, lambda x, y: - self.getDistance(x, y) - self.visibilities.pixel(int(p.x), int(p.y)))
                self.replaceInList((s, (p,o)), results)

        self.ambushes = [r for _, r in results]

    def getSituation(self):
        result = None
        score = 0.0
        for i in range(10):
            p = self.level.findRandomFreePositionInBox(self.level.area)
            o = Vector2(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5)).normalized()
            s = self.evaluate(p, o, lambda x, y: 15.0-self.getDistance(x, y))
                # - self.getDistance(int(p.x), int(p.y)) * 100 
            if s > score or result == None:
                result = (p, o)
                score = s
        print score
        return result

    def getDistance(self, x, y):
        n = self.terrain[y][x]
        if n:
            return self.distances[n]
        else:
            return 0.0

    def tick(self):
        for e in self.game.match.combatEvents[self.index:]:
            if e.type == gameinfo.MatchCombatEvent.TYPE_RESPAWN:
                if e.subject in self.queue:
                    del self.queue[e.subject]
                elif e.subject in self.game.enemyTeam.members:
                    self.aliveEnemies += 1
                    sys.stdout.write(str(self.aliveEnemies) + '\n')
            elif e.type == gameinfo.MatchCombatEvent.TYPE_KILLED and e.subject in self.game.enemyTeam.members:
                self.aliveEnemies -= 1
                sys.stdout.write(str(self.aliveEnemies) + '\n')
        self.index = len(self.game.match.combatEvents)

        for c in self.spawnCampers:
            for derp in c[0][:]:
                if derp[0].health <= 0:
                    c[0].remove(derp)

        if self.aliveEnemies == 0 and self.game.match.timeToNextRespawn > 5:
            for bot in self.game.bots_alive:
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
            for bot in self.game.bots_available:
                if bot in self.queue:
                    p, o = self.queue[bot]
                    if (bot.position-p).length() < 1.0:
                        self.issue(commands.Defend, bot, o)
                        continue
                else:
                    p, o = random.choice(self.ambushes)
                    self.queue[bot] = (p, o)
                
                self.issue(commands.Charge, bot, p)
        
        self.visualizer.tick()

    def shutdown(self):
        self.visualizer.quit()
        del self.visualizer

    def makeGraph(self):
        blocks = self.level.blockHeights
        width, height = len(blocks), len(blocks[0])

        g = nx.Graph(directed=False, map_height = height, map_width = width)
        #self.positions = g.new_vertex_property('vector<float>')
        #self.weights = g.new_edge_property('float')
    
        #g.vertex_properties['pos'] = self.positions
        #g.edge_properties['weight'] = self.weights
    
        self.terrain = []
        for j in range(0, height):
            row = []
            for i in range(0,width):
                if blocks[i][j] == 0:
                    g.add_node(i+j*width, position = (float(i)+0.5, float(j)+0.5) )
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
    
        self.graph = g



    def getNodeIndex(self, position):
        i = int(position.x)
        j = int(position.y)
        width = self.graph.graph["map_width"]
        return i+j*width

