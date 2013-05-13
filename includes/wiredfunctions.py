import time
import os
import sys
import re
import base64
import logging
import platform
from subprocess import call
from time import time, strftime, localtime, timezone, altzone, daylight
try:
    # This will fail on python > 2.7
    from ssl import OPENSSL_VERSION
except:
    pass


def wiredTime(timestamp):
    parsed = localtime(float(timestamp))
    if daylight:  # use offset including DST
        offset = utcOffset(altzone)
    else:
        offset = utcOffset(timezone)
    try:
        parsed = strftime("%Y-%m-%dT%H:%M:%S", parsed) + offset
    except:
        return 0
    return str(parsed)


def utcOffset(offset):
    hours = abs(offset) // 3600
    minutes = abs(offset) % 3600 // 60
    #sign = (offset < 0 and '-') or '+'
    sign = (offset < 0 and '+') or '-'
    return '%c%02d:%02d' % (sign, hours, minutes)


def getPlatform():
    sysplatform = {'OS': "unkown", 'OSVersion': "unkown", 'ARCH': "unkown", 'TLSLib': "unkown"}
    if checkPlatform("Windows"):
        try:
            sysplatform['OS'] = platform.system()
            sysplatform['OSVersion'] = platform.version()
            sysplatform['ARCH'] = platform.machine()
            sysplatform['TLSLib'] = OPENSSL_VERSION
        except:
            pass
        return sysplatform

    uname = os.uname()
    try:
        sysplatform['OS'] = uname[0]
        sysplatform['OSVersion'] = uname[2]
        sysplatform['ARCH'] = uname[4]
        sysplatform['TLSLib'] = OPENSSL_VERSION
    except:
        pass
    return sysplatform


def initLogger(logfile, level):
    logFile = 1
    logStdOut = 1
    log = logging.getLogger("wiredServer")
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s: %(message)s', "%b %d %y - %H:%M:%S")
    filelevel = logging.DEBUG  # default for now
    if level.upper() == "DEBUG":
        filelevel = logging.DEBUG
    if level.upper() == "INFO":
        filelevel = logging.INFO
    if level.upper() == "WARNING":
        filelevel = logging.WARNING
    if level.upper() == "ERROR":
        filelevel = logging.ERROR
    if level.upper() == "NONE":
        logFile = 0
    if logFile:
        try:
            filehandler = logging.FileHandler(str(logfile), "a")
        except IOError:
            print "Failed to open Logfile %s" % logfile
            raise SystemExit
        filehandler.setLevel(filelevel)
        filehandler.setFormatter(formatter)
        log.addHandler(filehandler)
    if logStdOut:
        streamhandler = logging.StreamHandler()
        streamhandler.setLevel(logging.DEBUG)
        streamhandler.setFormatter(formatter)
        log.addHandler(streamhandler)
    return log


def tsplit(string, *delimiters):
    pattern = '|'.join(map(re.escape, delimiters))
    return re.split(pattern, string)


def checkPlatform(name):
    if name.upper() == str(platform.system()).upper():
        return 1
    return 0


def readBanner(filename):
    banner = ''
    if not os.path.exists(filename):
        return None
    with open(filename, "rb") as f:
        data = f.read(1)
        while data:
            banner += data
            data = f.read(1024)
    banner = base64.b64encode(banner)
    return banner


