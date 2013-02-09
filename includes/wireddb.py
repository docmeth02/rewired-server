import sqlite3
from time import time
import os


class wiredDB():
    def __init__(self, config, logger):
        self.conn = 0
        self.logger = logger
        self.config = config
        self.pointer = 0
        self.dbIsOpen = 0

    ## DB HANDLING ##
    def openDB(self):
        self.conn = sqlite3.connect(self.config["dbFile"], check_same_thread=False)
        self.pointer = self.conn.cursor()
        self.conn.text_factory = str
        self.dbIsOpen = 1
        return 1

    def closeDB(self):
        if not self.dbIsOpen:
            return false
        self.conn.close()
        self.dbIsOpen = 0
        return 1

    ## User Managment ##
    def loadUsers(self):
        data = []
        data = self.loadData(1)
        return data

    def loadGroups(self):
        data = []
        data = self.loadData(0)
        return data

    def updateElement(self, data, type):
        if not self.openDB():
            return 0
        sql = "UPDATE wiredUsers SET password='" + str(data[1]) + "', groupname='" + str(data[2]) + "', privs='" +\
        str(data[3]) + "' WHERE name='" + str(data[0]) + "' AND type='" + str(type) + "';"
        result = self.pointer.execute(sql)
        self.conn.commit()
        if not result:
            self.closeDB()
            self.logger.error("db failed to update a row")
            return 0
        self.closeDB()
        return 1

    def deleteElement(self, username, type):
        if not self.openDB():
            return 0
        sql = "DELETE FROM wiredUsers WHERE name='" + str(username) + "' AND type='" + str(type) + "';"
        result = self.pointer.execute(sql)
        self.conn.commit()
        if not result:
            self.closeDB()
            self.logger.error("db failed to delete a row")
            return 0
        self.closeDB()
        return 1

    def loadData(self, type):
        if not self.openDB():
            return 0
        # since there is no check if a table exists try to create basic userdb everytime we open the db
        self.pointer.execute('CREATE TABLE IF NOT EXISTS wiredUsers (name TEXT UNIQUE, password TEXT, groupname \
                             TEXT, type BOOL, privs TEXT, PRIMARY KEY(name))')  # type group/user 0/1
        self.pointer.execute("INSERT OR IGNORE INTO wiredUsers VALUES (?, ?, ?, ?, ?);", ["admin",\
                            "d033e22ae348aeb5660fc2140aec35850c4da997", '', 1, '1' + chr(28) + '1' + chr(28) +\
                            '1' + chr(28) + '1' + chr(28) + '1' + chr(28) + '1' + chr(28) + '1' + chr(28) + '1' +\
                            chr(28) + '1' + chr(28) + '1' + chr(28) + '1' + chr(28) + '1' + chr(28) + '1' + chr(28) +\
                            '1' + chr(28) + '1' + chr(28) + '1' + chr(28) + '1' + chr(28) + '1' + chr(28) + '0' +\
                            chr(28) + '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '1'])
        if self.config['guestOn']:
            self.pointer.execute("INSERT OR IGNORE INTO wiredUsers VALUES (?, ?, ?, ?, ?);", ["guest", "", "", 1, '0' +\
                                chr(28) + '0' + chr(28) + '1' + chr(28) + '0' + chr(28) + '1' + chr(28) + '1' + chr(28) +\
                                '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '0' +\
                                chr(28) + '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '0' + chr(28) +\
                                '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '0' + chr(28) + '0'])
        self.conn.commit()
        data = 0
        self.pointer.execute("SELECT * FROM wiredUsers WHERE type=?;", [type])
        data = self.pointer.fetchall()
        if len(data) == 0:
            self.logger.info("userdb returned empty result for type %s", type)
            data = []
        self.closeDB()
        return data

    def saveUser(self, user):
        if not self.openDB():
            return 0
        self.pointer.execute("SELECT * FROM wiredUsers WHERE name = '" + str(user[0]) +\
                             "' AND type ='" + str(user[3]) + "';")
        existing = self.pointer.fetchall()
        if existing:
            # user already exists!
            self.closeDB()
            return 0
        self.pointer.execute("INSERT INTO wiredUsers VALUES ('" + str(user[0]) + "','" + str(user[1]) + "', '" +\
                             str(user[2]) + "', '" + str(user[3]) + "', '" + str(user[4]) + "');")
        self.conn.commit()
        self.closeDB()
        return 1

    ### News ###
    def loadNews(self):
        if not self.openDB():
            return 0
        sql = 'create table if not exists wiredNews (nick TEXT, date FLOAT, news TEXT)'
        self.pointer.execute(sql)
        self.conn.commit()
        data = 0
        self.pointer.execute("SELECT * FROM wiredNews")
        data = self.pointer.fetchall()
        if not data:
            self.logger.error("db returned empty news")
            data = []
        self.closeDB()
        try:
            data = sorted(data, key=lambda anews: anews[1])
        except:
            pass
        return data

    def saveNews(self, news):
        if not self.openDB():
            return 0
        self.pointer.execute("INSERT INTO wiredNews VALUES (?,?,?);", [news[0], news[1], news[2]])
        self.conn.commit()
        self.closeDB()
        return 1

    def dropNews(self):
        if not self.openDB():
            return 0
        self.pointer.execute("DELETE FROM wiredNews")
        self.conn.commit()
        self.closeDB()
        return 1

    ## File Index ##
    def openIndex(self):
        if not self.openDB():
            return 0
        sql = 'create table if not exists wiredIndex (name TEXT, type TEXT, size INTEGER, created FLOAT, \
              modified FLOAT, PRIMARY KEY(name));'
        self.pointer.execute(sql)
        self.conn.commit()
        dbIsOpen = 1
        return 1

    def closeIndex(self):
        self.closeDB()
        self.dbIsOpen = 0
        return 1

    def updateIndex(self, filelist):
        self.openIndex()
        if not self.openIndex():
            return 0
        processed = 0
        notify = time()
        for aitem in filelist:
            self.pointer.execute("INSERT OR REPLACE INTO wiredIndex VALUES (?, ?, ?, ?, ?);", [str(aitem['name']), \
                                str(aitem['type']), str(aitem['size']), str(aitem['created']), str(aitem['modified'])])
            processed += 1
            if time() >= notify:
                self.logger.debug("Index: processed %s out of %s items.", processed, len(filelist))
                notify = time() + 60
        self.conn.commit()
        self.closeIndex()
        return 1

    def searchIndex(self, searchstring):
        self.openIndex()
        self.pointer.execute("SELECT * FROM wiredIndex WHERE name LIKE ?;", ['%' + str(searchstring) + '%'])
        result = self.pointer.fetchall()
        self.closeIndex()
        return result

    def pruneIndex(self, config, filelist):
        self.openIndex()
        self.pointer.execute("SELECT * FROM wiredIndex;")
        data = self.pointer.fetchall()
        lookup = {}
        for afile in filelist:
            lookup[afile['name']] = afile['type']
        for aitem in data:
            if aitem[0] in lookup:
                if lookup[aitem[0]] == aitem[1]:
                    continue  # all good
            # file vanished - remove from index
            self.pointer.execute("DELETE FROM wiredIndex WHERE name = ?", [aitem[0]])
        self.conn.commit()
        self.pointer.execute("VACUUM")
        self.conn.commit()
        self.closeIndex()
        return 1

    def getServerSize(self):
        self.openIndex()
        self.pointer.execute("SELECT SUM(size) FROM wiredIndex WHERE TYPE = 'file';")
        result = self.pointer.fetchone()
        self.pointer.fetchall()
        self.conn.commit()
        try:
            result = int(result[0])
        except TypeError:
            result = 0
            pass
        return result

    def getServerFiles(self):
        self.openIndex()
        self.pointer.execute("SELECT Count(*) FROM wiredIndex WHERE TYPE = 'file';")
        result = self.pointer.fetchone()
        self.conn.commit()
        self.closeIndex()
        try:
            result = int(result[0])
        except TypeError:
            result = 0
            pass
        return result

    ## Banned Users ##
    def openBans(self):
        if not self.openDB():
            return 0
        sql = 'create table if not exists bans (user TEXT, nick TEXT, ip TEXT, ends REAL);'
        try:
            self.pointer.execute(sql)
            self.conn.commit()
        except sqlite3.Error:
            self.logger.error("Failed to create ban table.")
            return 0
        dbIsOpen = 1
        return 1

    def closeBans(self):
        if not self.dbIsOpen:
            return 0
        self.closeDB()
        self.dbIsOpen = 0
        return 1

    def addBan(self, user, nick, ip, ends):
        self.openBans()
        try:
            self.pointer.execute("INSERT INTO bans VALUES (?,?,?,?);", [user, nick, ip, ends])
            self.conn.commit()
        except sqlite3.Error:
            self.logger.error("Failed to add ban to db")
            self.closeBans()
            return 0
        self.closeBans()
        return 1

    def checkBan(self, user, ip):
        self.openBans()
        try:
            self.pointer.execute("SELECT * FROM bans WHERE user = ? AND ip = ?;", [user, ip])
            data = self.pointer.fetchall()
        except sqlite3.Error:
            self.logger.error("Failed to query db bans")
            self.closeBans()
            return 0
        self.closeBans()
        if not data:
            return 0
        try:
            data = data[0]
            banend = data[3]
        except IndexError:
            return 0
        if time() > float(banend):  # ban has expired
            self.removeBan(data[0], data[1], data[2], data[3])
            return 0
        self.logger.info("Login from banned ip %s (user:%s) detected.", data[2], data[0])
        return 1

    def removeBan(self, user, nick, ip, ends):
        self.openBans()
        try:
            self.pointer.execute("DELETE FROM bans WHERE user = ? AND nick = ? AND ip = ? AND ends = ?;",\
                                 [user, nick, ip, ends])
            self.conn.commit()
            self.pointer.execute("VACUUM")
        except sqlite3.Error:
            self.closeBans()
            self.logger.error("Failed to delete ban from DB")
            return 0
        self.closeBans()
        return 1
