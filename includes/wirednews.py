import time
import os
import sys


class wiredNews():
    def __init__(self, db):
        self.db = db
        self.news = []

    def loadNews(self):
        news = self.db.loadNews()
        for anews in news:
            anews = list(anews)
            anews[2] = anews[2].replace(chr(24), '\n')
            self.news.append(anews)
        return 1

    def saveNews(self, nick, date, news):
        news = news.replace('\n', chr(24))
        news = [unicode(str(nick), 'utf8'), date, unicode(news, 'utf8')]
        self.db.saveNews(news)
        self.news.append(news)
        self.reloadNews()
        return 1

    def clearNews(self):
        self.db.dropNews()
        self.reloadNews()
        return 1

    def reloadNews(self):
        self.news = []
        self.loadNews()
        return 1