def loadConfig(confFile):
    #will read config file or create one with the required defaults
    from configobj import ConfigObj
    from validate import Validator
    default = """serverName = string(default="A re:Wired Server")
    cert = string(default="cert.pem")
    logFile = string(default="logfile")
    userIdleTime = integer(default=600)
    pingTimeout = integer(default=600)
    dbFile = string(default="rewiredDB.db")
    doIndex = boolean(default=True)
    fileRoot =string(default="files")
    indexInterval = integer(default=1800)
    host = string(default="0.0.0.0")
    serverDesc = string(default="A re:Wired Server")
    port = integer(default=2000)
    serverBanner = string(default="data/banner.png")
    trackerRegister = boolean(default=False)
    trackerUrl = list(default=list("wired.zankasoftware.com", "wired.zapto.org"))
    trackerDNS = string(default="")
    trackerCategory = string(default="")
    trackerBandwidth = integer(default=1000000)
    serverPidFile = string(default="server.pid")
    guestOn = boolean(default=True)
    adminOn = boolean(default=True)
    # Disable users allowed to kick/ban top show up red in the userlist
    disableAdmins = boolean(default=False)
    # Exclude file or directories by patterns. *.iso, moo*, Icon
    excludePatterns = list(default=list("Icon"))
    # Level of client isolation: off/moderate/paranoid
    securityModel = string(default="moderate")
    # loglevels: debug, info, warning, error, none
    logLevel = string(default=debug)"""
    spec = default.split("\n")
    config = ConfigObj(confFile, list_values=True, stringify=True, configspec=spec)
    validator = Validator()
    config.validate(validator, copy=True)
    config.filename = confFile
    fileRoot = checkRootPath(config['fileRoot'])
    if fileRoot:
        config['fileRoot'] = fileRoot
    config.write()
    if not os.path.exists(config['cert']):
        from socket import gethostname
        import wiredcertificate
        try:
            cert = wiredcertificate.reWiredCertificate(str(gethostname()))
            cert.createSignedCert()
            cert.safeAsPem(str(config['cert']))
        except:
            print "Failed to create server cert: " + str(config['cert'])
    config['serverStarted'] = time()
    if type(config['serverDesc']) is list:
        config['serverDesc'] = ', '.join(config['serverDesc'])
    git = gitVersion()
    if git:
        config['appVersion'] = git
    else:
        config['appVersion'] = "20130427A2"
    config['appName'] = "re:wired Server"
    config['banner'] = readBanner(config['serverBanner'])
    return config


def checkRootPath(path):
    return os.path.normpath(path)
    if path[-1] == os.sep:
        path = path[0:-1]
    path = re.sub(r'(?<!\\)\\', '', path)
    #if not os.path.exists(path):
        #print "Warning Invalid root Path: "+path
        #return 0
    return path


def gitVersion():
    # parse git branch and commitid to server version string
    hasgit = 0
    # test for git command
    for dir in os.environ['PATH'].split(os.pathsep):
        if os.path.exists(os.path.join(dir, 'git')):
            try:
                call([os.path.join(dir, 'git')], stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))
            except OSError, e:
                break
            hasgit = 1
    if hasgit:
        if os.path.exists(os.path.join(os.getcwd(), "includes/git-version.sh")):
            # both git and our version script exist
            call([os.path.join(os.getcwd(), "includes/git-version.sh")],
                 stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))
    # check for version token and load it
    if os.path.exists(os.path.join(os.getcwd(), "includes/.gitversion")):
        version = 0
        try:
            with open(os.path.join(os.getcwd(), "includes/.gitversion"), 'r') as f:
                version = f.readline()
        except (IOError, OSError):
            return 0
        return version.strip()
    return 0


def getBanDuration(text):
    try:
        split = text.split(" ", 1)
        if len(split) != 2:
            try:
                value = int(text)
            except:
                return 0
            if value < 1:
                return 0
            return value
        value = int(split[0])
        if value < 1:
            return 0
    except:
        return 0
    return value


def initPID(config):
    pid = str(os.getpid())
    try:
        f = open(config['serverPidFile'], 'w')
        f.write(pid)
        f.close()
    except:
        print "Failed to write pid file to " + config['serverPidFile']
        pass
    return pid


def removePID(config):
    try:
        os.unlink(config['serverPidFile'])
    except:
        print "failed to remove pid file"
    return 1


def getPID(config):
    try:
        f = open(config['serverPidFile'], 'r')
        pid = f.read()
        f.close()
    except:
        pid = 0
        pass
    return pid


def daemonize():
    if os.fork():
        exit(0)
    os.umask(0)
    os.setsid()
    if os.fork():
        exit(0)
    sys.stdout.flush()
    sys.stderr.flush()
    si = file('/dev/null', 'r')
    so = file('/dev/null', 'a+')
    se = file('/dev/null', 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())
    return 1


def checkArgv(argv):
    try:
        value = argv[1]
    except:
        return 0
    return value.upper()


def normWiredPath(path):
    path = path.replace('\\', '/')
    path = path.replace('//', '/')
    return path
