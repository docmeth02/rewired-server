import time
import socket
import wiredfunctions


class wiredUserDB():
    def __init__(self, db, logger):
        self.logger = logger
        self.db = db
        self.users = []
        self.groups = []

    def loadUserDB(self):
        users = self.db.loadUsers()
        self.users = users
        groups = self.db.loadGroups()
        self.groups = groups
        return 1

    def addUserDB(self, data):
        if not self.db.saveUser(data):
            return 0
        self.users = []
        self.loadUserDB()
        return 1

    def checkLogin(self, user, password):
        for auser in self.users:
            if auser[0] == user:
                self.logger.debug("Found user %s", user)
                if auser[1] == str(password):
                    self.logger.info("Auth successful for user %s", user)
                    return auser
                else:
                    self.logger.error("Invalid password supplied for user %s", user)
        return 0

    def getGroup(self, groupname):
        for agroup in self.groups:
            if agroup[0] == groupname:
                return agroup
        self.logger.error("Invalid group %s requested", groupname)
        return 0


class wiredUser():
    def __init__(self, parent):
        self.parent = parent
        self.logger = parent.logger
        self.activeChats = {}
        self.memberOfGroup = 0
        self.chat = None
        self.user = None
        self.idle = 0
        self.admin = 0
        self.icon = 0
        self.nick = None
        self.login = "guest"
        self.ip = None
        self.host = ""
        self.status = ""
        self.image = None
        self.client = "Unknown"
        cipher = self.parent.socket.cipher()
        self.cipherName = cipher[0]
        self.cipherBits = cipher[2]
        self.loginTime = time.time()
        self.lastActive = time.time()
        self.knownIdle = 0
        self.privs = wiredPrivs(self)
        self.loginDone = 0

    def checkPrivs(self, privname):
        try:
            priv = getattr(self.privs, str(privname))
        except:
            self.logger.error("Unmatchable privilege %s request", privname)
            return 0
        return int(priv)

    def mapPrivs(self, privstring):
        self.privs.stringToPrivs(privstring)
        return 1

    def checkIdleNotify(self):
        if self.knownIdle:  # already signaled IDLE to all clients
            return 0
        if (int(time.time()) - int(self.parent.config['userIdleTime'])) >= int(self.lastActive):
            self.logger.debug("User %s entered idle state", self.user)
            self.idle = 1
            return 1
        return 0

    def checkWakeNotify(self):
        if (int(time.time()) - int(self.parent.config['userIdleTime'])) <= int(self.lastActive) and self.knownIdle:
            self.idle = 0
            return 1
        return 0

    def buildUserList(self):
        userlist = str(self.id) + chr(28)
        userlist += str(self.idle) + chr(28)
        userlist += str(self.admin) + chr(28)
        userlist += str(self.icon) + chr(28)
        userlist += str(self.nick) + chr(28)
        userlist += str(self.user) + chr(28)
        userlist += str(self.ip) + chr(28)
        userlist += str(self.host) + chr(28)
        userlist += str(self.status) + chr(28)
        userlist += str(self.image)
        return userlist

    def userInfo(self):
        userinfo = str(self.id) + chr(28)
        userinfo += str(self.idle) + chr(28)
        userinfo += str(self.admin) + chr(28)
        userinfo += str(self.icon) + chr(28)
        userinfo += str(self.nick) + chr(28)
        userinfo += str(self.user) + chr(28)
        userinfo += str(self.ip) + chr(28)
        userinfo += str(self.host) + chr(28)
        userinfo += str(self.client) + chr(28)
        userinfo += str(self.cipherName) + chr(28)
        userinfo += str(self.cipherBits) + chr(28)
        userinfo += str(wiredfunctions.wiredTime(self.loginTime)) + chr(28)
        userinfo += str(wiredfunctions.wiredTime(self.lastActive)) + chr(28)
        ## add running transfer check here
        transfers = self.parent.getAllTransfers()
        ul = ""
        dl = ""
        for id, transfer in transfers.items():
            if int(self.id) == int(transfer.userid):
                if not transfer.active:
                    break  # this is only a queued transfer
                if transfer.type == "DOWN":
                    if dl:
                        dl += chr(29)
                    dl += str(transfer.file) + chr(30) + str(transfer.tx) + chr(30) + str(transfer.size) +\
                    chr(30) + str(transfer.txRate)
                if transfer.type == "UP":
                    if ul:
                        ul += chr(29)
                    ul += str(transfer.file) + chr(30) + str(transfer.rx) + chr(30) +\
                    str(transfer.size) + chr(30) + str(transfer.rxRate)

        if dl:
            userinfo += dl + chr(28)
        else:
            userinfo += chr(28)
        if ul:
            userinfo += ul + chr(28)
        else:
            userinfo += chr(28)
        userinfo += str(self.status) + chr(28) + str(self.image)
        return userinfo

    def buildStatusChanged(self):
        newstatus = str(self.parent.id) + chr(28)
        newstatus += str(self.idle) + chr(28)
        newstatus += str(self.admin) + chr(28)
        newstatus += str(self.icon) + chr(28)
        newstatus += str(self.nick) + chr(28)
        newstatus += str(self.status)
        return newstatus


