import time
import threading
import string
import sys
import os
import wiredfunctions
import wiredfiles
import wireddb


class wiredIndex(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.name = "re:wiredIndexer"
        self.parent = parent
        self.logger = self.parent.logger
        self.shutdown = 0
        self.config = self.parent.config
        self.db = wireddb.wiredDB(self.config, self.logger)
        self.searchdb = self.parent.db  # use parents db for searching since this ones is blocked while indexing
        self.enabled = int(self.config['doIndex'])
        self.interval = int(self.config['indexInterval'])
        self.size = 0
        self.files = 0
        self.sizeChanged = 0
        self.nextRun = 0
        self.updateServerSizeIndex()

    @wiredfunctions.threading_excepthook
    def run(self):
        for i in range(1, 180):  # wait some time to let the server finish startup
            if self.shutdown:
                break
            time.sleep(1)
        while not self.shutdown:
            if time.time() >= self.nextRun:
                self.indexRoot()
                self.nextRun = time.time() + self.interval
            time.sleep(1)
        self.logger.info("Exiting indexer thread")

    def indexRoot(self):
        if not self.enabled:
            return 0
        self.logger.info("Starting index run")
        filehandler = wiredfiles.wiredFiles(self)
        self.logger.debug("Gathering filelist...")
        try:
            rootlist = filehandler.getRecursiveDirList("/")  # get filelist
        except Exception as e:
            self.logger.error("Indexer: Error while getting server filelist: %s", e)
        if self.shutdown:
            return 0
        self.logger.debug("Pruning the index db...")
        try:
            self.db.pruneIndex(self.config, rootlist)  # check for deleted files and prune them from the db
        except:
            self.logger.error("'Indexer: Error while pruning index db")
        if self.shutdown:
            return 0
        self.logger.debug("Indexing files...")
        try:
            self.db.updateIndex(rootlist)  # update indexdb
        except:
            self.logger.error("Indexer: Error while updating server size")
        try:
            self.updateServerSize(rootlist)  # update server info values
        except:
            self.logger.error("Indexer: Error while updating server size")
        self.logger.info("Finished index run: %s files totaling %s bytes.", self.files, self.size)
        return 1

    def searchIndex(self, searchString):
        try:
            dbresult = self.searchdb.searchIndex(str(searchString))
            if not dbresult:
                return []
        except:
            self.logger.error("Indexer: Error while processing search for term: %s", searchString)
            return 0
        result = []
        for aresult in dbresult:
            if str(searchString).upper() in str(os.path.basename(str(aresult[0]))).upper():

                result.append(aresult)
        return result

    def updateServerSize(self, filelist):
        lastSize = self.size
        lastFiles = self.files
        self.size = 0
        self.files = 0
        if not len(filelist):
                return 0  # no files in list
        try:
            for afile in filelist:
                if str(afile['type']).upper() == "FILE":
                    self.size += int(afile['size'])
                    self.files += 1
        except:
            self.logger.error("Indexer: Error while calculating new server size")
        if lastSize == self.size and lastFiles == self.files:
            return 0
        self.logger.debug("Server filecount or size changed!")
        self.sizeChanged = 1  # signal the cron thread to send new server info to the clients
        return 1

    def updateServerSizeIndex(self):
        lastSize = self.size
        lastFiles = self.files
        self.size = self.db.getServerSize()
        self.files = self.db.getServerFiles()
        if lastSize == self.size and lastFiles == self.files:
            return 0
        self.logger.debug("Server filecount and size loaded from index successfully!")
        self.sizeChanged = 1
        return 1
