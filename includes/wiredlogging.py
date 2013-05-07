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
        self.committimer = Timer(60, self.commit_to_db)
        self.committimer.start()

    def openlog(self):
        try:
            self.conn = connect('rewiredlog.db')  # self.config['dbFile'])  <--- Add this to config file
            self.pointer = self.conn.cursor()
            self.conn.text_factory = str
            # make sure our db exist
            self.pointer.execute('CREATE TABLE IF NOT EXISTS rewiredlog (date REAL PRIMARY KEY,user TEXT,\
                                 type TEXT, data TEXT)')
            self.conn.commit()
        except:
            return 0
        self.dbIsOpen = 1
        return 1

    def stop(self):
        if self.committimer:
            self.logger.debug("Shutting down logger")
            self.committimer.cancel()
            self.committimer.join(1)
            self.shutdown = 1
        if len(self.buffer):
            self.logger.info("Shutdown: syncing remaining changes to log")
            self.commit_to_db()
        self.logger.debug("logger thread shutdown done")
        return 1

    def closelog(self):
        if not self.dbIsOpen:
            return 0
        self.pointer.execute("VACUUM")
        self.conn.commit()
        self.conn.close()
        self.dbIsOpen = 0
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
        print event
        self.buffer.append(event)
        return 1

    def commit_to_db(self):
        if not self.openlog():
            self.logger.error('Failed to open log db')
            return 0
        self.lock.acquire()
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
        return 1
