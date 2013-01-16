import math
import itertools
import random

import networkx as nx
from PySide import QtGui

import api
from api.gameinfo import *
from api import *

from visualizer import VisualizerApplication

class SneakingCommander(Commander):

    def initialize(self):
        self.makeGraph()
        
        self.graph.add_node("enemy_base")
        self.positions["enemy_base"] = None
        start, finish = self.level.botSpawnAreas[self.game.enemyTeam.name]
        for i, j in itertools.product(range(int(start.x), int(finish.x)), range(int(start.y), int(finish.y))):
            self.graph.add_edge("enemy_base", self.terrain[j][i], weight = 1.0)

        self.graph.add_node("base")
        self.positions["base"] = None
        start, finish = self.level.botSpawnAreas[self.game.team.name]
        for i, j in itertools.product(range(int(start.x), int(finish.x)), range(int(start.y), int(finish.y))):
            self.graph.add_edge("base", self.terrain[j][i], weight = 1.0)

        self.node_EnemyFlagIndex = self.getNodeIndex(self.game.team.flag.position)
        self.node_EnemyScoreIndex = self.getNodeIndex(self.game.enemyTeam.flagScoreLocation)

        # self.node_Bases = self.graph.add_vertex()
        # e = self.graph.add_edge(self.node_Bases, self.node_MyBase)
        # e = self.graph.add_edge(self.node_Bases, self.node_EnemyBase)

        vb2f = nx.shortest_path(self.graph, source="enemy_base", target=self.node_EnemyFlagIndex)
        vf2s = nx.shortest_path(self.graph, source=self.node_EnemyFlagIndex, target=self.node_EnemyScoreIndex)
        #vb2s = nx.shortest_path(self.graph, source="enemy_base", target=self.node_EnemyScoreIndex)

        self.node_EnemyBaseToFlagIndex = "enemy_base_to_flag"
        self.graph.add_node(self.node_EnemyBaseToFlagIndex)
        self.positions["enemy_base_to_flag"] = None
        for vertex in vb2f:
            self.graph.add_edge(self.node_EnemyBaseToFlagIndex, vertex, weight = 1.0)
        
        self.node_EnemyFlagToScoreIndex = "enemy_flag_to_score" 
        self.graph.add_node(self.node_EnemyFlagToScoreIndex)
        self.positions["enemy_flag_to_score"] = None
        for vertex in vf2s:
            self.graph.add_edge(self.node_EnemyFlagToScoreIndex, vertex, weight = 1.0)
        
        self.node_EnemyBaseToScoreIndex = "enemy_base_to_score"
        self.graph.add_node(self.node_EnemyBaseToScoreIndex)
        self.positions["enemy_base_to_score"] = None
       # for vertex in vb2s:
       #     self.graph.add_edge(self.node_EnemyBaseToScoreIndex, vertex, weight = 1.0)

        ## node = self.makeNode(self.game.enemyTeam.flag.position)
        self.distances = nx.single_source_shortest_path_length(self.graph, self.node_EnemyFlagToScoreIndex)

        self.graph.remove_node("base")
        self.graph.remove_node("enemy_base")
        self.graph.remove_node(self.node_EnemyBaseToFlagIndex)
        self.graph.remove_node(self.node_EnemyFlagToScoreIndex)
        self.graph.remove_node(self.node_EnemyBaseToScoreIndex)

        self.updateEdgeWeights()

        self.paths = {b: None for b in self.game.team.members}

        self.visualizer = VisualizerApplication(self)
        self.visualizer.setDrawHookPreWorld(self.drawPreWorld)
        self.visualizer.setDrawHookPreBots(self.drawPreBots)
        self.visualizer.setDrawHookEnd(self.drawEnd)
        # self.visualizer.setKeyboardHook(self.keyboard)

    def getDistance(self, x, y):
        n = self.terrain[y][x]
        if n:
            return self.distances[n]
        else:
            return 0.0



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
    
        self.graph = g

    def getNodeIndex(self, position):
        i = int(position.x)
        j = int(position.y)
        width = self.graph.graph["map_width"]
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
                    self.graph[a][b]['weight'] = w

        for j in range(0, height-1):
            for i in range(0, width):
                a = self.terrain[j][i]
                b = self.terrain[j+1][i]
                if a and b:
                    w = max(255 - 4*(self.distances[a] + self.distances[b]), 0)
                    self.graph[a][b]['weight'] = w


    def tick(self):
        for bot in self.game.bots_alive:
            if bot.state == BotInfo.STATE_IDLE:
                if not bot.flag:
                    # go to flag
                    dst = self.game.enemyTeam.flag.position
                    message = 'go to flag'
                else:
                    # go home
                    dst = self.game.team.flagScoreLocation
                    message = 'go home'

                # calculate the shortest path between the bot and the target using our weights
                srcIndex = self.getNodeIndex(bot.position)
                dstIndex = self.getNodeIndex(dst)
                pathNodes = nx.shortest_path(self.graph, srcIndex, dstIndex, 'weight')

                pathLength = len(pathNodes)
                if pathLength > 0:
                    path = [self.positions[p] for p in pathNodes if self.positions[p]]
                    if len(path) > 0:
                        orderPath = path[::10]
                        orderPath.append(path[-1]) # take every 10th point including last point
                        self.issue(commands.Move, bot, orderPath, description = message) 
                        self.paths[bot] = path    # store the path for visualization

        self.visualizer.tick()

    def drawPreWorld(self, visualizer):
        blocks = self.level.blockHeights
        width, height = len(blocks), len(blocks[0])

        furthest = max([self.distances[n] for n in itertools.chain(*self.terrain) if n])

        for i, j in itertools.product(range(width), range(height)):            
            # average weights of edges connected to this node
            sum, count = 0, 0
            node = self.terrain[j][i]
            if node:
                for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ni, nj = i + offset[0], j + offset[1]
                    if ni < 0 or ni >= width or nj < 0 or nj >= height:
                        continue
                    neighbour = self.terrain[nj][ni]
                    if neighbour:
                        sum, count = sum + self.graph[node][neighbour]['weight'], count + 1
            if count:
                d = sum / count
            else:
                d = 32

            if self.level.blockHeights[i][j] == 1:
                visualizer.drawPixel((i, j), QtGui.qRgb(196, 196, 196))
            elif self.level.blockHeights[i][j] >= 2:            
                visualizer.drawPixel((i, j), QtGui.qRgb(64, 64, 64))
            else:
                visualizer.drawPixel((i, j), QtGui.qRgb(d,d,d))
                

    def drawPreBots(self, visualizer):
        for name, bot in self.game.bots.items():
            if bot.position is None:
                continue
            
            if 'Red' in name:
                color = QtGui.qRgb(255,0,0)
                pathColor = QtGui.qRgb(127,0,0)
            else:
                color = QtGui.qRgb(0,0,255)
                pathColor = QtGui.qRgb(0,0,127)
                
            if bot.health <= 0.0:
                color = QtGui.qRgb(0,0,0)

            if (bot.health > 0) and (bot in self.paths) and self.paths[bot]:
                path = self.paths[bot]
                pLast = bot.position
                for p in path:
                    visualizer.drawPixel((int(p.x), int(p.y)), QtGui.qRgb(255,255,0))
                    # visualizer.drawRay(pLast, p, color)
                    pLast = p

    def drawEnd(self, visualizer):
        pass

