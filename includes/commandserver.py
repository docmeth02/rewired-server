import threading
import time
import sys
import socket
import ssl
import wireduser
import ipaddr
from commandhandler import commandHandler
try:
    from dns import resolver, reversename
    from dns.resolver import NXDOMAIN
except:
    print "Failed to load dns lib. Please install python-dnspython."
    raise SystemExit
from traceback import format_exception


class commandServer(threading.Thread):
    def __init__(self, parent, (parentsocket, address)):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.parent = parent
        self.wiredlog = self.parent.wiredlog
        self.socket = parentsocket
        self.logger = self.parent.logger
        self.indexer = self.parent.indexer
        self.shutdown = 0
        self.config = self.parent.config
        self.protoVersion = "1.1"
        self.user = wireduser.wiredUser(self)
        if address[0][:7] == "::ffff:":
            self.user.ip = address[0][7:]
        else:
            self.user.ip = address[0]

        try:
            addr = reversename.from_address(self.user.ip)
            rdns = resolver.Resolver()
            rdns.lifetime = 1.0
            rdns.timeout = 1.0
            self.user.host = str(rdns.query(addr, "PTR")[0])
        except:
            self.user.host = ""
        self.id = 0
        self.handler = commandHandler(self)
        self.serverSize = self.indexer.size
        self.serverFiles = self.indexer.files
        self.lastPing = time.time()

    def run(self):
            self.logger.info("Incoming connection form %s", self.user.ip)
            self.socket.settimeout(.1)

            while not self.shutdown:
                data = ""
                char = 0
                while char != chr(4) and not self.shutdown:
                    char = 0
                    try:
                        char = self.socket.recv(1)
                    except ssl.SSLError as e:
                        if e.message == 'The read operation timed out':
                            pass
                        else:
                            self.logger.debug("Caught SSLError: %s" % e)
                            self.shutdown = 1
                            break
                    except socket.error:
                        self.logger.debug("Caught socket.error")
                        self.shutdown = 1
                        break

                    if char:
                        data += char
                    elif char == '':  # a disconnected socket returns an empty string on read
                        self.shutdown = 1
                        break
                    else:
                        time.sleep(0.1)
                if not self.shutdown:
                    response = self.handler.gotdata(data)
            self.exit()

    def exit(self):
        self.logger.info("Client %s disconnected", self.user.ip)
        self.logOut()
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except:
            pass
        self.logger.info("CMDhandler process exited")
        raise SystemExit

    def sendData(self, data):
        try:
            self.socket.send(data)
        except:
            return 0
        return 1

    ## Connection handling ##
    def getGlobalUserID(self):
        self.lock.acquire()
        self.parent.globalUserID += 1
        self.id = self.parent.globalUserID
        self.lock.release()
        return self.id

    def loginDone(self):
        self.lock.acquire()
        self.parent.clients[int(self.id)] = self
        self.lock.release()
        self.handler.joinChat(1)
        return 1

    def logOut(self):
        self.handler.leaveChat(1)
        self.lock.acquire()
        self.parent.clients.pop(self.id)
        self.parent.wiredlog.log_event('LOGOUT', {'USER': self.user.user, 'NICK': self.user.nick})
        self.lock.release()
        return 1

    def getUserList(self):
        self.lock.acquire()
        allclients = self.parent.clients
        self.lock.release()
        return allclients

    ### Users & Groups ###
    def checkLogin(self, username, password, ip):
        if self.parent.users.db.checkBan(username, ip):
            self.handler.reject(511)
            self.shutdown = 1
            self.socket.shutdown(socket.SHUT_RDWR)
            return 0

        return self.parent.users.checkLogin(username, password)

    def banUser(self, user, nick, ip, end):
        self.lock.acquire()
        result = self.parent.users.db.addBan(user, nick, ip, end)
        self.lock.release()
        if result:
            return 1
        return 0

    def getGroup(self, groupname):
        return self.parent.users.getGroup(groupname)

    def addUser(self, data):
        # this is used for adding both users and groups since there is no real difference
        self.lock.acquire()
        result = self.parent.users.addUserDB(data)
        self.lock.release()
        if result:
            return 1
        return 0

    def getUsers(self):
        self.lock.acquire()
        allusers = self.parent.users.users
        self.lock.release()
        return allusers

    def getGroups(self):
        self.lock.acquire()
        allgroups = self.parent.users.groups
        self.lock.release()
        return allgroups

    def delUser(self, username):
        if not self.parent.db.deleteElement(username, 1):
            return 0
        self.parent.users.loadUserDB()
        return 1

    def delGroup(self, username):
        if not self.parent.db.deleteElement(username, 0):
            return 0
        self.parent.users.loadUserDB()
        return 1

    def editUser(self, data):
        self.lock.acquire()
        if not self.parent.db.updateElement(data, 1):
            return 0
        self.parent.users.loadUserDB()
        self.lock.release()
        return 1

    def editGroup(self, data):
        self.lock.acquire()
        if not self.parent.db.updateElement(data, 0):
            return 0
        self.parent.users.loadUserDB()
        self.lock.release()
        return 1

    def updateUserPrivs(self, username, privs):
        for aid, aclient in self.parent.clients.iteritems():
            if aclient.user.user == username:
                self.logger.debug("Priv change for online user %s", username)
                self.lock.acquire()
                aclient.user.mapPrivs(privs)
                aclient.handler.PRIVILEGES([])
                self.lock.release()
                # notify online clients that account may have changed
                aclient.handler.notifyAll("304 " + aclient.user.buildStatusChanged() + chr(4))
        return 1

    def updateGroupPrivs(self, groupname, privs):
        for aid, aclient in self.parent.clients.iteritems():
            if str(aclient.user.memberOfGroup) == str(groupname):
                self.logger.debug("Priv change for online group member %s of %s", aclient.user.user, groupname)
                self.lock.acquire()
                aclient.user.mapPrivs(privs)
                aclient.handler.PRIVILEGES([])
                self.lock.release()
                # same as above
                aclient.handler.notifyAll("304 " + aclient.user.buildStatusChanged() + chr(4))
        return 1

    def updateServerInfo(self):
        info = self.handler.serverInfo()
        self.sendData(info)
        return 1

    ### Chat ###
    def getGlobalPrivateChatID(self):
        self.lock.acquire()
        self.parent.globalPrivateChatID += 1
        privateChatID = self.parent.globalPrivateChatID
        self.lock.release()
        return privateChatID

    def getTopic(self, chat):
        self.lock.acquire()
        try:
            chattopic = self.parent.topics[int(chat)]
        except:
            chattopic = []
        self.lock.release()
        return chattopic

    def setTopic(self, newtopic, chat):
        self.lock.acquire()
        self.parent.topics[int(chat)] = newtopic
        self.lock.release()
        return 1

    def releaseTopic(self, chat):
        # check for orphaned private chat topics and release them from memory
        if int(chat) == 1:  # never release public chat topic
            return 0

        inthischat = 0
        self.lock.acquire()
        allclients = self.parent.clients
        for aid, aclient in allclients.iteritems():
            check = 0
            try:
                check = aclient.user.activeChats[int(chat)]
            except KeyError:
                pass
            if check:
                inthischat = 1
        if not inthischat:
            self.logger.debug("Released topic for chat %s", chat)
            self.parent.topics.pop(int(chat), 0)
        self.lock.release()
        return 1

    ## Files
    def queueTransfer(self, transfer):
        # add queue check here
        self.lock.acquire()
        self.parent.transferqueue[transfer.id] = transfer
        self.logger.debug("Queued transfer %s for user %s", transfer.id, self.user.user)
        self.lock.release()
        return 1

    def getAllTransfers(self):
        return self.parent.transferqueue

    def doSearch(self, searchString):
        self.lock.acquire()
        try:
            result = self.indexer.searchIndex(searchString)
        except:
            self.logger.error("Failed to process search for term %s", searchString)
        self.lock.release()
        return result

    ### News ###
    def postNews(self, newstext):
        self.lock.acquire()
        self.parent.news.saveNews(self.user.nick, time.time(), newstext)
        self.lock.release()
        return 1

    def getNews(self):
        return reversed(self.parent.news.news)

    def clearNews(self):
        self.lock.acquire()
        self.parent.news.clearNews()
        self.lock.release()
        return 1
