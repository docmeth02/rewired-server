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
        with self.lock:
            try:
                self.socket.send(data)
            except:
                return 0
        return 1

    ## Connection handling ##
    def getGlobalUserID(self):
        with self.parent.lock:
            self.parent.globalUserID += 1
            self.id = self.parent.globalUserID
            self.name += str(self.id)
        return self.id

    def loginDone(self):
        with self.parent.lock:
            self.parent.clients[int(self.id)] = self
        self.handler.joinChat(1)
        return 1

    def logOut(self):
        if not self.id:
            return
        with self.lock:
            self.handler.leaveChat(1)
            with self.parent.lock:
                try:
                    self.parent.clients.pop(self.id)
                except:
                    pass
            self.id = None
        return 1

    def getUserList(self):
        with self.parent.lock:
            allclients = self.parent.clients
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
        with self.parent.lock:
            group = self.parent.users.getGroup(groupname)
        return group

    def addUser(self, data):
        # this is used for adding both users and groups since there is no real difference
        with self.parent.lock:
            result = self.parent.users.addUserDB(data)
        if result:
            return 1
        return 0

    def getUsers(self):
        with self.parent.lock:
            allusers = self.parent.users.users
        return allusers

    def getGroups(self):
        with self.parent.lock:
            allgroups = self.parent.users.groups
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

    def updateServerInfo(self):
        info = self.handler.serverInfo()
        self.sendData(info)
        return 1

    ### Chat ###
    def getGlobalPrivateChatID(self):
        with self.parent.lock:
            self.parent.globalPrivateChatID += 1
            privateChatID = self.parent.globalPrivateChatID
        return privateChatID

    def getTopic(self, chat):
        with self.parent.lock:
            try:
                chattopic = self.parent.topics[int(chat)]
            except:
                chattopic = []
        return chattopic

    def setTopic(self, newtopic, chat):
        with self.parent.lock:
            self.parent.topics[int(chat)] = newtopic
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
            with self.parent.lock:
                self.parent.topics.pop(int(chat), 0)
        return 1

    ## Files
    def queueTransfer(self, transfer):
        # add queue check here
        with self.parent.lock:
            self.parent.transferqueue[transfer.id] = transfer
        self.logger.debug("Queued transfer %s for user %s", transfer.id, self.user.user)
        return 1

    def getAllTransfers(self):
        return self.parent.transferqueue

    def doSearch(self, searchString):
        with self.parent.indexer.lock:
            result = self.parent.indexer.searchIndex(searchString)
        return result

    ### News ###
    def postNews(self, newstext):
        with self.parent.news.lock:
            self.parent.news.saveNews(self.user.nick, time.time(), newstext)
        return 1

    def getNews(self):
        return reversed(self.parent.news.news)

    def clearNews(self):
        with self.parent.news.lock:
            self.parent.news.clearNews()
        return 1
