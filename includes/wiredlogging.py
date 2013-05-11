from sqlite3 import connect
from threading import Timer, Lock
from json import loads, dumps
from time import time


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

    def commit_to_db(self):
        if not self.openlog():
            self.logger.error('Failed to open log db')
            return 0
        if not len(self.buffer):
            return 1
        self.lock.acquire()
        buffer = len(self.buffer)
        for aevent in self.buffer:
            self.pointer.execute("INSERT INTO rewiredlog VALUES (?, ?, ?, ?);", [aevent['TIME'], aevent['USER'],\
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
        return 1
