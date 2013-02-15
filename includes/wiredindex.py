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
        self.updateServerSizeIndex()
        self.queryCache = {}
        self.queryCacheLimit = 500  # max querycache items
        self.queryCacheTTL = 600  # time in seconds query cache items expire after
        self.lastindex = 0

    def run(self):
        for i in range(1, 180):  # wait some time to let the server finish startup
            if not self.keepalive:
                break
            time.sleep(1)
        while self.keepalive:
            if time.time() >= self.nextRun:
                self.indexRoot()
                self.nextRun = time.time() + self.interval
            time.sleep(1)
        self.logger.info("Exiting indexer thread")

    def indexRoot(self):
        self.logger.info("Starting index run")
        filehandler = wiredfiles.wiredFiles(self)
        self.logger.debug("Gathering filelist...")
        rootlist = filehandler.getRecursiveDirList("/")  # get filelist
        self.logger.debug("Pruning the index db...")
        self.db.pruneIndex(self.config, rootlist)  # check for deleted files and prune them from the db
        self.logger.debug("Indexing files...")
        self.db.updateIndex(rootlist)  # update indexdb
        self.updateServerSize(rootlist)  # update server info values
        self.logger.info("Finished index run: %s files totaling %s bytes.", self.files, self.size)
        self.lastindex = time.time()
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
        self.size = 0
        self.files = 0
        if not len(filelist):
                return 0  # no files in list
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
        if self.lastindex + 1800 <= time.time():
            self.logger.info("Index cache EXPIRED on %s", path)
            return 0

        if path in self.queryCache:  # check for hit in ramcache
            if self.queryCache[path]['date'] + 600 >= time.time():
                self.logger.debug("query cache HIT on %s", path)
                return self.queryCache[path]['data']  # still valid
            self.lock.acquire()
            self.queryCache.pop(path, 0)  # expired - purge it from cache
            self.lock.release()
            self.logger.debug("query cache item EXPIRED %s", path)

        # get result from index db
        self.lock.acquire()
        result = self.db.getDirListing(path)
        self.lock.release()

        if result:
            self.logger.debug("index cache HIT on %s", path)
            if not path in self.queryCache:
                self.lock.acquire()
                self.queryCache[path] = {'date': time.time(), 'data': result}
                self.lock.release()
            return result
        self.logger.debug("index cache MISS on %s", path)
        return 0

    def pruneQueryCache(self):
        self.lock.acquire()
        for key, aitem in self.queryCache.items():
            if aitem['date'] + self.queryCacheTTL <= time.time():
                self.queryCache.pop(key, 0)
                self.logger.debug("queryCache prune: %s", key)
                continue
            else:
                self.logger.debug("queryCache still valid: %s", key)

        if len(self.queryCache) > self.queryCacheLimit:
            # reduce length to queryCacheLimit
            reducerange = sorted(self.queryCache, key=lambda x: self.queryCache[x]['date'])
            for i in range(len(reducerange) - self.queryCacheLimit):
                print reducerange[i]
                self.queryCache.pop(reducerange[i], 0)

        self.lock.release()
        return 1
