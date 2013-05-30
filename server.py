#!/usr/bin/python
# -*- coding: UTF-8 -*-
import sys
from logging import getLogger
from includes import rewiredserver, wiredfunctions

sys.excepthook = wiredfunctions.handleException
daemonize = 0
config = None
if wiredfunctions.checkArgv(sys.argv) == "--DAEMON":
    daemonize = 1
server = rewiredserver.reWiredServer(daemonize, config, False)
server.initialize()
server.main()