class wiredPrivs():
    def __init__(self, parent):
        self.parent = parent
        self.getUserInfo = 0
        self.broadcast = 0
        self.postNews = 0
        self.clearNews = 0
        self.download = 0
        self.upload = 0
        self.uploadAnywhere = 0
        self.createFolders = 0
        self.alterFiles = 0
        self.deleteFiles = 0
        self.viewDropboxes = 0
        self.createAccounts = 0
        self.editAccounts = 0
        self.deleteAccounts = 0
        self.elevatePrivileges = 0
        self.kickUsers = 0
        self.banUsers = 0
        self.cannotBeKicked = 0
        self.downloadSpeed = 0
        self.uploadSpeed = 0
        self.downloadLimit = 0
        self.uploadLimit = 0
        self.changeTopic = 0

    def buildUserList(self):
        privmask = str(self.getUserInfo) + chr(28)
        privmask += str(self.broadcast) + chr(28)
        privmask += str(self.postNews) + chr(28)
        privmask += str(self.clearNews) + chr(28)
        privmask += str(self.download) + chr(28)
        privmask += str(self.upload) + chr(28)
        privmask += str(self.uploadAnywhere) + chr(28)
        privmask += str(self.createFolders) + chr(28)
        privmask += str(self.alterFiles) + chr(28)
        privmask += str(self.deleteFiles) + chr(28)
        privmask += str(self.viewDropboxes) + chr(28)
        privmask += str(self.createAccounts) + chr(28)
        privmask += str(self.editAccounts) + chr(28)
        privmask += str(self.deleteAccounts) + chr(28)
        privmask += str(self.elevatePrivileges) + chr(28)
        privmask += str(self.kickUsers) + chr(28)
        privmask += str(self.banUsers) + chr(28)
        privmask += str(self.cannotBeKicked) + chr(28)
        privmask += str(self.downloadSpeed) + chr(28)
        privmask += str(self.uploadSpeed) + chr(28)
        privmask += str(self.downloadLimit) + chr(28)
        privmask += str(self.uploadLimit) + chr(28)
        privmask += str(self.changeTopic)
        return privmask

    def stringToPrivs(self, privstring):
        privlist = str(privstring).split(chr(28))
        self.listToPrivs(privlist)
        return 1

    def listToPrivs(self, parameters):
        self.getUserInfo = int(parameters[0])
        self.broadcast = int(parameters[1])
        self.postNews = int(parameters[2])
        self.clearNews = int(parameters[3])
        self.download = int(parameters[4])
        self.upload = int(parameters[5])
        self.uploadAnywhere = int(parameters[6])
        self.createFolders = int(parameters[7])
        self.alterFiles = int(parameters[8])
        self.deleteFiles = int(parameters[9])
        self.viewDropboxes = int(parameters[10])
        self.createAccounts = int(parameters[11])
        self.editAccounts = int(parameters[12])
        self.deleteAccounts = int(parameters[13])
        self.elevatePrivileges = int(parameters[14])
        self.kickUsers = int(parameters[15])
        self.banUsers = int(parameters[16])
        self.cannotBeKicked = int(parameters[17])
        self.downloadSpeed = int(parameters[18])
        self.uploadSpeed = int(parameters[19])
        self.downloadLimit = int(parameters[20])
        self.uploadLimit = int(parameters[21])
        self.changeTopic = int(parameters[22])

        if self.banUsers or self.kickUsers:
            self.parent.admin = 1
        return 1
