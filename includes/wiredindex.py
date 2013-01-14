import time
import threading
import string
import sys
import os
import wiredfunctions
import wiredfiles


class wiredIndex(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.parent = parent
        self.logger = self.parent.logger
        self.keepalive = 1
        self.config = self.parent.config
        self.db = self.parent.db
        self.enabled = int(self.config['doIndex'])
        self.interval = int(self.config['indexInterval'])
        self.size = 0
        self.files = 0
        self.sizeChanged = 0
        self.nextRun = 0

    def run(self):
        time.sleep(5)  # wait some time to let the server finish startup
        self.updateServerSizeIndex()
        while self.keepalive:
            if time.time() >= self.nextRun:
                self.indexRoot()
                self.nextRun = time.time() + self.interval
            time.sleep(1)
        self.logger.info("Exiting indexer thread")

    def indexRoot(self):
        self.logger.info("Starting index run")
        filehandler = wiredfiles.wiredFiles(self)
        rootlist = filehandler.getRecursiveDirList("/")  # get filelist
        self.db.updateIndex(rootlist)  # update indexdb
        self.db.pruneIndex(self.config)  # check for deleted files and prune them from the db
        self.updateServerSize(rootlist)  # update server info values
        self.logger.info("Finished index run: %s files totaling %s bytes.", self.files, self.size)
        return 1

    def searchIndex(self, searchString):
        dbresult = self.db.searchIndex(searchString)
        result = []
        for aresult in dbresult:
            if str(searchString).upper() in str(os.path.basename(str(aresult[0]))).upper():

                result.append(aresult)
        return result

    def updateServerSize(self, filelist):
        lastSize = self.size
        lastFiles = self.files
        if not len(filelist):
            return 0  # no files in list
        self.size = 0
        self.files = 0
        for afile in filelist:
            if str(afile['type']).upper() == "FILE":
                self.size += int(afile['size'])
                self.files += 1
        if lastSize == self.size and lastFiles == self.files:
            return 0
        self.logger.debug("Server filecount or size changed!")
        self.sizeChanged = 1  # signal the cron thread to send new server info to the clients
        return 1

    def updateServerSizeIndex(self):
        self.size = self.db.getServerSize()
        self.files = self.db.getServerFiles()
        return 1
