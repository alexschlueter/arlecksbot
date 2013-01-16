import random

from api import Commander
from api import commands
from api.vector2 import Vector2
from api.gameinfo import BotInfo
from api.gameinfo import MatchCombatEvent

def contains(area, position):
    start, finish = area
    return position.x >= start.x and position.y >= start.y and position.x <= finish.x and position.y <= finish.y

class KilroyCommander(Commander):
    """
    see further documentation at http://code.google.com/p/sqlitebot/wiki/Kilroy
    """

    lastEventCount = 0

    defTopLeft = 0
    defTopRight = 0
    defBotLeft = 0
    defBotRight = 0
    defMidLeft = 0
    defMidTop = 0
    defMidRight = 0
    defMidBot = 0
    defAny = 0
    
    def initialize(self):
        #self.attacker = None
        self.verbose = False
        self.enemyFlagLocation = self.game.enemyTeam.flag.position

        #types - def,att,scr,spa
        #spa experiment depends on '4,4' offset and kilroy start in top-right
        #2 def, 2 att, rest scramble the middle
        #FIX - the below is very hard-coded(and duplicative) and could be fixed to a more dynamic assignment function depending on the team assigned and roles needed - perhaps also as class properties rather than a dictionary also
        self.info = {'Red0': {'timeLastCommand': 0, 'role': 'att1', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': ''},\
                     'Red1': {'timeLastCommand': 0, 'role': 'att2', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': ''},\
                     'Red2': {'timeLastCommand': 0, 'role': 'attX', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Red3': {'timeLastCommand': 0, 'role': 'def1', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':2, 'flagY':2},\
                     'Red4': {'timeLastCommand': 0, 'role': 'def2', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':-2, 'flagY':-2},\
                     'Red5': {'timeLastCommand': 0, 'role': 'def3', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':2, 'flagY':-2},\
                     'Red6': {'timeLastCommand': 0, 'role': 'def4', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Red7': {'timeLastCommand': 0, 'role': 'scr4', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Red8': {'timeLastCommand': 0, 'role': 'scr5', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Red9': {'timeLastCommand': 0, 'role': 'scr6', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Blue0': {'timeLastCommand': 0, 'role': 'att1', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': ''},\
                     'Blue1': {'timeLastCommand': 0, 'role': 'att2', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': ''},\
                     'Blue2': {'timeLastCommand': 0, 'role': 'attX', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Blue3': {'timeLastCommand': 0, 'role': 'def1', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':2, 'flagY':2},\
                     'Blue4': {'timeLastCommand': 0, 'role': 'def2', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':-2, 'flagY':-2},\
                     'Blue5': {'timeLastCommand': 0, 'role': 'def3', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':2, 'flagY':-2},\
                     'Blue6': {'timeLastCommand': 0, 'role': 'def4', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Blue7': {'timeLastCommand': 0, 'role': 'scr4', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Blue8': {'timeLastCommand': 0, 'role': 'scr5', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0},\
                     'Blue9': {'timeLastCommand': 0, 'role': 'scr6', 'threshEvade': 30, 'distEvade': 4, 'botTrack': '', 'state': '', 'flagX':0, 'flagY':0}}
                     
        #self.info['Red4']['timeLastCommand'] = 40

	# flanking setup from BalancedCommander
        # Calculate flag positions and store the middle.
        ours = self.game.team.flag.position
        theirs = self.game.enemyTeam.flag.position
        self.middle = (theirs + ours) / 2.0

        # Now figure out the flanking directions, assumed perpendicular.
        d = (ours - theirs)
        self.left = Vector2(-d.y, d.x).normalized()
        self.right = Vector2(d.y, -d.x).normalized()
        self.front = Vector2(d.x, d.y).normalized()

	self.flagRunner = ''
	
    def tick(self):

        #print("tick")
	#self.log.info('tick')
        #enemyFlagLocation = self.game.enemyTeam.flag.position
        timePassed = self.game.match.timePassed
        waitCommand = 2
        #print("%f" % (timePassed+waitCommand))

        #############################
	#do we have flag?
        gotFlag = False
        
        #only allow other runner not holding flag nearest flag to go
	#closestOpenRunner = 1000
        runnerName0 = ''
        runnerName1 = ''
        listDistRunner = []
        listDistRunnerName = []
        
        for bot in self.game.bots_alive:

	    #if bot.state != bot.STATE_SHOOTING:
	    #    print("debug")

            #FIX - make this a function check on bot.name
            if self.info[bot.name]['role'].find('att') != -1:
                if bot.flag:
                    gotFlag = True
                    self.flagRunner = bot.name
                    #kick defending bot with flag back to idle state for reevaluation
                    if bot.state == bot.STATE_DEFENDING and bot.state != BotInfo.STATE_SHOOTING:
                        self.info[bot.name]['state'] = 'idle'
                        
                    #print("flagRunner:%s" % (self.flagRunner))

                else:
                    distRunner = (bot.position-self.game.enemyTeam.flag.position).length()
                    listDistRunner.append(distRunner)
                    listDistRunnerName.append(bot.name)
                    """
                    if distRunner < closestOpenRunner:
                        closestOpenRunner = distRunner
                        runnerName = bot.name
                    """    


            #print("%s state = %d" % (bot.name,bot.state))
            #if bot.state == bot.STATE_IDLE or bot.state == bot.STATE_UNKNOWN:
            if bot.state == bot.STATE_IDLE:                
                #print("%s state = %d" % (bot.name,bot.state))
                self.info[bot.name]['state'] = 'idle'

        #sort distances and pick closest runners
        listSort = listDistRunner[:]
        #print listSort
        listSort.sort()
        close0 = None
        close1 = None
        
        if len(listSort) > 0:
            close0 = listSort[0]
        if len(listSort) > 1:    
            close1 = listSort[1]
        #print close0,close1

        i = 0
        for botDist in listDistRunner:
            #print botDist
            if botDist == close0:
                runnerName0 = listDistRunnerName[i]
            elif botDist == close1:
                runnerName1 = listDistRunnerName[i]

            i = i + 1
            
        #print runnerName0,runnerName1

        
        #kick defending runner back to idle for reevaluation        
        for bot in self.game.bots_alive:
#            if (bot.name == runnerName0 or bot.name == runnerName1) and (bot.position-self.game.enemyTeam.flagSpawnLocation).length() > 0.2 and self.info[bot.name]['state'] == 'defend_runner':
            if (bot.name == runnerName0) and (bot.position-self.game.enemyTeam.flagSpawnLocation).length() > 0.2 and self.info[bot.name]['state'] == 'defend_runner':
                print "runner set to idle %s" % (bot.name)
                self.info[bot.name]['state'] = 'idle'
        
                
        #############################
	#handle offense/attacker bot(s) init
        for bot in self.game.bots_alive:   #was bots_available
            #if self.info[bot.name]['role'].find('att') != -1:
            #    print "attacker %s state %d" % (bot.name,bot.state)
            if self.info[bot.name]['state'] == 'idle':

                #FIX - make this a function check on bot.name
                if self.info[bot.name]['role'].find('att') != -1 and bot.state != BotInfo.STATE_SHOOTING:

                    #print "attacker %s state %d" % (bot.name,bot.state)
                    if bot.flag:
                        #bring it home
                        targetLocation = self.game.team.flagScoreLocation
                        self.issue(commands.Charge, bot, targetLocation, description = 'returning enemy flag!')
                        self.info[bot.name]['state'] = 'charge_home'

                    else:
        
                        #skip moving and defend our position if not chosen closest open runner
                        #if bot.name != runnerName0 and bot.name != runnerName1:
                        if bot.name != runnerName0:                        
                            #self.issue(commands.Defend, bot, (self.game.enemyTeam.botSpawnArea[0] - bot.position), description = 'defend facing enemy spawn')
                            defendAngles = self.bestDefend(bot)
                            self.issue(commands.Defend, bot, defendAngles, description = 'defend runner')
                            print "defend_runner %s" % (bot.name)
                            self.info[bot.name]['state'] = 'defend_runner'
                            
                            continue
                            
                        if not gotFlag: #team doesn't have flag
                            target = self.game.enemyTeam.flag.position
                        else:
                            target = self.game.enemyTeam.flagSpawnLocation

                        #only flank spawn location, not dropped flag in field
                        distFlagDisplace = (self.game.enemyTeam.flagSpawnLocation-self.game.enemyTeam.flag.position).length()
                        flank = self.getFlankingPositionFlag(bot, target)
                        if (target - flank).length() > (bot.position - target).length() or distFlagDisplace > 1:
                            if (bot.position - target).length() > 0.2:
                                #was Attack, but evasive behavior now so shouldn't be seen
                                #self.issue(commands.Attack, bot, target, description = 'attack from flank', lookAt=target)
                                self.issue(commands.Charge, bot, target, description = 'attack from flank')
                                self.info[bot.name]['state'] = 'charge_flag'
                                print "charge_flag %s" % (bot.name)
                            else:
                                defendAngles = self.bestDefend(bot)
                                #self.issue(commands.Defend, bot, (self.game.enemyTeam.botSpawnArea[0] - bot.position), description = 'defend facing enemy spawn')
                                self.issue(commands.Defend, bot, defendAngles, description = 'defend runner')
                                print "defend_runner %s" % (bot.name)
                                self.info[bot.name]['state'] = 'defend_runner'
                            
                        else:
                            flank = self.level.findNearestFreePosition(flank)
                            self.issue(commands.Charge, bot, flank, description = 'running to flank')
                            self.info[bot.name]['state'] = 'charge_flank'
                            print "charge_flank %s" % (bot.name)

        #############################
        #evasion                
	#handle offense/attacker bot(s)
        for bot in self.game.bots_alive:

            #FIX - make this a function check on bot.name
            #add bot types here to use evade
            if self.info[bot.name]['role'].find('att') != -1 or self.info[bot.name]['role'].find('scr') != -1 or self.info[bot.name]['role'].find('spa') != -1:

                if len(bot.seenBy) > 0 and timePassed > self.info[bot.name]['timeLastCommand'] and bot.state != BotInfo.STATE_SHOOTING:
                    
                    dist0 = (bot.seenBy[0].position - bot.position).length()
                    #print "runner seen! %f" % (dist0)
                    #ignore far away seenBy
                    if dist0 > self.info[bot.name]['threshEvade']:
                        continue

                    #FIX tune defending thresh
                    if dist0 > 20 and (bot.seenBy[0].state == bot.STATE_IDLE or bot.seenBy[0].state == bot.STATE_DEFENDING):
                        continue


                    print "runner evade"
                    #move bot away from enemy
                    
                    newPosition1 = self.level.findNearestFreePosition(bot.position + Vector2(self.info[bot.name]['distEvade'],self.info[bot.name]['distEvade']))
                    dist1 = (bot.seenBy[0].position - newPosition1).length()
                    newPosition2 = self.level.findNearestFreePosition(bot.position + Vector2(-self.info[bot.name]['distEvade'],-self.info[bot.name]['distEvade']))
                    dist2 = (bot.seenBy[0].position - newPosition2).length()
                    
                    finalPosition = Vector2(0.0,0.0)
                    if dist1 > dist2:
                        finalPosition = newPosition1
                    else:
                        finalPosition = newPosition2
                    
                    
                    #FIX - shortcut flank
                    #finalPosition = self.getFlankingPositionBot(bot, bot.seenBy[0].position)
                    
                    self.issue(commands.Attack, bot, finalPosition, description = 'evade', lookAt=bot.seenBy[0].position)
                    self.info[bot.name]['state'] = 'evade'
                    self.info[bot.name]['timeLastCommand'] = timePassed+waitCommand

                    self.info[bot.name]['threshEvade'] = self.info[bot.name]['threshEvade'] - 15 #threshDegrade
                    #FIX - not working, try flank
                    #self.info[bot.name]['distEvade'] = self.info[bot.name]['distEvade'] + 20

                """
                else: #cleanup set state
                    if len(bot.seenBy) == 0
                    if self.info[bot.name]['state'] == 'evade':
                        self.info[bot.name]['state'] = 'idle'
                """    

        #############################
        #scramble                
	#handle scramble bot(s)
        for bot in self.game.bots_available:

            #FIX - make this a function check on bot.name
            if self.info[bot.name]['role'].find('scr') != -1 and bot.state != BotInfo.STATE_SHOOTING:

                if len(bot.visibleEnemies) > 0 and bot.visibleEnemies[0].health > 0:
                    #FIX - choose closest visible and check angle for too close view angle threshold
                    self.issue(commands.Charge, bot, bot.visibleEnemies[0].position, description = 'charge enemy')
                else:
                    #pick a random position in the level to move to                               
                    halfBox = 0.4 * min(self.level.width, self.level.height) * Vector2(1, 1)
                
                    target = self.level.findRandomFreePositionInBox((self.middle + halfBox, self.middle  - halfBox))

                    #issue the order
                    if target:
                        self.issue(commands.Attack, bot, target, description = 'random patrol')

        #############################
        #spawncamp - not currently using this role because of spawncamp protections, but could be altered to camp further from spawn to catch bots exiting spawn               
	#handle spawncamp bot(s)
        for bot in self.game.bots_available:

            #FIX - make this a function check on bot.name
            if self.info[bot.name]['role'].find('spa') != -1 and bot.state != BotInfo.STATE_SHOOTING:

                spawnPosition = self.game.enemyTeam.botSpawnArea[1]
                offsetPosition = Vector2(spawnPosition.x+self.info[bot.name]['flagX'],spawnPosition.y+self.info[bot.name]['flagY'])

                offsetPosition = self.level.findNearestFreePosition(offsetPosition)
                
                if (offsetPosition - bot.position).length() > 9.0 : #need larger 9.0 radius units for braking to stop,etc
                    #self.issue(commands.Attack, bot, offsetPosition, description = 'moving to spawn',lookAt=self.game.enemyTeam.botSpawnArea[0])
                    self.issue(commands.Charge, bot, [Vector2(60.0,48.0),offsetPosition], description = 'moving to spawn')

                else:
                    self.issue(commands.Defend, bot, (spawnPosition - bot.position), description = 'defend facing spawn')

        #############################
        #visible enemies
        #only def,any use visible enemies (not att,etc)
                    
	enemyName = None
	enemyPosition = None
        closestEnemyDist = 1000

        for bot in self.game.bots_alive:
            if self.info[bot.name]['role'].find('def') != -1 or self.info[bot.name]['role'].find('any') != -1:

                #check for visible enemies
                #if bot.visibleEnemies != None:
                if len(bot.visibleEnemies) > 0:
                    for visibleEnemy in bot.visibleEnemies:
                        if visibleEnemy.health > 0:
                            enemyDist = (visibleEnemy.position - bot.position).length() 
                            if enemyDist < closestEnemyDist:
                                closestEnemyDist = enemyDist
                                #debug print "visibleEnemy:%s %f" % (visibleEnemy.name,enemyDist)
                                #self.log.info(bot.visibleEnemies)
                                #enemyPosition = bot.visibleEnemies[0].position		
                                enemyName = visibleEnemy.name
                                enemyPosition = visibleEnemy.position
                                #enemySeenBy = visibleEnemy.seenBy

	if enemyPosition != None:
	    #if nearby visible enemy, turn to face/defend
            numBotsFacing = 0
	    for bot in self.game.bots_alive:
                if self.info[bot.name]['role'].find('def') != -1 or self.info[bot.name]['role'].find('any') != -1:
                    if timePassed > self.info[bot.name]['timeLastCommand'] and bot.state != BotInfo.STATE_SHOOTING:
                                                
                        #if (enemyPosition - bot.position) != bot.facingDirection:
                        #FIX - sort by closest bot - not necessary at flag since clumped together
                        if (enemyPosition - bot.position).length() < 25 and numBotsFacing < 2: #was 30 distance
                            #and self.info[bot.name]['botTrack'] == ''
                            #self.log.info(enemyPosition-bot.position) 
                            #self.log.info(bot.facingDirection)
                            numBotsFacing = numBotsFacing + 1
                            print "%s defending visible bot" % (bot.name)
                            self.issue(commands.Defend, bot, (enemyPosition - bot.position), description = 'defending facing enemy bot')
                            self.info[bot.name]['timeLastCommand'] = timePassed+waitCommand
                            self.info[bot.name]['botTrack'] = enemyName
                            self.info[bot.name]['state'] = 'track_enemy'

        #############################
        #check combatEvents for latest activity - FIX - need to loop over last n items instead of just last(-1) item
	if len(self.game.match.combatEvents) > self.lastEventCount:
	    lastCombatEvent = self.game.match.combatEvents[-1]
	    #self.log.info('event:'+str(lastCombatEvent.type))
            if lastCombatEvent.instigator is not None:
	        print "event:%d %f %s %s" % (lastCombatEvent.type,lastCombatEvent.time,lastCombatEvent.instigator.name,lastCombatEvent.subject.name)
            else:
	        print "event:%d %f" % (lastCombatEvent.type,lastCombatEvent.time)
	    self.lastEventCount = len(self.game.match.combatEvents)

            ###############

            #remove dead enemies from tracking list	    	
	    if lastCombatEvent.type == MatchCombatEvent.TYPE_KILLED and (lastCombatEvent.subject.name.find(self.game.enemyTeam.name) != -1):
                deadBot = self.game.bots[lastCombatEvent.subject.name]
	        #remove bot name from our bots tracking list
                for bot in self.game.bots_alive:  #FIX couldn't get just self.game.bots to work
                    if self.info[bot.name]['botTrack'] == deadBot.name:
                        self.info[bot.name]['botTrack'] = ''
                        self.info[bot.name]['state'] = 'idle'
                        #print "remove enemy from track :%s: %s" % (bot.name,deadBot.name)


            #check for flag drop - type_killed doesn't register
	    if lastCombatEvent.type == MatchCombatEvent.TYPE_FLAG_DROPPED and (lastCombatEvent.subject.name.find(self.game.enemyTeam.name) != -1):
		print("flag runner killed")
		for bot in self.game.bots_alive:
		    if self.info[bot.name]['role'].find('att') != -1 and bot.state != BotInfo.STATE_SHOOTING:
                        self.info[bot.name]['state'] = 'idle'
		        #self.moveIdle(bot)


            #check for any nearby dead teammates to turn towards	    	
	    if lastCombatEvent.type == MatchCombatEvent.TYPE_KILLED and (lastCombatEvent.subject.name.find(self.game.team.name) != -1):
	        #face our last killed team member
		deadBot = self.game.bots[lastCombatEvent.subject.name]
	        #print "%s %s" % (deadBot.name, self.flagRunner)
                self.info[deadBot.name]['botTrack'] = ''
                
                """
		if deadBot == self.flagRunner:
		    print("flag runner killed")
		    for bot in self.game.bots_alive:
		        if self.info[bot.name]['role'].find('att') != -1 and bot.state != BotInfo.STATE_SHOOTING:
		            moveIdle(bot)
                """
                		    
        	for bot in self.game.bots_alive:
                    #FIX - don't swing to dead bots if swinging away from approaching enemy
                    #FIX - maybe just do a full scan defend rotate, starting toward direction of deadbot than defending just to deadbot position
                    if (self.info[bot.name]['role'].find('def') != -1 or self.info[bot.name]['role'].find('any') != -1) and bot.state != BotInfo.STATE_SHOOTING:
                        
                        if (deadBot.position - bot.position).length() < 20:
                            print "%s defend deadBot" % (bot.name)
                            self.issue(commands.Defend, bot, (deadBot.position - bot.position), description = 'defending facing dead bot')
                            self.info[bot.name]['timeLastCommand'] = timePassed+waitCommand
                            self.info[bot.name]['state'] = 'track_deadbot'



        #############################
	#periodically reset back to facing enemy flag
        #FIX - just run on available bots
        for bot in self.game.bots_alive:

            #FIX - evade decay won't happen with current faster refresh of 2 sec
            if timePassed > self.info[bot.name]['timeLastCommand'] and bot.state != BotInfo.STATE_SHOOTING:                
                self.info[bot.name]['threshEvade'] = 30
                self.info[bot.name]['distEvade'] = 4
                
                if self.info[bot.name]['role'].find('def') != -1 or self.info[bot.name]['role'].find('any') != -1:
                    self.moveOrFace(bot)
		    

    #############################    
    #defense
    def moveOrFace(self, bot):

        #FIX - below flow is messy
        # defend the flag!
        targetPosition = self.game.team.flagSpawnLocation
        targetMin = targetPosition - Vector2(8.0, 8.0) #was 8.0, 8.0
        targetMax = targetPosition + Vector2(8.0, 8.0)

        if self.info[bot.name]['role'].find('def4') == 0:
            targetPosition = self.game.enemyTeam.flagScoreLocation
        
        #if (targetPosition - bot.position).length() > 9.0 and (targetPosition - bot.position).length() > 3.0 :
        if (targetPosition - bot.position).length() > 3.0: #was 0.3
            if self.info[bot.name]['state'] != 'station_attack':
                self.info[bot.name]['state'] = 'station_attack'
                print "%s station_attack" % (bot.name)
                
                while True:
                    #position = self.level.findRandomFreePositionInBox((targetMin,targetMax))

                    #position = targetPosition
                    #print("spawn %f %f" % (position.x,position.y)) 
                    position = Vector2(targetPosition.x+self.info[bot.name]['flagX'],targetPosition.y+self.info[bot.name]['flagY'])
                    position = self.level.findNearestFreePosition(position)

                    if self.info[bot.name]['role'].find('def4') == 0:
                        self.issue(commands.Attack, bot, self.game.enemyTeam.flagScoreLocation, description = 'defending enemy return',lookAt=self.game.enemyTeam.botSpawnArea[1])
                    else:
                        self.issue(commands.Attack, bot, position, description = 'defending around flag',lookAt=self.game.enemyTeam.botSpawnArea[1]) #was self.enemyFlagLocation) corner 1 is map30 specific
                    break

                    """
                    if position and (targetPosition - position).length() > 3.0:
                        self.issue(commands.Attack, bot, position, description = 'defending around flag',lookAt=self.game.enemyTeam.botSpawnArea[1]) #was self.enemyFlagLocation) corner 1 is map30 specific
                        #defense clustered doesn't give any deadbot reaction time
                        #self.issue(commands.Attack, bot, targetPosition, description = 'defending around flag',lookAt=self.enemyFlagLocation)
                        break
                    """
        else:
            if self.info[bot.name]['state'] != 'station_defend': #if one defender out of sync then everyone reset, FIX - doesn't apply to def away from our flag
                self.info[bot.name]['state'] = 'station_defend'
                print "%s station_defend" % (bot.name)

                for bot in self.game.bots_alive:

                    defendAngles = self.bestDefend(bot)
                    
                    if self.info[bot.name]['role'] == 'def1' and self.info[bot.name]['state'] == 'station_defend':
                        #self.issue(commands.Defend, bot, [[Vector2(1.0,0.0),1.0],[Vector2(-1.0,0.0),1.0]], description = 'defending facing flag')
                        #swing north/south instead
                        #self.issue(commands.Defend, bot, [[Vector2(0.0,1.0),1.0],[Vector2(0.0,-1.0),1.0]], description = 'def1 at flag')
                        #self.issue(commands.Defend, bot, [[Vector2(0.0,1.0),1.0],[Vector2(0.1,-0.9),1.0]], description = 'def1 at flag')
                        self.issue(commands.Defend, bot, defendAngles, description = 'def1 at flag')
                    elif self.info[bot.name]['role'] == 'def2' and self.info[bot.name]['state'] == 'station_defend':
                        self.issue(commands.Defend, bot, defendAngles, description = '')
                    elif self.info[bot.name]['role'] == 'def3' and self.info[bot.name]['state'] == 'station_defend':
                        self.issue(commands.Defend, bot, defendAngles, description = '')
                    elif self.info[bot.name]['role'] == 'def4' and self.info[bot.name]['state'] == 'station_defend':
                        self.issue(commands.Defend, bot, defendAngles, description = 'def4 at flag')
                        
                    elif self.info[bot.name]['role'].find('any') != -1 and self.info[bot.name]['state'] == 'station_defend':
                        self.issue(commands.Defend, bot, (self.enemyFlagLocation - bot.position), description = 'defending facing flag')
                        #print("any defend %s" % (bot.name)

    def getFlankingPositionFlag(self, bot, target):
        flanks = [target + f * 16.0 for f in [self.left, self.right]]
        options = map(lambda f: self.level.findNearestFreePosition(f), flanks)
        return sorted(options, key = lambda p: (bot.position - p).length())[0]

    def getFlankingPositionBot(self, bot, target):
        # Now figure out the flanking directions, assumed perpendicular.
        d = (bot.position - target)
        left = Vector2(-d.y, d.x).normalized()
        right = Vector2(d.y, -d.x).normalized()
        front = Vector2(d.x, d.y).normalized()
        
        flanks = [target + f * 26.0 for f in [left, right]]
        options = map(lambda f: self.level.findNearestFreePosition(f), flanks)
        return sorted(options, key = lambda p: (bot.position - p).length())[0]
        
    def moveIdle(self, bot):
        self.issue(commands.Charge, bot, bot.position, description = 'charge to idle')

    def bestDefend(self, bot):

        thresh = 8 # was 20
        x_limit = self.level.width - thresh
        y_limit = self.level.height - thresh
        
        if bot.position.x < thresh and bot.position.y < thresh: #top-left
            defendAngles = [[Vector2(1.0,0.0),1.0],[Vector2(0.0,1.0),1.0]]
            self.defTopLeft = self.defTopLeft + 1
            if self.defTopLeft % 2 == 0:
                defendAngles.reverse()
        elif bot.position.x > x_limit and bot.position.y < thresh: #top-right
            defendAngles = [[Vector2(0.0,1.0),1.0],[Vector2(-1.0,0.0),1.0]]
            self.defTopRight = self.defTopRight + 1
            if self.defTopRight % 2 == 0:
                defendAngles.reverse()
        elif bot.position.x < thresh and bot.position.y > y_limit: #bottom-left
            defendAngles = [[Vector2(1.0,0.0),1.0],[Vector2(0.0,-1.0),1.0]]
            self.defBotLeft = self.defBotLeft + 1
            if self.defBotLeft % 2 == 0:
                defendAngles.reverse()            
        elif bot.position.x > x_limit and bot.position.y > y_limit: #bottom-right
            defendAngles = [[Vector2(-1.0,0.0),1.0],[Vector2(0.0,-1.0),1.0]]
            self.defBotRight = self.defBotRight + 1
            if self.defBotRight % 2 == 0:
                defendAngles.reverse()            

        elif bot.position.x < thresh and bot.position.y > thresh and bot.position.y < y_limit: #mid-left
            defendAngles = [[Vector2(0.0,1.0),1.0],[Vector2(0.1,-0.9),1.0]]
            self.defMidLeft = self.defMidLeft + 1
            if self.defMidLeft % 2 == 0:
                defendAngles.reverse()            
        elif bot.position.x > thresh and bot.position.x < x_limit and bot.position.y < thresh: #mid-top
            defendAngles = [[Vector2(1.0,0.0),1.0],[Vector2(-0.9,0.1),1.0]]
            self.defMidTop = self.defMidTop + 1
            if self.defMidTop % 2 == 0:
                defendAngles.reverse()            
        elif bot.position.x > x_limit and bot.position.y > thresh and bot.position.y < y_limit: #mid-right
            defendAngles = [[Vector2(0.0,1.0),1.0],[Vector2(-0.1,-0.9),1.0]]
            self.defMidRight = self.defMidRight + 1
            if self.defMidRight % 2 == 0:
                defendAngles.reverse()            
        elif bot.position.x > thresh and bot.position.x < x_limit and bot.position.y > y_limit: #mid-bottom
            defendAngles = [[Vector2(1.0,0.0),1.0],[Vector2(-0.9,-0.1),1.0]]
            self.defMidBot = self.defMidBot + 1
            if self.defMidBot % 2 == 0:
                defendAngles.reverse()            
   
        else:
            defendAngles = [[Vector2(0.0,1.0),1.0],[Vector2(0.0,-1.0),1.0]]
            self.defAny = self.defAny + 1
            if self.defAny % 2 == 0:
                defendAngles.reverse()            

        #move last item to first
        #defendAngles.insert(0,defendAngles[-1])
        #del defendAngles[-1]
       
        return defendAngles
    
            
        
        
        

