import wiredfunctions
import wirednews
import wireduser
import wiredtransfer
import wireddb
import wiredindex
import wiredtracker
import signal
import socket
import select
import threading
import logging
from transferserver import transferServer
from commandserver import commandServer
from time import sleep, time
from sys import path
from os import sep
from ssl import SSLError


class reWiredServer():
    def __init__(self, daemonize, configfile, bundled):
        self.lock = threading.Lock()
        self.configfile = configfile
        self.daemonize = bool(daemonize)
        self.bundled = bool(bundled)
        if self.daemonize and not self.bundled:
            wiredfunctions.daemonize()
        self.keeprunning = 1
        self.cleantimer = 0
        self.globalUserID = 0
        self.globalPrivateChatID = 1
        self.clients = {}
        self.topics = {}
        self.tracker = []
        self.transferqueue = {}
        self.binpath = path[0] + sep
        self.threadDebugtimer = 0
        if not self.configfile:
            self.configfile = self.binpath + "server.conf"

    def initialize(self):
        self.config = wiredfunctions.loadConfig(self.configfile)
        if self.bundled:  # path to the git version file is differen when running in bundled mode
            git = wiredfunctions.gitVersion("rewiredserver/includes")
            if git:
                self.config['appVersion'] = git
        self.logger = wiredfunctions.initLogger(self.config["logFile"], self.config["logLevel"])
        self.pid = wiredfunctions.initPID(self.config)
        self.logger.info("Server pid: %s", self.pid)
        self.db = wireddb.wiredDB(self.config, self.logger)
        self.news = wirednews.wiredNews(self.db)
        self.news.loadNews()
        self.users = wireduser.wiredUserDB(self.db, self.logger)
        self.users.loadUserDB()
        self.indexer = wiredindex.wiredIndex(self)
        self.indexer.start()
        if self.config['trackerUrl'] and self.config['trackerRegister']:
            self.initTrackers()
            self.logger.debug("%s tracker threads started", len(self.tracker))

        # create listening sockets
        try:
            self.commandSock = self.open_command_socket()
            self.transferSock = self.open_transfer_socket()
        except:
            pass
        self.houseKeeping()
        self.threadDebug()
        return 1

    def main(self):
        # handle signals
        if not self.bundled:
            signal.signal(signal.SIGINT, self.serverShutdown)
            signal.signal(signal.SIGTERM, self.serverShutdown)
            signal.signal(signal.SIGFPE, self.restartTracker)
        while self.keeprunning:
            try:
                inputready, outputready, exceptready = select.select([self.commandSock, self.transferSock], [], [], 1)
                for asocket in inputready:
                    if asocket == self.commandSock:
                        commandServer(self, self.commandSock.accept()).start()
                    if asocket == self.transferSock:
                        transferServer(self, self.transferSock.accept()).start()
            except select.error as e:
                self.logger.error("SELECT ERROR: %s", e)
                continue
            except ssl.SSLError as e:
                self.logger.error("SSL ERROR: %s", e)
                continue
            except Exception as e:
                self.logger.error("Socket Error: %s", e)
                continue
            except SSLError as exception:
                self.logger.error(exception)
                continue
        self.logger.info("Main thread shutdown initiated")
        while threading.active_count() > 1 and not self.bundled:
            self.logger.info(str(threading.active_count()) + " threads still alive... " + str(threading.enumerate()))
            sleep(1)
        if self.bundled:
            self.logger.info(str(threading.active_count()) + " threads still alive... " + str(threading.enumerate()))
        try:
            for ahandler in self.logger.handlers:
                self.logger.removeHandler(ahandler)
                ahandler.close()
        except AttributeError:
            pass
        logging.shutdown()


    def serverShutdown(self, signum=None, frame=None):
        self.logger.info("Got signal: %s.Starting server shutdown", signum)
        # shutdown the server
        self.keeprunning = 0
        if self.cleantimer:
            self.cleantimer.cancel()
            self.cleantimer.join()
        if self.threadDebugtimer:
            self.threadDebugtimer.cancel()
            self.threadDebugtimer.join()
        for key, aclient in self.clients.items():
            aclient.lock.acquire()
            try:
                aclient.shutdown = 1
                aclient.socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            aclient .lock.release()
        for key, atransfer in self.transferqueue.items():
            atransfer.parent.lock.acquire()
            atransfer.shutdown = 1
            atransfer.parent.socket.shutdown(socket.SHUT_RDWR)
            atransfer.parent.lock.release()
        if self.indexer:
            self.indexer.shutdown = 1
        if self.tracker:
            for atracker in self.tracker:
                atracker.keepalive = 0
        if hasattr(self, 'commandSock'):
            self.commandSock.close()
        if hasattr(self, 'transferSock'):
            self.transferSock.close()
        wiredfunctions.removePID(self.config)
        try:
            for ahandler in self.logger.handlers:
                self.logger.removeHandler(ahandler)
                try:
                    ahandler.close()
                except:
                    pass
        except AttributeError:
            pass
        return 1

    def houseKeeping(self):
        if not self.keeprunning:
            return 0  # server is about to shutdown. don't interfere
        self.cleantimer = threading.Timer(60.0, self.houseKeeping)  # call ourself again in 60 seconds
        self.cleantimer.start()
        self.checkTracker()
        self.checkIndexer()
        if self.indexer.sizeChanged:    # the indexer messaged that the server info changed
            self.logger.debug("Server size changed: Sending new server info to all cients")
            for aid, aclient in self.clients.items():  # now update all clients
                aclient.lock.acquire()
                aclient.serverSize = self.indexer.size
                aclient.serverFiles = self.indexer.files
                aclient.lock.release()
                aclient.updateServerInfo()
            self.indexer.lock.acquire()
            self.indexer.sizeChanged = 0
            self.indexer.lock.release()

        # check for zombies and idle users
        for aid, aclient in self.clients.items():
            if aclient.user.checkIdleNotify():
                aclient.handler.notifyAll("304 " + str(aclient.user.buildStatusChanged()) + chr(4))
                self.lock.acquire()
                aclient.user.knownIdle = 1
                self.lock.release()

            if not aclient.is_alive() or aclient.lastPing <= (time() - self.config['pingTimeout']):
                self.logger.error("Found dead thread for userid %s Lastping %s seconds ago",\
                                  aid, (time() - aclient.lastPing))
                try:
                    aclient.logOut()
                    self.lock.acquire()
                    aclient.shutdown = 1
                    aclient.socket.shutdown(socket.SHUT_RDWR)
                    self.clients.pop(aclient.id, 0)
                    self.lock.release()
                except socket.error:
                    self.clients.pop(aclient.id, 0)
                    self.lock.release()
                    self.logger.error("Client %s: socket was already dead", aid)
        return 1

    def threadDebug(self):
        if not self.keeprunning:
            return 0
        self.logger.info(str(threading.active_count()) + " active threads:" + str(threading.enumerate()))
        self.threadDebugtimer = threading.Timer(1800.0, self.threadDebug)
        self.threadDebugtimer.start()
        return 1

    def open_command_socket(self):
        try:
            if socket.has_ipv6 and not wiredfunctions.checkPlatform("Windows"):
                self.logger.debug("Command socket is ipv6 capable")
                sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("::", self.config['port']))
            else:
                self.logger.debug("Command socket is only capable of ipv4")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.config['host'], self.config['port']))
            sock.listen(4)
            return sock
        except:
                self.logger.error("Can't bind to Port %s. Make sure it's not in use", self.config['port'])
                self.serverShutdown()
                system.exit()

    def open_transfer_socket(self):
        try:
            if socket.has_ipv6 and not wiredfunctions.checkPlatform("Windows"):
                self.logger.debug("Transfer socket is ipv6 capable")
                sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("::", (int(self.config['port']) + 1)))
            else:
                self.logger.debug("Transfer socket is only capable of ipv4")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.config['host'], (int(self.config['port']) + 1)))
            sock.listen(4)
            return sock
        except:
            self.logger.error("Can't bind to Port %s. Make sure it's not in use", self.config['port'] + 1)
            self.serverShutdown()
            system.exit()

    def restartTracker(self, signum, frame):
        self.logger.info("Restarting tracker threads...")
        for atracker in self.tracker:
            atracker.keepalive = 0

        for key, atracker in enumerate(self.tracker):
            self.tracker[key].join(5)
            del(self.tracker[key])

        self.tracker = []  # make sure its empty

        self.initTrackers()
        return 1

    def initTrackers(self):
        trackers = self.getTrackers()
        for aTracker in trackers:
            aTracker = wiredtracker.wiredTracker(self, aTracker)
            aTracker.start()
            self.tracker.append(aTracker)
        return 1

    def getTrackers(self):
        clean = []
        trackers = self.config['trackerUrl']
        if type(self.config['trackerUrl']) is str:
            trackers = self.config['trackerUrl'].split(',')
        for atracker in trackers:
            clean.append(atracker.strip())
        return clean

    def checkTracker(self):
        trackers = self.getTrackers()
        if trackers and self.config['trackerRegister']:
            for key, atracker in enumerate(self.tracker):
                    if not atracker.isAlive():
                        name = atracker.name
                        self.tracker[key].join()
                        self.tracker.pop(key)
                        self.logger.error("%s: thread died... restarting", name)
                        newtracker = wiredtracker.wiredTracker(self, name)
                        newtracker.start()
                        self.tracker.append(newtracker)

    def checkIndexer(self):
        if not self.indexer.isAlive():
            print "Indexer died on us!"
            self.indexer.join(5)
            del self.indexer
            self.indexer = wiredindex.wiredIndex(self)
            self.indexer.start()
            return 0
        return 1
