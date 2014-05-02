from sqlite3 import connect, Error
from threading import Timer, RLock
from json import loads, dumps
from time import time
from json import loads
from os.path import basename
from time import strftime, localtime


class wiredlog():
    def __init__(self, parent):
        self.parent = parent
        self.lock = RLock()
        self.config = self.parent.config
        self.logger = self.parent.logger
        self.dbIsOpen = 0
        self.shutdown = 0
        self.pointer = None
        self.buffer = []
        self.debug = 0
        self.eventcount = None
        self.committimer = Timer(60, self.commit_to_db)
        self.committimer.start()

    def openlog(self):
        self.lock.acquire()
        try:
            self.conn = connect(self.config['logdbFile'], check_same_thread=True)
            self.pointer = self.conn.cursor()
            self.conn.text_factory = str
            # make sure our db exist
            self.pointer.execute('CREATE TABLE IF NOT EXISTS rewiredlog (date REAL PRIMARY KEY,user TEXT,\
                                 type TEXT, data TEXT)')
            self.conn.commit()
        except:
            self.lock.release()
            self.logger.error("Failed to open logging db")
            return 0
        self.dbIsOpen = 1
        return 1

    def stop(self):
        self.logger.debug("Logger: shutting down logger")
        if len(self.buffer):
            self.logger.info("Logger: syncing remaining events to log")
            self.commit_to_db(True)
        self.shutdown = 1
        if self.committimer:
            self.committimer.cancel()
            self.committimer.join(1)
        self.vacuum()
        self.logger.debug("Logger: shutdown done")
        return 1

    def closelog(self):
        if not self.dbIsOpen:
            return 0
        self.conn.close()
        self.dbIsOpen = 0
        self.lock.release()
        return 1

    def vacuum(self):
        if self.openlog():
            self.pointer.execute("VACUUM")
            self.conn.commit()
        self.closelog()
        return 1

    def log_event(self, type, data):
        event = {}
        event['TYPE'] = str(type)
        event['TIME'] = time()
        event['USER'] = None
        try:  # if this event has a username use it as a db index
            event['USER'] = data['USER']
            data.pop('USER', 0)
        except:
            pass
        event['DATA'] = dumps(str(data).encode('UTF-8', errors='ignore'))
        with self.lock:
            self.buffer.append(event)
        if self.debug:
            self.logger.debug("Logged event: %s", str(event))
        return 1

    def retrieve_events(self, limit=False, filters=False, offset=False):
        if not self.openlog():
            return 0
        sql = "SELECT * FROM rewiredlog %FILTER% ORDER BY date DESC"
        if filters:
            values, line = ([], " WHERE ")
            for akey, avalue in filters.items():
                line += "%s = ? AND " % akey
                values.append(avalue)
            line = line[0:len(line) - 5]
            sql = sql.replace("%FILTER%", line)
        else:
            sql = sql.replace("%FILTER%", "", 1)
        if limit:
            sql += (" LIMIT %s" % limit)
        if offset:
            sql += (" OFFSET %s;" % offset)
        else:
            sql += ";"
        try:
            if filters:
                self.pointer.execute(sql, values)
            else:
                self.pointer.execute(sql)
            result = self.pointer.fetchall()
        except Error as e:
            print "retrieve_events: %s" % e
            return 0
        self.closelog()
        return result

    def event_count(self):
        if not self.openlog():
            return 0
        if type(self.eventcount) is int:  # we looked this up before and nothing changed since
            return self.eventcount
        self.pointer.execute('SELECT Count(*) FROM rewiredlog')
        count = self.pointer.fetchone()
        self.closelog()
        if type(count) is tuple:
            count = int(count[0])
        else:
            self.eventcount = int(count)
            return int(count)
        return count

    def commit_to_db(self, singlecommit=0):
        if len(self.buffer):
            if not self.openlog():
                return 0
            buffer = len(self.buffer)
            for aevent in self.buffer:
                self.pointer.execute("INSERT INTO rewiredlog VALUES (?, ?, ?, ?);", [aevent['TIME'], aevent['USER'],
                                                                                     aevent['TYPE'], aevent['DATA']])
            self.conn.commit()
            self.buffer = []
            self.closelog()
            if self.debug:
                self.logger.debug("Logger: commited %s out of %s events to db", buffer - len(self.buffer), buffer)
            if type(self.eventcount) is int:
                self.eventcount += (buffer - len(self.buffer))
        if not self.shutdown and not singlecommit:
            self.committimer = Timer(60, self.commit_to_db)
            self.committimer.start()
        return 1

    def format_event(self, event, extended=False):
        formated = {}
        eventMap = {
            'LOGIN': ["Login (%s)", ['IP']],
            'LOGOUT': ["Disconnected", []],
            'SERVERSTART': ["Server started", []],
            'SERVERSTOP': ["Server stopped", []],
            'LIST': ["List dir: '%s'", ['DIR']],
            'DELETE': ["Deleted %s", ['NAME']],
            'SEARCH': ["Searched for %s", ['SEARCH']],
            'UPLOAD': ["Uploaded %s <br /> (%s)", ['FILE', 'SIZE']],
            'DOWNLOAD': ["Downloaded %s <br /> (%s)", ['FILE', 'SIZE']],
            'INFO': ["Userinfo on user %s", ['TARGET']],
            'STAT': ["File Info on %s", ['NAME']],
            'MOVE': ["Moved %s", ['SRC']],
            'NICK': ["Changed Name: %s", ['NICK']],
            'STATUS': ["Changed status:<br />%s", ['STATUS']],
            'POST': ["Posted a news item", []],
            'CLEARNEWS': ["Cleared server news", []],
            'BROADCAST': ["Broadcasted a message", []],
            'TOPIC': ["Changed chat topic: <br />%s", ['TOPIC']],
            'KICK': ["Kicked user: %s", ['VICTIM']],
            'BAN': ["Banned user %s for %s", ['VICTIM', 'DURATION']],
            'CREATEUSER': ["Created user: %s", ['NAME']],
            'CREATEGROUP': ["Created group: %s", ['NAME']],
            'DELETEUSER': ["Deleted user: %s", ['NAME']],
            'DELETEGROUP': ["Deleted group: %s", ['NAME']],
            'EDITUSER': ["Modified user: %s", ['NAME']],
            'EDITGROUP': ["Modified group: %s", ['NAME']],
            'TYPE': ["Changed type of %s to %s", ['NAME', 'TYPE']],
            'COMMENT': ["Commented on %s", ['NAME']],
            'FOLDER': ["Created folder: %s", ['NAME']]
        }
        if not event[2] in eventMap:
            self.logger.error("Unknown event %s" % event[2])
            return 0
        mapping = eventMap[event[2]]
        replace = ()
        string = mapping[0] + " "
        data = loads(event[3])

        if extended and len(mapping[1]) >= 2:
            formated['STRING'] = string[0: string.find('%s')]
            string = string[string.find('%s'):]

        for avar in mapping[1]:
            try:
                value = data[avar]
            except KeyError:
                continue
            if (avar == 'DIR' or avar == 'FILE' or avar == 'NAME' or avar == 'SRC') and not extended:
                # shorten filenames
                if value != "/":
                    value = basename(value)
            elif avar == 'SIZE':
                value = format_size(int(value))
            replace += (value,)
        if replace:
            string = safe_string(string % replace)

        if extended and len(mapping[1]) >= 2:
            formated['EXTENDED'] = string
        else:
            formated['STRING'] = string

        user = event[1]
        if not user:
            user = "-"
        else:
            formated['LOGIN'] = user
        if 'NICK' in data:
            user += " (%s)" % safe_string(data['NICK'])
        formated['USER'] = user
        if 'RESULT' in data:
            formated['RESULT'] = data['RESULT'].lower()
        else:
            formated['RESULT'] = "-"

        formated['DATE'] = strftime("%H:%M:%S", localtime(event[0]))

        if extended:
            formated['DATE'] = strftime("%d/%m/%Y - %H:%M:%S", localtime(event[0]))
        return formated

    def get_ratio(self, login):
        upload = self.retrieve_events(0, {'user': str(login), 'type': 'UPLOAD'}, 0)
        download = self.retrieve_events(0, {'user': str(login), 'type': 'DOWNLOAD'}, 0)
        upload = self.sum_transfer_events(upload)
        download = self.sum_transfer_events(download)
        if not download and not upload:
            ratio = "NA"
        elif not upload and download:
            ratio = 0.0
        elif not download and upload:
            ratio = 1.0
        else:
            try:
                ratio = round((float(upload) / float(download)), 4)
            except ZeroDivisionError:
                ratio = "NA"
        return {'ratio': ratio, 'upload': format_size(upload), 'download': format_size(download)}

    def sum_transfer_events(self, transferlist):
        size = 0
        for aitem in transferlist:
            data = loads(aitem[3])
            if 'SIZE' in data:
                size += int(data['SIZE'])
        return size

    def get_userinfo(self, login):
        if not self.openlog():
            return 0
        values, data = ({}, 0)
        for key, aclient in self.parent.clients.items():
            if aclient.user.user == login:
                values = {'ip': aclient.user.ip, 'nick': aclient.user.nick, 'image': aclient.user.image,
                          'lastseen': 'is online'}
        data = self.retrieve_events(1, {'user': str(login), 'type': 'LOGOUT'}, 0)
        if data:
            if not 'lastseen' in values:
                values['lastseen'] = format_time(float(time()) - float(data[0][0])) + " ago."
        data = self.retrieve_events(1, {'user': str(login), 'type': 'LOGIN'}, 0)
        if data:
            if not 'lastseen' in values:
                values['lastseen'] = format_time(float(time()) - float(data[0][0])) + " ago."
            data = loads(data[0][3])
            if not 'nick' in values:
                values['nick'] = safe_string(data['NICK'])
            if not 'ip' in values:
                values['ip'] = data['IP']
        if not len(values):
            return 0
        ratio = self.get_ratio(login)
        return dict(values, **ratio)


def format_size(size):
    for x in [' bytes', ' KB', ' MB', ' GB']:
            if size < 1024.0 and size > -1024.0:
                size = "%3.1f%s" % (size, x)
                skip = 1
                break
            size /= 1024.0
    if not skip:
        size = "%3.1f%s" % (size, ' TB')
    return size


def format_time(seconds):
    days = int(seconds // (3600 * 24))
    hours = int((seconds // 3600) % 24)
    minutes = int((seconds // 60) % 60)
    seconds = int(seconds % 60)
    return "%s days, %s:%s:%s" % (days, str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2))


def safe_string(value):
    try:
        value = value.encode("utf-8")
    except UnicodeError, TypeError:
        value = unicode(value, "utf-8")
    return value
