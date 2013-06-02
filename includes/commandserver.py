import threading
import time
import sys
import socket
import wireduser
import ipaddr
import wiredfunctions
from commandhandler import commandHandler
from ssl import SSLError, wrap_socket, PROTOCOL_TLSv1
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
        self.name = "CommandServer-"
        self.parent = parent
        self.lock = threading.Lock()
        self.config = self.parent.config
        self.connection = parentsocket
        self.socket = wrap_socket(self.connection, server_side=True, certfile=str(self.config['cert']), keyfile=str(
            self.config['cert']), ssl_version=PROTOCOL_TLSv1)
        self.logger = self.parent.logger
        self.shutdown = 0
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
        self.serverSize = self.parent.indexer.size
        self.serverFiles = self.parent.indexer.files
        self.lastPing = time.time()

    def run(self):
            self.logger.info("Incoming connection form %s", self.user.ip)
            self.socket.settimeout(1)

            while not self.shutdown:
                data = ""
                char = 0
                while char != chr(4) and not self.shutdown:
                    char = 0
                    try:
                        char = self.socket.recv(1)
                    except SSLError as e:
                        if str(e) == 'The read operation timed out':
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
                    elif char == "":
                        self.shutdown = 1
                        break
                    else:
                        continue
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
        self.lock.acquire()
        try:
            self.socket.send(data)
        except:
            self.lock.release()
            return 0
        self.lock.release()
        return 1

    ## Connection handling ##
    def getGlobalUserID(self):
        self.parent.lock.acquire()
        self.parent.globalUserID += 1
        self.id = self.parent.globalUserID
        self.name += str(self.id)
        self.parent.lock.release()
        return self.id

    def loginDone(self):
        self.parent.lock.acquire()
        self.parent.clients[int(self.id)] = self
        self.parent.lock.release()
        self.handler.joinChat(1)
        return 1

    def logOut(self):
        if not self.id:
            return
        self.lock.acquire()
        self.handler.leaveChat(1)
        self.parent.lock.acquire()
        try:
            self.parent.clients.pop(self.id)
        except:
            pass
        self.parent.lock.release()
        self.id = None
        self.lock.release()
        return 1

    def getUserList(self):
        self.parent.lock.acquire()
        allclients = self.parent.clients
        self.parent.lock.release()
        return allclients

    ### Users & Groups ###
    def checkLogin(self, username, password, ip):
        banned = self.parent.db.checkBan(username, ip)
        if banned:
            self.handler.reject(511)
            self.shutdown = 1
            self.socket.shutdown(socket.SHUT_RDWR)
            return 0
        login = self.parent.users.checkLogin(username, password)
        return login

    def banUser(self, user, nick, ip, end):
        result = self.parent.db.addBan(user, nick, ip, end)
        if result:
            return 1
        return 0

    def getGroup(self, groupname):
        self.parent.lock.acquire()
        group = self.parent.users.getGroup(groupname)
        self.parent.lock.release()
        return group

    def addUser(self, data):
        # this is used for adding both users and groups since there is no real difference
        self.parent.lock.acquire()
        result = self.parent.users.addUserDB(data)
        self.parent.lock.release()
        if result:
            return 1
        return 0

    def getUsers(self):
        self.parent.lock.acquire()
        allusers = self.parent.users.users
        self.parent.lock.release()
        return allusers

    def getGroups(self):
        self.parent.lock.acquire()
        allgroups = self.parent.users.groups
        self.parent.lock.release()
        return allgroups

    def delUser(self, username):
        result = self.parent.db.deleteElement(username, 1)
        if not result:
            return 0
        self.parent.users.loadUserDB()
        return 1

    def delGroup(self, username):
        result = self.parent.db.deleteElement(username, 0)
        if not result:
            return 0
        self.parent.users.loadUserDB()
        return 1

    def editUser(self, data):
        result = self.parent.db.updateElement(data, 1)
        if not result:
            return 0
        self.parent.users.loadUserDB()
        return 1

    def editGroup(self, data):
        result = self.parent.db.updateElement(data, 0)
        if not result:
            return 0
        self.parent.users.loadUserDB()
        return 1

    def updateUserPrivs(self, username, privs):
        for aid, aclient in self.parent.clients.items():
            if aclient.user.user == username:
                self.logger.debug("Priv change for online user %s", username)
                with aclient.lock:
                    aclient.user.mapPrivs(privs)
                aclient.handler.PRIVILEGES([])
                # notify online clients that account may have changed
                aclient.handler.notifyAll("304 " + aclient.user.buildStatusChanged() + chr(4))
                aclient.user.updateTransfers()
        return 1

    def updateGroupPrivs(self, groupname, privs):
        for aid, aclient in self.parent.clients.items():
            if str(aclient.user.memberOfGroup) == str(groupname):
                self.logger.debug("Priv change for online group member %s of %s", aclient.user.user, groupname)
                with aclient.lock:
                    aclient.user.mapPrivs(privs)
                aclient.handler.PRIVILEGES([])
                # same as above
                aclient.handler.notifyAll("304 " + aclient.user.buildStatusChanged() + chr(4))
                aclient.user.updateTransfers()
        return 1

    ##  ??
    def updateServerInfo(self):
        info = self.handler.serverInfo()
        self.sendData(info)
        return 1

    ### Chat ###
    def getGlobalPrivateChatID(self):
        self.parent.lock.acquire()
        self.parent.globalPrivateChatID += 1
        privateChatID = self.parent.globalPrivateChatID
        self.parent.lock.release()
        return privateChatID

    def getTopic(self, chat):
        self.parent.lock.acquire()
        try:
            chattopic = self.parent.topics[int(chat)]
        except:
            chattopic = []
        self.parent.lock.release()
        return chattopic

    def setTopic(self, newtopic, chat):
        self.parent.lock.acquire()
        self.parent.topics[int(chat)] = newtopic
        self.parent.lock.release()
        return 1

    def releaseTopic(self, chat):
        # check for orphaned private chat topics and release them from memory
        if int(chat) == 1:  # never release public chat topic
            return 0

        inthischat = 0
        allclients = self.parent.clients
        for aid, aclient in allclients.items():
            check = 0
            try:
                check = aclient.user.activeChats[int(chat)]
            except KeyError:
                pass
            if check:
                inthischat = 1
        if not inthischat:
            self.logger.debug("Released topic for chat %s", chat)
            self.parent.lock.acquire()
            self.parent.topics.pop(int(chat), 0)
            self.parent.lock.release()
        return 1

    ## Files
    def queueTransfer(self, transfer):
        # add queue check here
        self.parent.lock.acquire()
        self.parent.transferqueue[transfer.id] = transfer
        self.parent.lock.release()
        self.logger.debug("Queued transfer %s for user %s", transfer.id, self.user.user)
        return 1

    def getAllTransfers(self):
        return self.parent.transferqueue

    def doSearch(self, searchString):
        self.parent.indexer.lock.acquire()
        result = self.parent.indexer.searchIndex(searchString)
        self.parent.indexer.lock.release()
        return result

    ### News ###
    def postNews(self, newstext):
        self.parent.news.lock.acquire()
        self.parent.news.saveNews(self.user.nick, time.time(), newstext)
        self.parent.news.lock.release()
        return 1

    def getNews(self):
        return reversed(self.parent.news.news)

    def clearNews(self):
        self.parent.news.lock.acquire()
        self.parent.news.clearNews()
        self.parent.news.lock.release()
        return 1
