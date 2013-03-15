import wiredfunctions
import wireduser
import wiredfiles
import wiredtransfer
import time
import sys
import socket
import os


class commandHandler():
    def __init__(self, parent):
        self.parent = parent
        self.logger = parent.logger
        self.config = self.parent.config

    def HELLO(self, parameters):
        if parameters:
            if parameters[0] == "1.5":
                info = self.serverInfo(1.5)
                self.parent.sendData(info)
                # add version bump here
                return 1
        info = self.serverInfo()
        self.parent.sendData(info)
        return 1

    def NICK(self, parameters):
        self.parent.user.nick = str(parameters[0])
        if self.parent.user.loginDone:
            data = self.parent.user.buildStatusChanged()
            self.notifyAll("304 " + data + chr(4))
        return 1

    def ICON(self, parameters):
        self.parent.user.icon = str(parameters[0])
        self.parent.user.image = str(parameters[1])
        if self.parent.user.loginDone:
            data = "340 " + str(self.parent.id) + chr(28) + str(self.parent.user.image) + chr(4)
            self.notifyAll(data)
        return 1

    def STATUS(self, parameters):
        self.parent.user.status = str(parameters[0])
        if self.parent.user.loginDone:
            data = self.parent.user.buildStatusChanged()
            self.notifyAll("304 " + data + chr(4))
        return 1

    def CLIENT(self, parameters):
        self.parent.user.client = str(parameters[0])
        return 1

    def USER(self, parameters):
        # add user check here
        self.parent.user.user = str(parameters[0])
        return 1

    def PRIVILEGES(self, parameters):
        privs = self.parent.user.privs.buildUserList()
        response = '602 ' + privs + chr(4)
        self.parent.sendData(response)
        return 1

    def PASS(self, parameters):
        self.logger.info("Login attempt for user %s", self.parent.user.user)
        user = self.parent.checkLogin(str(self.parent.user.user), str(parameters[0]), self.parent.user.ip)
        if not user:
                # login failed
            self.logger.error("Login failed for user %s", self.parent.user.user)
            self.reject(510)
            self.parent.shutdown = 1
            return 0
        if self.parent.user.loginDone:
            # qwired will try to relogin on an already established connection:
            self.logger.info("Ignoring reconnect try on already established link for user %s", self.parent.user.user)
            return 1
        self.parent.user.id = self.parent.getGlobalUserID()  # get ourself a shiny new userid
        if user[2]:  # group member
            group = self.parent.getGroup(str(user[2]))
            self.logger.debug("User %s is a member of group %s", self.parent.user.user, group[0])
            if not group:
                self.logger.error("Invalid group %s referenced for user %s", group[0], self.parent.user.user)
                self.reject(510)
                self.parent.shutdown = 1
                return 0
            self.parent.user.memberOfGroup = group[0]
            self.parent.user.mapPrivs(group[4])
        else:
            self.parent.user.mapPrivs(user[4])
        self.logger.info("Login for user %s successful.", self.parent.user.user)
        self.parent.sendData('201 ' + str(self.parent.user.id) + chr(4))  # send login successful
        self.parent.sendData(self.getTopic(1))  # send topic for public chat (if any)
        self.parent.loginDone()  # add this client to the logged in user list
        self.parent.user.loginDone = 1  # login is now complete
        return 1

    def WHO(self, parameters):
        chatid = int(parameters[0])
        clients = self.parent.getUserList()
        userlist = {}

        for aid, aclient in clients.items():
            try:
                check = aclient.user.activeChats[int(chatid)]
            except KeyError:
                continue
            userlist[aclient.user.activeChats[int(chatid)]] = aclient

        for aid, aclient in sorted(userlist.items(), key=lambda x: x):
                ip = ""
                host = ""
                if self.parent.user.checkPrivs("getUserInfo"):
                    ip = aclient.user.ip
                    host = aclient.user.host
                response = "310 " + str(chatid) + chr(28) + str(aclient.user.id) + chr(28) + str(aclient.user.idle) +\
                chr(28) + str(aclient.user.admin) + chr(28) + str(aclient.user.icon) + chr(28) +\
                str(aclient.user.nick) + chr(28) + str(aclient.user.user) + chr(28) + str(ip) + chr(28) +\
                str(host) + chr(28) + str(aclient.user.status) + chr(28) + str(aclient.user.image) + chr(4)
                self.parent.sendData(response)

        self.parent.sendData('311 ' + str(chatid) + chr(4))  # send userlist done
        return 1

    def INFO(self, parameters):
        if not self.parent.user.checkPrivs("getUserInfo"):
            self.reject(516)
            return 0
        clients = self.parent.getUserList()
        try:
            userinfo = clients[int(parameters[0])].user.userInfo()
        except KeyError:
            self.logger.error("Invalid INFO userid %s requested", parameters[0])
            return 0
        self.parent.sendData('308 ' + str(userinfo) + chr(4))
        return 1

    def SAY(self, parameters):
        if not len(parameters[1]):
            return 0
        clients = self.parent.getUserList()
        chatid = int(parameters[0])
        chat = wiredfunctions.tsplit(parameters[1], '\n')
        for achat in chat:
            data = '300 ' + str(chatid) + chr(28) + str(self.parent.user.id) + chr(28) + str(achat) + chr(4)
            self.notifyChat(data, chatid)
        return 1

    def ME(self, parameters):
        if not len(parameters[1]):
            return 0
        chatid = parameters[0]
        data = '301 ' + str(chatid) + chr(28) + str(self.parent.user.id) + chr(28) + str(parameters[1]) + chr(4)
        self.notifyChat(data, chatid)
        return 1

    def BANNER(self, parameters):
        self.parent.sendData('203 ' + str(self.config['banner']) + chr(4))
        return 1

    def POST(self, parameters):
        if not self.parent.user.checkPrivs("postNews"):
            self.reject(516)
            return 0
        self.parent.postNews(parameters[0])
        date = wiredfunctions.wiredTime(time.time())
        data = "322 " + str(self.parent.user.nick) + chr(28) + str(date) + chr(28) + str(parameters[0]) + chr(4)
        self.logger.info("%s posted a news item", self.parent.user.nick)
        self.notifyAll(data)
        return 1

    def NEWS(self, parameters):
        news = self.parent.getNews()
        if news:
            for anews in news:
                date = wiredfunctions.wiredTime(float(anews[1]))
                self.parent.sendData("320 " + str(anews[0]) + chr(28) + str(date) + chr(28) + str(anews[2]) + chr(4))
        self.parent.sendData("321 Done" + chr(4))
        return 1

    def CLEARNEWS(self, parameters):
        if not self.parent.user.checkPrivs("clearNews"):
            self.reject(516)
            return 0
        self.parent.clearNews()
        self.logger.info("%s cleared the news", self.parent.user.user)
        self.parent.sendData("321 Done" + chr(4))
        return 1

    def MSG(self, parameters):
        clients = self.parent.getUserList()
        self.parent.parent.lock.acquire()
        for aid, aclient in clients.items():
            if int(aclient.user.id) == int(parameters[0]):
                aclient.sendData('305 ' + str(self.parent.user.id) + chr(28) + str(parameters[1]) + chr(4))
        self.parent.parent.lock.release()
        return 1

    def BROADCAST(self, parameters):
        if not self.parent.user.checkPrivs("broadcast"):
            self.reject(516)
            return 0
        data = parameters[0]
        self.notifyAll('309 ' + str(self.parent.id) + chr(28) + str(data) + chr(4))

    def TOPIC(self, parameters):
        if not self.parent.user.checkPrivs("changeTopic"):
            self.reject(516)
            return 0
        newtopic = {}
        chatid = int(parameters[0])
        self.logger.debug("Topic of chat %s set to %s by %s", parameters[0], parameters[1], self.parent.id)
        try:
            newtopic['userid'] = self.parent.id
            newtopic['nick'] = self.parent.user.nick
            newtopic['user'] = self.parent.user.login
            newtopic['ip'] = self.parent.user.ip
            newtopic['time'] = time.time()
            newtopic['topic'] = str(parameters[1])
        except KeyError:
            self.logger.error("Invalid parameters in TOPIC")
        self.parent.setTopic(newtopic, chatid)
        data = self.getTopic(chatid)
        self.notifyChat(data, chatid)
        return 1

    def getTopic(self, chat):
        chattopic = self.parent.getTopic(int(chat))
        if not chattopic:
            return 0
        try:
            topictime = wiredfunctions.wiredTime(chattopic['time'])
            nick = chattopic['nick']
            ip = chattopic['ip']
            login = chattopic['user']
            topic = chattopic['topic']
        except KeyError:
            self.logger.error("Invalid parameters in getTopic")
            return 0
        data = '341 ' + str(chat) + chr(28) + str(nick) + chr(28) + str(login) + chr(28) +\
        str(ip) + chr(28) + str(topictime) + chr(28) + str(topic) + chr(4)
        return data

    def PING(self, parameters):
        self.parent.sendData('202 PONG' + chr(4))
        self.parent.lastPing = time.time()
        return 1

    def PRIVCHAT(self, parameters):
        chatID = self.parent.getGlobalPrivateChatID()  # get a new private chat id
        self.parent.sendData("330 " + str(chatID) + chr(4))
        self.parent.user.activeChats[int(chatID)] = 1
        return 1

    def INVITE(self, parameters):
        if (int(self.parent.user.id) == int(parameters[0])):
            return 0
        clients = self.parent.getUserList()
        self.parent.parent.lock.acquire()
        for aid, aclient in clients.items():
            if aclient.id == int(parameters[0]):
                aclient.sendData('331 ' + str(parameters[1]) + chr(28) + str(int(self.parent.id)) + chr(4))
        self.parent.parent.lock.release()
        return 1

    def DECLINE(self, parameters):
        chatid = int(parameters[0])
        data = '332 ' + str(chatid) + chr(28) + str(self.parent.id) + chr(4)
        self.notifyChat(data, chatid)

    def JOIN(self, parameters):
        self.parent.user.activeChats[int(parameters[0])] = 1
        self.joinChat(int(parameters[0]))
        return 1

    def joinChat(self, chat):
        clients = self.parent.getUserList()
        userlist = self.parent.user.buildUserList()
        self.parent.user.activeChats[int(chat)] = time.time()  # time user joined this chat
        self.parent.parent.lock.acquire()
        for aid, aclient in clients.items():
            if aclient.id != self.parent.id and int(chat) in aclient.user.activeChats:
                aclient.sendData('302 ' + str(chat) + chr(28) + userlist + chr(4))
        self.parent.parent.lock.release()
        return 1

    def LEAVE(self, parameters):
        self.leaveChat(int(parameters[0]))
        return 1

    def leaveChat(self, chat):
        if not self.parent.user.loginDone:
            return 0  # don't send leave for clients with failed logins
        self.parent.user.activeChats.pop(int(chat), 0)
        data = '303 ' + str(chat) + chr(28) + str(self.parent.user.id) + chr(4)
        self.notifyChat(data, chat)
        self.parent.releaseTopic(chat)  # release chat topic
        return 1

    def KICK(self, parameters):
        if not self.parent.user.checkPrivs("kickUsers"):
            self.reject(516)
            return 0
        clients = self.parent.getUserList()
        for aid, aclient in clients.items():
            if int(aclient.id) == int(parameters[0]):
                if aclient.user.checkPrivs("cannotBeKicked"):
                    self.reject(515)
                    return 0
                self.notifyAll("306 " + str(parameters[0]) + chr(28) + str(self.parent.id) +\
                chr(28) + str(parameters[1]) + chr(4))
                self.parent.parent.lock.acquire()
                try:
                    aclient.shutdown = 1
                    aclient.socket.shutdown(socket.SHUT_RDWR)
                except:
                    self.logger.error("Failed to terminate thread for user %s", aclient.user.nick)
                self.parent.parent.lock.release()

                self.logger.info("%s was kicked by %s", aclient.user.nick, self.parent.user.user)
        return 1

    def BAN(self, parameters):
        if not self.parent.user.checkPrivs("banUsers"):
            self.reject(516)
            return 0
        try:
            target = int(parameters[0])
            msg = str(parameters[1])
            duration = wiredfunctions.getBanDuration(msg)
            if duration:
                try:
                    msg = msg.split(" ", 1)[1]
                except:
                    msg = ""
                    pass
            else:
                duration = 10  # default ban duration is 10 minutes
        except KeyError, IndexError:
            self.logger.error("Invalid field count in BAN")
            self.reject(500)
        clients = self.parent.getUserList()
        for aid, aclient in clients.items():
            if int(aclient.id) == int(target):
                if aclient.user.checkPrivs("cannotBeKicked"):
                    self.reject(515)
                    return 0
                self.parent.banUser(aclient.user.user, aclient.user.nick, aclient.user.ip,\
                                    float(time.time() + (int(duration) * 60)))
                self.notifyAll('307 ' + str(aclient.id) + chr(28) + str(self.parent.id) + chr(28) + str(msg) + chr(4))

                self.parent.parent.lock.acquire()
                try:
                    aclient.shutdown = 1
                    aclient.socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                self.parent.parent.lock.release()
        return 1

    ### USER MANAGEMENT ###
    def CREATEUSER(self, parameters):
        if not self.parent.user.checkPrivs("createAccounts"):
            self.reject(516)
            return 0
        username = parameters[0]
        password = parameters[1]
        group = parameters[2]
        privs = wireduser.wiredPrivs(self.parent)
        privs.listToPrivs(parameters[3:])
        privstring = privs.buildUserList()
        if not self.parent.addUser([username, password, group, 1, privstring]):
            self.parent.sendData("514 Account Exists" + chr(4))
            self.logger.info("%s tried to add already existing user %s", self.parent.user.user, username)
            return 0
        self.logger.info("%s added user %s", self.parent.user.user, username)
        return 1

    def CREATEGROUP(self, parameters):
        if not self.parent.user.checkPrivs("createAccounts"):
            self.reject(516)
            return 0
        username = parameters[0]
        password = ''
        group = parameters[0]
        privs = wireduser.wiredPrivs(self.parent)
        privs.listToPrivs(parameters[1:])
        privstring = privs.buildUserList()
        if not self.parent.addUser([username, password, group, 0, privstring]):
            self.parent.sendData("514 Account Exists" + chr(4))
            self.logger.info("%s tried to add already existing group %s", self.parent.user.user, group)
            return 0
        self.logger.info("%s added group %s", self.parent.user.user, group)
        return 1

    def USERS(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        users = self.parent.getUsers()
        for auser in users:  # start userlist
            self.parent.sendData("610 " + str(auser[0]) + chr(4))
        self.parent.sendData('611 Done' + chr(4))
        return 1

    def GROUPS(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        groups = self.parent.getGroups()
        for agroup in groups:  # start userlist
            self.parent.sendData("620 " + str(agroup[0]) + chr(4))
        self.parent.sendData('621 Done' + chr(4))
        return 1

    def READUSER(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        users = self.parent.getUsers()
        for auser in users:
            if str(auser[0]) == str(parameters[0]):
                self.parent.sendData("600 " + str(auser[0]) + chr(28) + str(auser[1]) + chr(28) +\
                                     str(auser[2]) + chr(28) + str(auser[4]) + chr(4))
                return 1
        return 0

    def READGROUP(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        groups = self.parent.getGroups()
        for agroup in groups:
            if str(agroup[0]) == str(parameters[0]):
                self.parent.sendData("601 " + str(agroup[0]) + chr(28) + str(agroup[4]) + chr(4))
                return 1
        return 0

    def DELETEUSER(self, parameters):
        if not self.parent.user.checkPrivs("deleteAccounts"):
            self.reject(516)
            return 0
        if not self.parent.delUser(parameters[0]):
            self.logger.error("server failed to delete account %s", parameters[0])
            # send error
        self.logger.info("%s deleted account %s", self.parent.user.user, parameters[0])
        return 1

    def DELETEGROUP(self, parameters):
        if not self.parent.user.checkPrivs("deleteAccounts"):
            self.reject(516)
            return 0
        if not self.parent.delGroup(parameters[0]):
            self.logger.error("server failed to delete group %s", parameters[0])
            # send error
            return 0
        self.logger.info("%s deleted group %s", self.parent.user.user, parameters[0])
        return 1

    def EDITUSER(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        privs = wireduser.wiredPrivs(self.parent)
        privs.listToPrivs(parameters[3:])
        privstring = privs.buildUserList()
        if not self.parent.editUser([parameters[0], parameters[1], parameters[2], privstring]):
            self.logger.error("server failed to edit account %s", parameters[0])
            #send error
            return 0
        # now update all users logged in as this user
        self.parent.updateUserPrivs(parameters[0], privstring)
        self.logger.info("%s modified account %s", self.parent.user.user, parameters[0])
        return 1

    def EDITGROUP(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        privs = wireduser.wiredPrivs(self.parent)
        privs.listToPrivs(parameters[1:])
        privstring = privs.buildUserList()
        if not self.parent.editGroup([parameters[0], "", parameters[0], privstring]):
            self.logger.error("server failed to edit account %s", parameters[0])
            #send error
            return 0
        # now update all users logged in and are member of this group
        self.parent.updateGroupPrivs(parameters[0], privstring)
        self.logger.info("%s modified group %s", self.parent.user.user, parameters[0])
        return 1

    ## Files ##
    def LIST(self, parameters):
        wiredfiles.LISTgetter(self, self.parent.user, self.parent.indexer, parameters[0], self.parent.sendData).start()
        return 0

    def LISTRECURSIVE(self, parameters):
        wiredfiles.LISTRECURSIVEgetter(self, self.parent.user, self.parent.indexer, parameters[0], self.parent.sendData).start()
        return 0

    def STAT(self, parameters):
        files = wiredfiles.wiredFiles(self.parent)
        filelist = files.getStat(parameters[0])
        ftype = 0
        comment = files.getComment(parameters[0])
        if not filelist:
            return 0
        if filelist['type'] == 'dir':
            ftype = files.getFolderType(parameters[0])
        response = "402 " + str(filelist['name']) + chr(28) + str(ftype) + chr(28) + str(filelist['size']) +\
        chr(28) + wiredfunctions.wiredTime(filelist['created']) + chr(28) +\
        wiredfunctions.wiredTime(filelist['modified']) + chr(28) + str(filelist['hash']) +\
        chr(28) + str(comment) + chr(4)
        self.parent.sendData(response)
        return 1

    def DELETE(self, parameters):
        if not self.parent.user.checkPrivs("deleteFiles"):
            self.reject(516)
            return 0
        file = wiredfiles.wiredFiles(self.parent)
        if file.delete(parameters[0]):
            self.logger.info("%s deleted file %s", self.parent.user.user, parameters[0])
            return 1
        self.logger.error("server failed to delete file %s", parameters[0])
        return 0

    def MOVE(self, parameters):
        if not self.parent.user.checkPrivs("alterFiles"):
            self.reject(516)
            return 0
        move = wiredfiles.wiredFiles(self.parent)
        if not move.move(parameters[0], parameters[1]):
            self.reject(520)
            return 0
        self.logger.info("%s moved %s to %s", self.parent.user.user, parameters[0], parameters[1])
        return 1

    def TYPE(self, parameters):
        if not self.parent.user.checkPrivs("alterFiles"):
            self.reject(516)
            return 0
        folder = wiredfiles.wiredFiles(self.parent)
        folder.setFolderType(parameters[0], parameters[1])
        return 1

    def COMMENT(self, parameters):
        if not self.parent.user.checkPrivs("alterFiles"):
            self.reject(516)
            return 0
        com = wiredfiles.wiredFiles(self.parent)
        if not com.setComment(parameters[0], parameters[1]):
            # send error here
            self.logger.error("server failed to save comment for file %s", parameters[0])
            return 0
        return 1

    def FOLDER(self, parameters):
        type = 0
        folder = wiredfiles.wiredFiles(self.parent)
        if not self.parent.user.checkPrivs("createFolders"):
            if not folder.isUploadFolder(parameters[0]):
                print "parent folder is no upload folder: %s" % parameters[0]
                self.reject(516)
                return 0
            else:
                type = 2
                print "Allowing creation of uploadfolder %s" % parameters[0]
        if not folder.createFolder(parameters[0], type):
            # send error here
            self.logger.error("server failed to create folder %s", parameters[0])
            return 0
        return 1

    def GET(self, parameters):
        if not self.parent.user.checkPrivs("download"):
            self.reject(516)
            return 0
        transfer = wiredtransfer.wiredTransfer(self)
        try:
            transfer.userid = self.parent.id
            transfer.txLimit = int(self.parent.user.privs.downloadSpeed)
            transfer.rxLimit = int(self.parent.user.privs.uploadSpeed)
            transfer.file = parameters[0]
            transfer.id = transfer.genID()
            transfer.offset = int(parameters[1])
            transfer.type = "DOWN"
        except KeyError:
            self.logger.error("Invalid GET request: %s", parameters)
            ##send error
            return 0
        self.parent.queueTransfer(transfer)
        # add queued check here
        response = "400 " + str(transfer.file) + chr(28) + str(transfer.offset) + chr(28) + str(transfer.id) + chr(4)
        self.parent.sendData(response)
        self.logger.info("qeued transfer of %s for user %s (id: %s)", transfer.file, self.parent.user.user, transfer.id)
        return 1

    def PUT(self, parameters):
        if not self.parent.user.checkPrivs("upload"):
            self.reject(516)
            return 0
        transfer = wiredtransfer.wiredTransfer(self)
        transfer.userid = self.parent.id
        transfer.txLimit = int(self.parent.user.privs.downloadSpeed)
        transfer.rxLimit = int(self.parent.user.privs.uploadSpeed)
        transfer.file = parameters[0]
        transfer.checksum = str(parameters[2])
        # check for already existing files
        precheck = wiredfiles.wiredFiles(self)
        result = precheck.uploadCheck(transfer.file, transfer.checksum)
        if result == 521:   # file exists
            self.logger.error("%s tried to upload alredy existing file %s", self.parent.user.user, parameters[0])
            self.parent.sendData("521 File or Directory Exists" + chr(4))
            return 0
        if result == 522:   # file exists
            self.logger.info("file checksum mismatch in %s from user %s", transfer.file, self.parent.user.user)
            self.parent.sendData("522 Checksum Mismatch" + chr(4))
            return 0
        transfer.offset = result
        transfer.id = transfer.genID()
        transfer.size = int(parameters[1])
        transfer.type = "UP"
        self.parent.queueTransfer(transfer)
        response = "400 " + str(transfer.file) + chr(28) + str(transfer.offset) + chr(28) + str(transfer.id) + chr(4)
        self.parent.sendData(response)
        return 1

    def SEARCH(self, parameters):
        result = self.parent.doSearch(str(parameters[0]))
        if len(result):
            for aresult in result:
                if not self.parent.user.checkPrivs("viewDropboxes"):
                    files = wiredfiles.wiredFiles(self)
                    if files.checkDropBoxinPath(str(aresult[0])):
                        break
                if aresult[1] == "dir":
                    type = 1
                    size = wiredfiles.wiredFiles(self)
                    size = size.simpleDirList(str(self.config['fileRoot']) + str(aresult[0]))
                    if size:
                        size = len(size)
                    else:
                        size = 0
                else:
                    type = 0
                    size = aresult[2]
                data = "420 " + str(aresult[0]) + chr(28) + str(type) + chr(28) + str(size) + chr(28) +\
                wiredfunctions.wiredTime(aresult[3]) + chr(28) + wiredfunctions.wiredTime(aresult[4]) + chr(4)
                self.parent.sendData(data)
        self.parent.sendData("421 Done" + chr(4))
        return 1

    def serverInfo(self, proto=1.1):
        self.parent.protoVersion = proto
        platform = wiredfunctions.getPlatform()
        serverstart = wiredfunctions.wiredTime(str(self.parent.config['serverStarted']))
        msg = "200 " + str(self.parent.config['appName']) + "/" + str(self.parent.config['appVersion']) +\
        " (" + platform['OS'] + "; " + str(platform['OSVersion']) + "; " + platform['ARCH'] + ") (" +\
        platform['TLSLib'] + ')' + chr(28) + str(self.parent.protoVersion) + chr(28) +\
        (self.parent.config['serverName']) + chr(28) + str(self.parent.config['serverDesc']) + chr(28) +\
        serverstart + chr(28) + str(self.parent.serverFiles) + chr(28) + str(self.parent.serverSize) + chr(4)
        return msg

    ## Data handling ##
    def notifyAll(self, data):
        clients = self.parent.getUserList()
        self.parent.parent.lock.acquire()
        for aid, aclient in clients.items():
            aclient.sendData(data)
        self.parent.parent.lock.release()
        return 1

    def notifyChat(self, data, chat):
        clients = self.parent.getUserList()
        self.parent.parent.lock.acquire()
        for aid, aclient in clients.items():
            try:
                check = aclient.user.activeChats[int(chat)]
            except KeyError:
                check = 0
            if check:
                aclient.sendData(data)
        self.parent.parent.lock.release()
        return 1

    def reject(self, reason):
        if int(reason) == 500:
            response = "500 Command Failed"
        if int(reason) == 501:
            response = "501 Command Not Recognized"
        if int(reason) == 502:
            response = "502 Command Not Implemented"
        if int(reason) == 510:
            response = "510 Login Failed"
        if int(reason) == 511:
            response = "511 Banned"
        if int(reason) == 515:
            response = "515 Cannot Be Disconnected"
        if int(reason) == 516:
            response = "516 Permission Denied"
        if int(reason) == 520:
            response = "520 File or Directory Not Found"

        self.parent.sendData(response + chr(4))
        return 1

    def gotdata(self, data):
        data = (str(data).strip())
        if data.count(chr(4)) == 0:
            self.logger.error("incomplete transmission from %s: %s", self.parent.user.ip, data)
            return 0
        split = wiredfunctions.tsplit(data, chr(4))
        for data in split:
            if not data:
                break
            data = data.replace(chr(4), '')
            command = data
            parameters = {}
            if data.count(' ') != 0:
                end = data.index(' ')
                parameters = data[end + 1:]
                command = data[:end]
                parameters = wiredfunctions.tsplit(parameters, chr(28))

            self.logger.debug("got command %s from %s", command, self.parent.user.ip)
            try:
                result = getattr(self, str(command).upper())(parameters)
            except AttributeError:
                print sys.exc_info()
                self.logger.error("unkown command %s from %s", command, self.parent.user.ip)
                self.parent.sendData('502 Command Not Implemented' + chr(4))
                pass

            if command != "PING" and self.parent.user.loginDone:
                self.parent.user.lastActive = time.time()
                if self.parent.user.checkWakeNotify():
                    data = self.parent.user.buildStatusChanged()
                    data = "304 " + data + chr(4)
                    self.notifyAll(data)
                    self.parent.user.knownIdle = 0
        return 1
