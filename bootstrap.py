import sys
import os
import argparse
import inspect

# Configure the directory you installed The AI Sandbox into using this global
# variable.  You can also specify --sbxdir=~/TheAiSandbox on the command
# line, or use the AISANDBOX_DIR environment variable so it's found
# automatically for all applications.
SBX_WORKING_DIR = None


# The binary directory is most often detected automatically from the
# installation folder.  If you want to specify this manually, you can use
# this global variable, or the command parameter --sbxbin or the environment
# variable called AISANDBOX_BIN.
SBX_BINARY_DIR = None


# You need to have a version of The AI Sandbox that matches this SDK version
# number.  More recent versions of The AI Sandbox may work, but ideally you
# should use the update scripts or grab the newest versions from the
# http://aisandbox.com/ download page.
SBX_REQUIRED_VERSION = "0.20.7"



def find_eggs(path):
    """Scan the specified directory for packaged EGG modules, and add them
    to the Python path so they can be imported as any other module."""

    eggs = []
    for folder, subs, files in os.walk(path):
        for filename in [f for f in files if f.endswith('.egg')]:
            eggs.append(os.path.join(folder, filename))
    sys.path.extend([os.path.abspath(e) for e in eggs])


def setup_paths(binaryDir, appDir):
    """Given a binary directory, add necessary paths to the Python system for
    importing modules and egg files."""

    paths = [
        binaryDir,
        os.path.join(binaryDir, 'lib'),
        os.path.join(binaryDir, 'scripts'),
    ]    
    sys.path.extend([os.path.normpath(p) for p in paths])

    find_eggs(paths[0])
    find_eggs(appDir)


def setup_directory(workDir, appDir):
    """Knowing the working directory, make sure this is active and tell the
    AI Sandbox module of the starting directory to find various data files."""

    os.chdir(workDir)

    from aigd import ApplicationFramework
    ApplicationFramework.setInitialDirectory(appDir)


def setup_version(requiredVersion):
    """Knowing the required version of The AI Sandbox, check if it's there and
    perform and update if necessary."""

    if not requiredVersion:
        return

    try:        
        try:
            from aisbx import version            
            if version.checkValid(requiredVersion):
                return
            else:        
                version.doUpdate()

        except ImportError:
            print >>sys.stderr, "ERROR: Couldn't initialize The AI Sandbox version %s.  Starting update..." % requiredVersion
        
            import subprocess
            import winshell
            subprocess.call(['update.exe'], cwd = os.path.join(winshell.folder('local_appdata'), 'AiGameDev.com', 'The AI Sandbox'), shell = True)
    except:
        print >>sys.stderr, "ERROR: Fatal problem initializing The AI Sandbox version %s!  Please update.\n" % requiredVersion
        print >>sys.stderr, "  ", os.path.join('%LocalAppData%', 'AiGameDev.com', 'The AI Sandbox'), "\n"
    
    sys.exit(-1)


def select_working_folder(options):
    """Setup the working directory from one of multiple configurable sources.
    In order, the command line, manually specified global variables, the
    execution environment, and the current directory as a fallback."""

    def hasAllSubFolders(folder, sub):
        for f in sub:
            if not os.path.isdir(os.path.join(folder, f)):
                return False
        return True

    for folder in [os.path.abspath(os.path.expanduser(o)) for o in options if o is not None]:

        if not os.path.isdir(folder):
            continue        

        if hasAllSubFolders(folder, ['binaries', 'output', 'config', 'cache']):
            return folder

    print >>sys.stderr, """\
ERROR: Cannot find The AI Sandbox installation folder on your computer.

Please specify any of the following:
    * Parameter --sbxdir=<DIR> on the command line.
    * A global variable at the top of bootstrap.py.
    * The environment variable AISANDBOX_DIR.
    * Set the current working directory to this location.

"""
    sys.exit(-1)


def select_binary_folder(options):
    """Setup the binaries folder in a similar fashion.  Either the command
    line, a manually specified global variable, the execution environment,
    or a directory specified in config/environment.pth."""

    for folder in [o for o in options if o is not None]:
        if inspect.isfunction(folder):
            try:
                folder = folder()
            except Exception:
                continue
        folder = os.path.abspath(os.path.expanduser(folder))

        if not os.path.isdir(folder):
            continue

        for f in ['aigd.so', 'aigd.pyd']:
            if os.path.exists(os.path.join(folder, f)):
                return folder

    print >>sys.stderr, """\
ERROR: Cannot find a valid binaries folder for The AI Sandbox.

Make sure the files are installed correctly.  Alternatively, specify:
    * Parameter --sbxbin=<DIR> on the command line.
    * A global variable at the top of bootstrap.py.
    * The environment variable AISANDBOX_BIN.
    * A file called binaries.pth in the 'config' directory.

"""
    sys.exit(-1)


def initialize():
    """The main entry point of the bootstrap module, used to setup everything
    from paths to working directories and platform versions."""

    # Check for command line arguments if there are any.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--sbxdir')
    parser.add_argument('--sbxbin')
    args, _ = parser.parse_known_args()

    # First find the installation directory of The AI Sandbox for these options.
    workDir = select_working_folder([
        args.sbxdir,
        SBX_WORKING_DIR,
        os.environ.get('AISANDBOX_DIR', None),
        os.getcwd(),
    ])

    # Then try to deduce the binaries folder, given the versioning system.
    binDir = select_binary_folder([
        args.sbxbin,
        SBX_BINARY_DIR,
        os.environ.get('AISANDBOX_BIN', None),
        os.path.join(workDir, 'binaries'),
        lambda: os.path.join(workDir, open(os.path.join(workDir, 'config', 'environment.pth'), 'r').readline().rstrip()),
    ])

    appDir = os.path.join(os.path.split(os.path.abspath(sys.argv[0]))[0],'')

    if os.path.isdir(os.path.join('source', 'platform')):
        sys.path.append(os.path.join('source', 'platform'))

    # To find the dynamic libraries like Ogre, we need to set the path manually.
    if 'linux' in sys.platform and binDir not in os.environ.get('LD_LIBRARY_PATH', ''):
        os.environ['LD_LIBRARY_PATH'] = binDir
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except OSError:
            print >>sys.stderr, "Fatal error configuring the dynamic library path."
            sys.exit(-1)

    if 'win32' in sys.platform and binDir not in os.environ.get('PATH', ''):
        os.environ['PATH'] += ';' + binDir

    setup_paths(binDir, appDir)
    setup_directory(workDir, appDir)
    setup_version(SBX_REQUIRED_VERSION)


# When importing this module, presumably first, it performs initialization by default.
initialize()

