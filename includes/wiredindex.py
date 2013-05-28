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
        self.queryCache = {}
        self.queryCacheLimit = 1000  # max querycache items
        self.queryCacheTTL = 600  # time in seconds query cache items expire after
        self.lastindex = 0

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
        self.lastindex = time.time()
        return 1

    def searchIndex(self, searchString):
        try:
            dbresult = self.searchdb.searchIndex(str(searchString))
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

    def getCachedDirList(self, path):
        # this needs to be threadsafe as all clients can access it concurrently
        if path in self.queryCache:  # check for hit in ramcache
            if self.queryCache[path]['date'] + 600 >= time.time():
                self.logger.debug("query cache HIT on %s", path)
                return self.queryCache[path]['data']  # still valid

            self.lock.acquire()
            self.queryCache.pop(path, 0)  # expired - purge it from cache
            self.lock.release()
            self.logger.debug("query cache item EXPIRED %s", path)

        if self.config['cachemode'].lower() != "index":
            self.logger.debug("query cache MISS on %s", path)
            return 0

        # get result from index db
        if self.lastindex + 1800 <= time.time():
            self.logger.debug("Index cache EXPIRED on %s", path)
            return 0

        self.lock.acquire()
        result = self.db.getDirListing(path)
        self.lock.release()

        if result:
            self.logger.debug("index cache HIT on %s", path)
            if not path in self.queryCache:  # add the result to ramcache
                self.addQueryCache(path, result)
            return result
        self.logger.debug("index cache MISS on %s", path)
        return 0

    def addQueryCache(self, path, result):
        self.lock.acquire()
        self.queryCache[path] = {'date': time.time(), 'data': result}
        self.lock.release()
        return 1

    def pruneQueryCache(self):
        self.lock.acquire()
        length = len(self.queryCache)
        for key, aitem in self.queryCache.items():
            if aitem['date'] + self.queryCacheTTL <= time.time():
                self.queryCache.pop(key, 0)
                continue

        if len(self.queryCache) > self.queryCacheLimit:
            # reduce length to queryCacheLimit
            reducerange = sorted(self.queryCache, key=lambda x: self.queryCache[x]['date'])
            for i in range(len(reducerange) - self.queryCacheLimit):
                self.queryCache.pop(reducerange[i], 0)

        self.lock.release()
        if int(length) - len(self.queryCache):
            self.logger.debug("pruneQueryCache: Removed %s expired items", (int(length) - len(self.queryCache)))
        return 1
