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
            with self.lock:
                self.news.append(anews)
        return 1

    def saveNews(self, nick, date, news):
        news = news.replace('\n', chr(24))
        news = [self._decode(nick), date, self._decode(news)]
        self.db.saveNews(news)
        with self.lock:
            self.news.append(news)
        self.reloadNews()
        return 1

    def clearNews(self):
        self.db.dropNews()
        self.reloadNews()
        return 1

    def reloadNews(self):
        with self.lock:
            self.news = []
        self.loadNews()
        return 1

    @staticmethod
    def _decode(string):
        string = str(string)
        decoded = None
        try:
            decoded = unicode(string, 'utf-8')
        except:
            decoded = unicode(string, 'utf-8', "replace")
        return decoded
