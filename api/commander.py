#################################################################################
#  This file is part of The AI Sandbox.
#
#  Copyright (c) 2007-2012, AiGameDev.com
#
#  Credits:         See the PEOPLE file in the base directory.
#  License:         This software may be used for your own personal research
#                   and education only.  For details, see the LICENSING file.
#################################################################################

import os
import sys
import logging


class Commander(object):
    """
    The base class for Commanders, that give orders to the team members.
    This class should be inherited from to create your own competition Commander.
    You must implement `tick(self)` in your custom Commander.
    """


    def initialize(self):
        """
        Use this function to setup your bot before the game starts.
        You can also set self.verbose = True to get more information about each bot visually.

        You should not issue orders during initialize.
        """
        pass


    def tick(self):
        """
        Override this function for your own bots.  Here you can access all the information in `self.game`,
        which includes game information, and `self.level` which includes information about the level.

        You can send commands to your bots using the `self.issue()` function in this class.
        """
        raise NotImplementedError


    def shutdown(self):
        """
        Use this function to teardown your bot after the game is over.
        """
        pass


    def issue(self, CommandClass, bot, *args, **dct):
        """
        Issue a command for a single bot, with optional arguments depending on the command.

        `CommandClass`: must be one of `[api.commands.Defend, api.commands.Attack, api.commands.Move, api.commands.Charge]`
        """
        if not self.verbose and 'description' in dct:
            del dct['description']

        self.commandQueue.append(CommandClass(bot.name, *args, **dct))


    def __init__(self, nick, **kwargs):
        super(Commander, self).__init__()

        self.nick = nick
        self.name = self.__class__.__name__
        """
        The name of this commander.
        """

        self.log = logging.getLogger(self.name)
        """
        The logging object that should be used for debug printing.
        """
        if not self.log.handlers:
            try:
                module = sys.modules[self.__class__.__module__].__file__
                filename = os.path.join(os.path.dirname(module), 'logs', self.name+'.log')

                dir = os.path.split(filename)[0]
                if not os.path.isdir(dir):
                    os.makedirs(dir)

                output = logging.FileHandler(filename)
                self.log.addHandler(output)
                self.log.setLevel(logging.DEBUG)
            except OSError as e:
                # error making the logging directory
                pass
            except IOError as e:
                # error opening the log file
                pass

        self.verbose = False
        """
        Set this to true to enable the display of the bot command descriptions next to each bot.
        """

        self.level = None
        """
        The LevelInfo object describing the current level.
        """

        self.game = None
        """
        The GameInfo object describing this Commander's knowledge of the current state of the game.
        """

        self.commandQueue = [] # the queue were issues commands are stored to be run later by the game

    # internal
    def setGameInfo(self, info):
        self.game = info.game

    # internal
    def isReady(self):
        return True

    # internal
    def gatherCommands(self):
        pass

    # internal
    def clearCommandQueue(self):
        self.commandQueue = []


