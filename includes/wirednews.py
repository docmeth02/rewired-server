import time
import os
import sys
from threading import RLock

class wiredNews():
    def __init__(self, db):
        self.lock = RLock()
        self.db = db
        self.news = []

    def loadNews(self):
        news = self.db.loadNews()
        for anews in news:
            anews = list(anews)
            anews[2] = anews[2].replace(chr(24), '\n')
            self.lock.acquire()
            self.news.append(anews)
            self.lock.release()
        return 1

    def saveNews(self, nick, date, news):
        news = news.replace('\n', chr(24))
        news = [unicode(str(nick), 'utf8'), date, unicode(news, 'utf8')]
        self.db.saveNews(news)
        self.lock.acquire()
        self.news.append(news)
        self.lock.release()
        self.reloadNews()
        return 1

    def clearNews(self):
        self.db.dropNews()
        self.reloadNews()
        return 1

    def reloadNews(self):
        self.lock.acquire()
        self.news = []
        self.lock.release()
        self.loadNews()
        return 1
