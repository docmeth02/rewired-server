from sqlite3 import connect, Error
from threading import Timer, Lock
from json import loads, dumps
from time import time
from json import loads
from os.path import basename
from time import strftime, localtime


class wiredlog():
    def __init__(self, parent):
        self.parent = parent
        self.lock = Lock()
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
        try:
            self.conn = connect(self.config['logdbFile'])
            self.pointer = self.conn.cursor()
            self.conn.text_factory = str
            # make sure our db exist
            self.pointer.execute('CREATE TABLE IF NOT EXISTS rewiredlog (date REAL PRIMARY KEY,user TEXT,\
                                 type TEXT, data TEXT)')
            self.conn.commit()
        except:
            self.logger.error("Failed to open logging db")
            return 0
        self.dbIsOpen = 1
        return 1

    def stop(self):
        if self.committimer:
            self.logger.debug("Logger: shutting down logger")
            self.committimer.cancel()
            self.committimer.join(1)
            self.shutdown = 1
        if len(self.buffer):
            self.logger.info("Logger: syncing remaining events to log")
            self.commit_to_db()
        self.vacuum()
        self.logger.debug("Logger: shutdown done")
        return 1

    def closelog(self):
        if not self.dbIsOpen:
            return 0
        self.conn.close()
        self.dbIsOpen = 0
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
        event['DATA'] = dumps(data)
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

    def commit_to_db(self):
        if not self.openlog():
            return 0
        if not len(self.buffer):
            self.committimer = Timer(60, self.commit_to_db)
            self.committimer.start()
            return 1
        self.lock.acquire()
        buffer = len(self.buffer)
        for aevent in self.buffer:
            self.pointer.execute("INSERT INTO rewiredlog VALUES (?, ?, ?, ?);", [aevent['TIME'], aevent['USER'],
                                                                                 aevent['TYPE'], aevent['DATA']])
        self.conn.commit()
        self.buffer = []
        self.lock.release()
        self.closelog()
        if not self.shutdown:
            self.committimer = Timer(60, self.commit_to_db)
            self.committimer.start()
        if self.debug:
            self.logger.debug("Logger: commited %s out of %s events to db", buffer - len(self.buffer), buffer)
        if type(self.eventcount) is int:
            self.eventcount += (buffer - len(self.buffer))
        return 1

    def format_event(self, event, extended=False):
        formated = {}
        eventMap = {
            'LOGIN': ["Login (%s)", ['IP']],
            'LOGOUT': ["Disconnected", []],
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
            string = string % replace

        if extended and len(mapping[1]) >= 2:
            formated['EXTENDED'] = string
        else:
            formated['STRING'] = string

        user = event[1]
        if 'NICK' in data:
            user += " (%s)" % data['NICK']
        formated['USER'] = user
        if 'RESULT' in data:
            formated['RESULT'] = data['RESULT'].lower()

        formated['DATE'] = strftime("%H:%M:%S", localtime(event[0]))

        if extended:
            formated['DATE'] = strftime("%d/%m/%Y - %H:%M:%S", localtime(event[0]))
        return formated


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
