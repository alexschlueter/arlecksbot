import sys
import random
import itertools
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
        for p, _ in self.ambushes:
            visualizer.drawCircle(p, QtGui.qRgb(255,255,0), 0.5)
            
    def keyPressed(self, e):
        if e.key() == QtCore.Qt.Key_Space:
            self.mode = 1 - self.mode

    def initialize(self):
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

        ## node = self.makeNode(self.game.enemyTeam.flag.position)
        self.distances = nx.single_source_shortest_path_length(self.graph, self.node_EnemyFlagToScoreIndex)
        self.queue = {}
        self.index = 0
        print "Done with init. Calculating ambush spots"
        self.calculateAmbushes()

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

    def calculateAmbushes(self):        
        results = []
        for i in range(2000):  # NOTE: you must feed in better pre-selected positions (eg near boxes) to get good results with this number of iterations.
            if (i%1000)==0: print >>sys.stderr, '.',
            p = self.level.findRandomFreePositionInBox(self.level.area)
            o = Vector2(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5)).normalized()

            s = self.evaluate(p, o, lambda x, y: 25.0-square(self.getDistance(x, y))) - square(self.visibilities.pixel(int(p.x), int(p.y)) * 5.0)
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
            if e.type != gameinfo.MatchCombatEvent.TYPE_RESPAWN:
                continue
            if e.subject in self.queue:
                del self.queue[e.subject] 
        self.index = len(self.game.match.combatEvents)

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

