import sys
import random
import itertools
from visibility import Wave

from api import Commander, commands, gameinfo
from api.vector2 import Vector2


from PySide import QtGui, QtCore
import networkx as nx

SCALE = 10

def square(x): return x*x
 

class VisualizerWindow(QtGui.QWidget):    
                
    def __init__(self, commander):
        super(VisualizerWindow, self).__init__()
        
        self.commander = commander
        
        self.resize(88*SCALE, 50*SCALE)
        self.center()
        self.setWindowTitle('Capture The Flag')
        
        self.show()

    def keyPressEvent(self, e):
        if hasattr(self, 'keyboardHook'):
            self.keyPressHook(self, e)  
            self.update()
            

    def center(self):
        qr = self.frameGeometry()
        cp = QtGui.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def paintEvent(self, e):
        self.paint = QtGui.QPainter()
        self.paint.begin(self)
        self.drawGame()
        self.paint.end()
        self.paint = None
        
    def drawGame(self):

        if hasattr(self, 'preWorldHook'):
            self.preWorldHook(self)     
        #blocks
        for i, j in itertools.product(range(88), range(50)):            
            if self.commander.level.blockHeights[i][j] == 1:
                self.drawPixel((i, j), QtGui.qRgb(196, 0, 196))
            elif self.commander.level.blockHeights[i][j] >= 2:            
                self.drawPixel((i, j), QtGui.qRgb(64, 0, 64))

        
        if hasattr(self, 'preBotHook'):
            self.preBotHook(self)     

        #bots                    
        for name, bot in self.commander.game.bots.items():
            if bot.position is None:
                continue
            
            if 'Red' in name:
                if bot.seenlast > 0.0:
                    color = QtGui.qRgb(150,0,0)
                else:
                    color = QtGui.qRgb(255,0,0)
            else:
                if bot.seenlast > 0.0:
                    color = QtGui.qRgb(0,0,150)
                else:
                    color = QtGui.qRgb(0,0,255)
                
            if bot.health <= 0.0:
                color = QtGui.qRgb(0,0,0)

            self.drawCircle(bot.position, color)
            self.drawRay(bot.position, bot.facingDirection, QtGui.qRgb(0,0,0))

        #end 
        if hasattr(self, 'endDrawHook'):
            self.endDrawHook(self)                      

    def drawLine(self, (x1, y1), (x2, y2), color):
        self.paint.setBrush(QtGui.QColor(color))
        self.paint.drawLine(x1*SCALE, y1*SCALE, x2*SCALE, y2*SCALE)

    def drawRay(self, (x, y), (u, v), color):
        self.drawLine((x, y), (x+u*2.0, y+v*2.0), color)

    def drawCircle(self, (x, y), color, scale = 1.0):
        self.paint.setBrush(QtGui.QColor(color))
        rectangle = QtCore.QRectF((x-scale*0.5)*SCALE, (y-scale*0.5)*SCALE, scale*SCALE, scale*SCALE)
        self.paint.drawEllipse(rectangle)

    def drawPixel(self, (x, y), color): 
        self.paint.setBrush(QtGui.QColor(color))
        self.paint.drawRect(x*SCALE, y*SCALE, SCALE, SCALE)
        

class VisualizerApplication(QtGui.QApplication):

    def __init__(self, commander):
        super(VisualizerApplication, self).__init__([])
        self.window = VisualizerWindow(commander)

    def tick(self):
        self.window.update()
        self.processEvents()

    def setDrawHookPreWorld(self, hook):
        self.window.preWorldHook = hook

    def setDrawHookPreBots(self, hook):
        self.window.preBotHook = hook

    def setDrawHookEnd(self, hook):
        self.window.endDrawHook = hook

    def setKeyboardHook(self, hook):
        self.window.keyPressHook = hook         
