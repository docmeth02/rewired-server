import wiredfunctions
import wireduser
import wiredfiles
import wiredtransfer
import time
import sys
import socket
import os
from traceback import format_exc


class commandHandler():
    def __init__(self, parent):
        self.parent = parent
        self.logger = parent.logger
        self.wiredlog = parent.wiredlog
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
            self.notifyAll(self.buildResponse(304, [data]))
            self.wiredlog.log_event('NICK', {'USER': self.parent.user.user, 'NICK': self.parent.user.nick})
        return 1

    def ICON(self, parameters):
        self.parent.user.icon = str(parameters[0])
        self.parent.user.image = str(parameters[1])
        if self.parent.user.loginDone:
            data = self.buildResponse(340, [self.parent.id, self.parent.user.image])
            self.notifyAll(data)
        return 1

    def STATUS(self, parameters):
        self.parent.user.status = str(parameters[0])
        if self.parent.user.loginDone:
            data = self.parent.user.buildStatusChanged()
            self.notifyAll(self.buildResponse(304, [data]))
            self.wiredlog.log_event('STATUS', {'USER': self.parent.user.user, 'STATUS': self.parent.user.status})
        return 1

    def CLIENT(self, parameters):
        self.parent.user.client = str(parameters[0])
        return 1

    def USER(self, parameters):
        # add user check here
        self.parent.user.user = str(parameters[0])
        return 1

    def PRIVILEGES(self, parameters):
        self.parent.sendData(self.buildResponse(602, [self.parent.user.privs.privsToString()]))
        return 1

    def PASS(self, parameters):
        self.logger.info("Login attempt for user %s", self.parent.user.user)
        user = self.parent.checkLogin(str(self.parent.user.user), str(parameters[0]), self.parent.user.ip)
        if not user:
            # login failed
            self.logger.error("Login failed for user %s", self.parent.user.user)
            self.reject(510)
            self.parent.shutdown = 1
            self.wiredlog.log_event('LOGIN', {'RESULT': 'FAILED', 'USER': self.parent.user.user,
                                              'NICK': self.parent.user.nick})
            return 0
        if self.parent.user.loginDone:
            # qwired will try to relogin on an already established connection:
            self.logger.info("Ignoring reconnect try on already established link for user %s", self.parent.user.user)
            return 1
        self.parent.user.id = self.parent.getGlobalUserID()  # get ourself a shiny new userid
        if user[2]:  # group member
            group = self.parent.getGroup(str(user[2]))
            if not group:
                self.logger.error("Invalid group %s referenced for user %s", group, self.parent.user.user)
                self.reject(510)
                self.parent.shutdown = 1
                return 0
            self.logger.debug("User %s is a member of group %s", self.parent.user.user, group[0])
            self.parent.user.memberOfGroup = group[0]
            self.parent.user.mapPrivs(group[4])
        else:
            self.parent.user.mapPrivs(user[4])
        self.logger.info("Login for user %s successful.", self.parent.user.user)
        self.parent.sendData(self.buildResponse(201, [self.parent.user.id]))  # send login successful
        topic = self.getTopic(1)
        if topic:
            self.parent.sendData(topic)  # send topic for public chat (if any)
        self.parent.loginDone()  # add this client to the logged in user list
        self.parent.user.loginDone = 1  # login is now complete
        self.wiredlog.log_event('LOGIN', {'RESULT': 'OK', 'USER': self.parent.user.user,
                                          'NICK': self.parent.user.nick, 'IP': self.parent.user.ip})
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
            if aclient.user.id is None:  # skip users that are not logged in yet
                continue
            ip = ""
            host = ""
            user = ""
            if (self.parent.user.checkPrivs("getUserInfo") and 'MODERATE' in self.config['securityModel'].upper())\
                    or 'OFF' in self.config['securityModel'].upper():
                ip = aclient.user.ip
                host = aclient.user.host
                user = aclient.user.user
            try:
                data = self.buildResponse(310, [chatid, aclient.user.id, aclient.user.idle, aclient.user.admin,
                                                aclient.user.icon, aclient.user.nick, user, ip, host,
                                                aclient.user.status, aclient.user.image])
                self.parent.sendData(data)
            except Exception as e:
                self.logger.debug("WHO Error: %s %s", str(e), format_exc())
                continue
        self.parent.sendData(self.buildResponse(311, [chatid]))  # send userlist done
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
        self.parent.sendData(self.buildResponse(308, [userinfo]))
        self.wiredlog.log_event('INFO', {'USER': self.parent.user.user, 'NICK': self.parent.user.nick,
                                         'TARGET': clients[int(parameters[0])].user.user})
        return 1

    def SAY(self, parameters):
        if not len(parameters[1]) or self.parent.user.id is None:
            self.logger.error('SAY: invalid parameters')
            return 0
        clients = self.parent.getUserList()
        chatid = int(parameters[0])
        chat = wiredfunctions.tsplit(parameters[1], '\n')
        for achat in chat:
            self.notifyChat(self.buildResponse(300, [chatid, self.parent.user.id, achat]), chatid)
        return 1

    def ME(self, parameters):
        if not len(parameters[1]) or self.parent.user.id is None:
            self.logger.error('ME: invalid parameters')
            return 0
        chatid = parameters[0]
        self.notifyChat(self.buildResponse(301, [chatid, self.parent.user.id, parameters[1]]), chatid)
        return 1

    def BANNER(self, parameters):
        self.parent.sendData(self.buildResponse(203, [self.config['banner']]))
        return 1

    def POST(self, parameters):
        if not self.parent.user.checkPrivs("postNews"):
            self.reject(516)
            return 0
        self.parent.postNews(parameters[0])
        date = wiredfunctions.wiredTime(time.time())
        self.notifyAll(self.buildResponse(322, [self.parent.user.nick, date, parameters[0]]))
        self.logger.info("%s posted a news item", self.parent.user.nick)
        self.wiredlog.log_event('POST', {'USER': self.parent.user.user, 'NICK': self.parent.user.nick})
        return 1

    def NEWS(self, parameters):
        news = self.parent.getNews()
        if news:
            for anews in news:
                date = wiredfunctions.wiredTime(float(anews[1]))
                self.parent.sendData(self.buildResponse(320, [anews[0], date, anews[2]]))
        self.parent.sendData(self.buildResponse(321, ['Done']))
        return 1

    def CLEARNEWS(self, parameters):
        if not self.parent.user.checkPrivs("clearNews"):
            self.reject(516)
            return 0
        self.parent.clearNews()
        self.parent.sendData(self.buildResponse(321, ['Done']))
        self.logger.info("%s cleared the news", self.parent.user.user)
        self.wiredlog.log_event('CLEARNEWS', {'USER': self.parent.user.user, 'NICK': self.parent.user.nick})
        return 1

    def MSG(self, parameters):
        clients = self.parent.getUserList()
        for aid, aclient in clients.items():
            if aclient.user.id is None:
                continue
            if int(aclient.user.id) == int(parameters[0]):
                aclient.sendData(self.buildResponse(305, [self.parent.user.id, parameters[1]]))
                return 1
            # raise user not found error
        return 0

    def BROADCAST(self, parameters):
        if not self.parent.user.checkPrivs("broadcast"):
            self.reject(516)
            return 0
        data = parameters[0]
        self.notifyAll(self.buildResponse(309, [self.parent.id, data]))
        self.wiredlog.log_event('BROADCAST', {'USER': self.parent.user.user, 'NICK': self.parent.user.nick})

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
        if data:
            self.notifyChat(data, chatid)
        if chatid == 1:
            self.wiredlog.log_event('TOPIC', {'USER': self.parent.user.user, 'NICK': self.parent.user.nick,
                                              'TOPIC': str(parameters[1])})
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
        return self.buildResponse(341, [chat, nick, login, ip, topictime, topic])

    def PING(self, parameters):
        self.parent.sendData(self.buildResponse(202, ['PONG']))
        self.parent.lastPing = time.time()
        return 1

    def PRIVCHAT(self, parameters):
        chatID = self.parent.getGlobalPrivateChatID()  # get a new private chat id
        self.parent.sendData(self.buildResponse(330, [chatID]))
        self.parent.user.activeChats[int(chatID)] = 1
        return 1

    def INVITE(self, parameters):
        if (int(self.parent.user.id) == int(parameters[0])):
            return 0
        clients = self.parent.getUserList()
        for aid, aclient in clients.items():
            if aclient.id == int(parameters[0]):
                aclient.sendData(self.buildResponse(331, [parameters[1], self.parent.id]))
        return 1

    def DECLINE(self, parameters):
        chatid = int(parameters[0])
        self.notifyChat(self.buildResponse(332, [chatid, self.parent.id]), chatid)

    def JOIN(self, parameters):
        self.parent.user.activeChats[int(parameters[0])] = 1
        self.joinChat(int(parameters[0]))
        return 1

    def joinChat(self, chat):
        clients = self.parent.getUserList()
        userlist = self.parent.user.buildUserList()
        self.parent.user.activeChats[int(chat)] = time.time()  # time user joined this chat
        for aid, aclient in clients.items():
            if aclient.id != self.parent.id and int(chat) in aclient.user.activeChats:
                aclient.sendData(self.buildResponse(302, [chat, userlist]))
        return 1

    def LEAVE(self, parameters):
        self.leaveChat(int(parameters[0]))
        return 1

    def leaveChat(self, chat):
        if not self.parent.user.loginDone or self.parent.user.id is None:
            return 0  # don't send leave for clients with failed logins
        self.parent.user.activeChats.pop(int(chat), 0)
        self.notifyChat(self.buildResponse(303, [chat, self.parent.user.id]), chat)
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
                self.notifyAll(self.buildResponse(306, [parameters[0], self.parent.id, parameters[1]]))
                with aclient.lock:
                    try:
                        aclient.shutdown = 1
                        aclient.socket.shutdown(socket.SHUT_RDWR)
                    except:
                        self.logger.error("Failed to terminate thread for user %s", aclient.user.nick)

                self.logger.info("%s was kicked by %s", aclient.user.nick, self.parent.user.user)
                self.wiredlog.log_event('KICK', {'USER': self.parent.user.user, 'VICTIM': aclient.user.user})
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
                self.parent.banUser(aclient.user.user, aclient.user.nick, aclient.user.ip,
                                    float(time.time() + (int(duration) * 60)))
                self.notifyAll(self.buildResponse(307, [aclient.id, self.parent.id, msg]))
                with aclient.lock:
                    try:
                        aclient.shutdown = 1
                        aclient.socket.shutdown(socket.SHUT_RDWR)
                    except:
                        pass
                self.wiredlog.log_event('BAN', {'USER': self.parent.user.user, 'VICTIM': aclient.user.user,
                                                'DURATION': int(duration)})
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
        privstring = privs.privsToString()
        if not self.parent.addUser([username, password, group, 1, privstring]):
            self.parent.sendData(self.buildResponse(514, ['Account Exists']))
            self.logger.info("%s tried to add already existing user %s", self.parent.user.user, username)
            return 0
        self.logger.info("%s added user %s", self.parent.user.user, username)
        self.wiredlog.log_event('CREATEUSER', {'USER': self.parent.user.user, 'NAME': username})
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
            self.parent.sendData(self.buildResponse(514, ['Account Exists']))
            self.logger.info("%s tried to add already existing group %s", self.parent.user.user, group)
            return 0
        self.logger.info("%s added group %s", self.parent.user.user, group)
        self.wiredlog.log_event('CREATEGROUP', {'USER': self.parent.user.user, 'NAME': group})
        return 1

    def USERS(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        users = self.parent.getUsers()
        for auser in users:  # start userlist
            self.parent.sendData(self.buildResponse(610, [auser[0]]))
        self.parent.sendData(self.buildResponse(611, ['Done']))
        return 1

    def GROUPS(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        groups = self.parent.getGroups()
        for agroup in groups:  # start userlist
            self.parent.sendData(self.buildResponse(620, [agroup[0]]))
        self.parent.sendData(self.buildResponse(621, ['Done']))
        return 1

    def READUSER(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        users = self.parent.getUsers()
        for auser in users:
            if str(auser[0]) == str(parameters[0]):
                self.parent.sendData(self.buildResponse(600, [auser[0], auser[1], auser[2], auser[4]]))
                return 1
        return 0

    def READGROUP(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        groups = self.parent.getGroups()
        for agroup in groups:
            if str(agroup[0]) == str(parameters[0]):
                self.parent.sendData(self.buildResponse(601, [agroup[0], agroup[4]]))
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
        self.wiredlog.log_event('DELETEUSER', {'USER': self.parent.user.user, 'NAME': parameters[0]})
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
        self.wiredlog.log_event('DELETEGROUP', {'USER': self.parent.user.user, 'NAME': parameters[0]})
        return 1

    def EDITUSER(self, parameters):
        if not self.parent.user.checkPrivs("editAccounts"):
            self.reject(516)
            return 0
        privs = wireduser.wiredPrivs(self.parent)
        privs.listToPrivs(parameters[3:])
        privstring = privs.privsToString()
        if not self.parent.editUser([parameters[0], parameters[1], parameters[2], privstring]):
            self.logger.error("server failed to edit account %s", parameters[0])
            #send error
            return 0
        # now update all users logged in as this user
        self.parent.updateUserPrivs(parameters[0], privstring)
        self.logger.info("%s modified account %s", self.parent.user.user, parameters[0])
        self.wiredlog.log_event('EDITUSER', {'USER': self.parent.user.user, 'NAME': parameters[0]})
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
        self.wiredlog.log_event('EDITGROUP', {'USER': self.parent.user.user, 'NAME': parameters[0]})
        return 1

    ## Files ##
    def LIST(self, parameters):
        wiredfiles.LISTgetter(self, self.parent.user, None, parameters[0], self.parent.sendData).start()
        self.wiredlog.log_event('LIST', {'USER': self.parent.user.user, 'NICK': self.parent.user.nick,
                                         'DIR': parameters[0]})
        return 0

    def LISTRECURSIVE(self, parameters):
        wiredfiles.LISTRECURSIVEgetter(self, self.parent.user, None, parameters[0], self.parent.sendData).start()
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
        self.parent.sendData(self.buildResponse(402, [filelist['name'], ftype, filelist['size'],
                                                      wiredfunctions.wiredTime(filelist['created']),
                                                      wiredfunctions.wiredTime(filelist['modified']),
                                                      filelist['hash'], comment]))
        self.wiredlog.log_event('STAT', {'USER': self.parent.user.user, 'NAME': parameters[0]})
        return 1

    def DELETE(self, parameters):
        if not self.parent.user.checkPrivs("deleteFiles"):
            self.reject(516)
            return 0
        file = wiredfiles.wiredFiles(self.parent)
        if file.delete(parameters[0]):
            self.logger.info("%s deleted file %s", self.parent.user.user, parameters[0])
            self.wiredlog.log_event('DELETE', {'USER': self.parent.user.user, 'NAME': parameters[0]})
            return 1
        self.reject(500)
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
        self.wiredlog.log_event('MOVE', {'USER': self.parent.user.user, 'SRC': parameters[0], 'TARGET': parameters[1]})
        return 1

    def TYPE(self, parameters):
        if not self.parent.user.checkPrivs("alterFiles"):
            self.reject(516)
            return 0
        folder = wiredfiles.wiredFiles(self.parent)
        folder.setFolderType(parameters[0], parameters[1])
        self.wiredlog.log_event('TYPE', {'USER': self.parent.user.user, 'NAME': parameters[0], 'TYPE': parameters[1]})
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
        self.wiredlog.log_event('COMMENT', {'USER': self.parent.user.user, 'NAME': parameters[0],
                                            'COMMENT': parameters[1]})
        return 1

    def FOLDER(self, parameters):
        type = 0
        folder = wiredfiles.wiredFiles(self.parent)
        if os.path.exists(parameters[0]):  # folder already exists
            self.reject(521)
            return 1
        if not self.parent.user.checkPrivs("createFolders"):
            if not folder.isUploadFolder(parameters[0]):
                self.logger.error("parent folder is no upload folder: %s", parameters[0])
                self.reject(516)
                return 0
            else:
                type = 2
                self.logger.error("Allowing creation of uploadfolder %s", parameters[0])
        if not folder.createFolder(parameters[0], type):
            # send error here
            self.logger.error("server failed to create folder %s", parameters[0])
            return 0
        self.wiredlog.log_event('FOLDER', {'USER': self.parent.user.user, 'NAME': parameters[0], 'TYPE': type})
        return 1

    def GET(self, parameters):
        if not self.parent.user.checkPrivs("download"):
            self.reject(516)
            return 0
        transfer = wiredtransfer.wiredTransfer(self)
        try:
            transfer.userid = self.parent.id
            transfer.limit = int(self.parent.user.privs.downloadSpeed)
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
        self.parent.sendData(self.buildResponse(400, [transfer.file, transfer.offset, transfer.id]))
        self.logger.info("qeued transfer of %s for user %s (id: %s)", transfer.file, self.parent.user.user, transfer.id)
        return 1

    def PUT(self, parameters):
        if not self.parent.user.checkPrivs("upload"):
            self.reject(516)
            return 0
        transfer = wiredtransfer.wiredTransfer(self)
        transfer.userid = self.parent.id
        transfer.limit = int(self.parent.user.privs.uploadSpeed)
        transfer.file = parameters[0]
        try:
            transfer.checksum = str(parameters[2])
        except IndexError:
            transfer.checksum = 0
        # check for already existing files
        precheck = wiredfiles.wiredFiles(self)
        result = precheck.uploadCheck(transfer.file, transfer.checksum)
        if result == 521:   # file exists
            self.logger.error("%s tried to upload alredy existing file %s", self.parent.user.user, parameters[0])
            self.reject(521)
            return 0
        if result == 522:   # file exists
            self.logger.info("file checksum mismatch in %s from user %s", transfer.file, self.parent.user.user)
            self.reject(522)
            return 0
        transfer.offset = result
        transfer.id = transfer.genID()
        transfer.size = int(parameters[1])
        transfer.type = "UP"
        self.parent.queueTransfer(transfer)
        self.parent.sendData(self.buildResponse(400, [transfer.file, transfer.offset, transfer.id]))
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
                self.parent.sendData(self.buildResponse(420, [aresult[0], type, size,
                                                              wiredfunctions.wiredTime(aresult[3]),
                                                              wiredfunctions.wiredTime(aresult[4])]))
        self.parent.sendData(self.buildResponse(421, ['Done']))
        self.wiredlog.log_event('SEARCH', {'USER': self.parent.user.user, 'NICK': self.parent.user.nick,
                                           'SEARCH': parameters[0]})
        return 1

    def serverInfo(self, proto=1.1):
        self.parent.protoVersion = proto
        platform = wiredfunctions.getPlatform()
        serverstart = wiredfunctions.wiredTime(str(self.parent.config['serverStarted']))
        string = '%s/%s (%s; %s; %s Python %s) (%s)' % (self.parent.config['appName'], self.parent.config['appVersion'],
                                                        platform['OS'], platform['OSVersion'], platform['ARCH'],
                                                        platform['PYTHON'], platform['TLSLib'])

        return self.buildResponse(200, [string, self.parent.protoVersion, self.parent.config['serverName'],
                                        self.parent.config['serverDesc'], serverstart, self.parent.serverFiles,
                                        self.parent.serverSize])

    ## Data handling ##
    def notifyAll(self, data):
        clients = self.parent.getUserList()
        for aid, aclient in clients.items():
            aclient.sendData(data)
        return 1

    def notifyChat(self, data, chat):
        clients = self.parent.getUserList()
        for aid, aclient in clients.items():
            try:
                check = aclient.user.activeChats[int(chat)]
            except KeyError:
                check = 0
            if check:
                aclient.sendData(data)
        return 1

    def reject(self, reason):
        if int(reason) == 500:
            response = self.buildResponse(500, ['Command Failed'])
        if int(reason) == 501:
            response = self.buildResponse(501, ['Command Not Recognized'])
        if int(reason) == 502:
            response = self.buildResponse(502, ['Command Not Implemented'])
        if int(reason) == 510:
            response = self.buildResponse(510, ['Login Failed'])
        if int(reason) == 511:
            response = self.buildResponse(511, ['Banned'])
        if int(reason) == 515:
            response = self.buildResponse(515, ['Cannot Be Disconnected'])
        if int(reason) == 516:
            response = self.buildResponse(516, ['Permission Denied'])
        if int(reason) == 520:
            response = self.buildResponse(520, ['File or Directory Not Found'])
        if int(reason) == 521:
            response = self.buildResponse(521, ['File or Directory Exists'])
        if int(reason) == 522:
            response = self.buildResponse(522, ['Checksum Mismatch'])

        self.parent.sendData(response)
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
            if not hasattr(self, command.upper()):
                self.logger.error("Empty command from %s: %s", self.parent.user.ip, repr(data))
                self.reject(500)
                return 0
            self.logger.debug("got command %s from %s", command, self.parent.user.ip)
            try:
                result = getattr(self, str(command).upper())(parameters)
            except Exception as e:
                self.logger.error("Error %s %s", str(e), format_exc())
                self.reject(500)
                pass

            if command != "PING" and self.parent.user.loginDone:
                self.parent.user.lastActive = time.time()
                if self.parent.user.checkWakeNotify():
                    data = self.parent.user.buildStatusChanged()
                    self.notifyAll(self.buildResponse(304, [data]))
                    self.parent.user.knownIdle = 0
        return 1

    @staticmethod
    def buildResponse(restype, payload=[]):
        response = "%s " % restype
        for i in range(0, len(payload)):
            char = chr(28)
            if i == (len(payload)-1):
                char = chr(4)
            response += "%s%s" % (payload[i], char)
        return response
