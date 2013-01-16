#!/usr/bin/python2.7 -u
import sys
sys.path.append('./game/impl-1.7-py2.7.egg')

import os
import glob
from inspect import isclass
import importlib
import time
import socket
import logging

from game import networkclient

import api

logger = logging.getLogger("client")

def flushLog(logger):
    for h in logger.handlers:
        try:
            h.flush()
        except:
            pass

def getCommander(name, path):
    """Given a Commander name, import the module and return the class
    object so it can be instantiated for the competition."""

    files = []
    classname = None
    if name:
        filename, _, classname = name.rpartition('.')
        files.append(filename)
    else:
        files = glob.glob(os.path.join(path, '*.py'))

    modules = []
    for file in files:
        try:
            modulename, _ = os.path.splitext(os.path.basename(file))
            modules.append(importlib.import_module(modulename))
        except (ImportError, SyntaxError) as e:
            logger.error("ERROR: While importing '%s', %s." % (file, e))
            flushLog(logger)
            raise

    candidates = []
    for module in modules:
        for c in dir(module):
            # Check if this Commander was explicitly exported in the module.
            if hasattr(module, '__all__') and not c in module.__all__: continue
            # Discard private classes or the base class.
            if c.startswith('__') or c == 'Commander': continue
            # Match the class by the specified sub-name.
            if classname is not None and classname not in c: continue

            # Now check it's the correct derived class...
            cls = getattr(module, c)
            try:
                if isclass(cls) and issubclass(cls, api.Commander):
                    candidates.append(cls)
            except TypeError:
                pass

    if len(candidates) == 0:
        if name:
            logger.error('Error: Unable to find commander {} on path {}'.format(name, path))
            flushLog(logger)
        else:
            logger.error('Error: Unable to find any commanders on path {}'.format(path))
            flushLog(logger)
        return None
    elif len(candidates) > 1:
        logger.error('Error: Found more than one commander: {}'.format([c.__name__ for c in candidates]))
        flushLog(logger)
        return None
    else:
        cls = candidates[0]
        logger.debug('Found candidate {}'.format(cls.__name__))
        flushLog(logger)
        return cls




def main(args):
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--path', required=False, default='.')                  # optional path to look in for commanders
    parser.add_argument('--name', required=False, default='network_client')     # optional path for name of client
    parser.add_argument('--serverHost', required=False, default='localhost')
    parser.add_argument('--serverPort', type=int, required=False, default=41041)
    parser.add_argument('commander', nargs=1)                                   # mandatory client file/class name
    args, _ = parser.parse_known_args()

    if args.path:
        sys.path.insert(0, args.path)

    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.addHandler(logging.FileHandler(os.path.join('logs', args.name + '.log'), mode='w+'))
    logger.setLevel(logging.DEBUG)
    flushLog(logger)

    commanderCls = getCommander(args.commander, args.path)
    if not commanderCls:
        sys.exit(1)

    logger.debug('CLIENT: Initializing on {}:{}'.format(args.serverHost, args.serverPort))
    flushLog(logger)

    wrapper = networkclient.NetworkClient((args.serverHost, args.serverPort), commanderCls, args.name)

    logger.debug('CLIENT: Starting...')

    flushLog(logger)
    try:
        wrapper.run() 
    except networkclient.DisconnectError:
        pass

    logger.debug('CLIENT: Finished!')
    flushLog(logger)



from traceback import extract_tb

def format(tb, limit = None):
    extracted_list = extract_tb(tb)
    list = []
    for filename, lineno, name, line in extracted_list:
        item = '%s(%d): error in %s' % (filename,lineno,name)
        if line:
            item = item + '\n\t%s' % line.strip()
        else:
            item = item + '.'
        list.append(item)
    return list


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception as e:
        logger.critical(str(e))
        tb_list = format(sys.exc_info()[2])
        for s in tb_list:
            logger.critical(s)
        flushLog(logger)
        raise
