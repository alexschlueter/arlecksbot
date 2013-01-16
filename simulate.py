#################################################################################
#  This file is part of The AI Sandbox.
#
#  Copyright (c) 2007-2012, AiGameDev.com
#
#  Credits:         See the PEOPLE file in the base directory.
#  License:         This software may be used for your own personal research
#                   and education only.  For details, see the LICENSING file.
#################################################################################

import bootstrap
import random

from aisbx import platform
from aisbx import callstack

from game.application import CaptureTheFlag


# By default load these commanders.
defaults = ['examples.BalancedCommander', 'mycmd.PlaceholderCommander']

# Possible levels that can be used.
levels = ['map00', 'map01', 'map10', 'map11', 'map20', 'map21', 'map30']


def main(PreferedRunner, args, accel, **kwargs):
    """
        Setup our custom demo application, as well as a window-mode runner,
        and launch it.  This function returns once the demo is over.
            - If RCTRL+R is pressed, the application is restarted.
            - On RCTRL+F, the game code is dynamically refreshed.
    """

    while True:
        runner = PreferedRunner()
        if accel:
            runner.accelerate()

        if not args:
            args = defaults

        app = CaptureTheFlag(args, **kwargs)
        if not runner.run(app):
            break
        r = app.reset
        del runner
        del app

        if not r:
            break
        else:
            import gc
            gc.collect()

            from reload import reset
            reset()


# This is the entry point for the whole application.  The main function is
# called only when the module is first executed.  Subsequent resetting or
# refreshing cannot automatically update this __main__ module.
if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--console', action='store_true', default=False,            
                help='Run the simulation in headless mode without opening a graphical window, logging information to the console instead.')
    parser.add_argument('-a', '--accelerate', action='store_true', default=False,
                help='Step the simulation as fast as possible, whether or not a window is open.  Disable vsync in .cfg file for faster performance.')
    parser.add_argument('-l', '--level', default=random.choice(levels),
                help='Specify which level should be loaded, e.g. map00 or map21.  These are loaded from the .png and .ini file combination in #/assets/.')
    parser.add_argument('competitors', nargs='*',
                help='The name of a script and class (e.g. mybot.Placeholder) implementing the Commander interface.  Files are exact, but classes match by substring.')
    args, _ = parser.parse_known_args()

    try:
        if args.console:
            main(platform.ConsoleRunner, args.competitors, accel=args.accelerate, level=args.level)
        else:
            main(platform.WindowRunner, args.competitors, accel=args.accelerate, level=args.level)

    except Exception as e:
        print >> sys.stderr, str(e)
        tb_list = callstack.format(sys.exc_info()[2])
        for s in tb_list:
            print >> sys.stderr, s
        raise
