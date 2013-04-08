import threading
import wiredfunctions
import wireduser
import wiredtransfer
from socket import error as SOCKETERROR
from socket import SHUT_RDWR
from time import sleep


class transferServer(threading.Thread):
    def __init__(self, parent, (socket, address)):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.parent = parent
        self.socket = socket
        self.socket.settimeout(10)
        self.logger = self.parent.logger
        self.shutdown = 0
        self.transfer = None
        self.transferDone = 0
        self.doTransfer = 0
        self.config = self.parent.config
        if address[0][:7] == "::ffff:":
            self.ip = address[0][7:]
        else:
            self.ip = address[0]

    def run(self):
        self.logger.info("Incoming connection on transfer port form %s", self.ip)
        self.transfer = wiredtransfer.wiredTransfer(self)
        while not self.shutdown or not self.transferDone:
                data = ""
                char = 0
                while char != chr(4) and not self.shutdown or self.transferDone:
                    char = 0
                    try:
                        char = self.socket.recv(1)
                    except ssl.SSLError:
                        pass
                    except socket.error:
                        self.logger.debug("Caught socket.error")
                        self.shutdown = 1
                        break

                    if char:
                        data += char
                    if char == '':  # a disconnected socket returns an empty string on read
                        self.shutdown = 1

                if not self.shutdown:
                    if not self.process(data):
                        self.shutdown = 1
                        self.shutdownSocket()
                        raise SystemExit
                sleep(0.25)
        self.shutdownSocket()

    def process(self, data):
        if not self.doTransfer:
            if not self.transfer.startTransfer(data):
                #failed to parse command
                self.shutdown = 1
                self.logger.error("Got invalid command on transfer port from %s", self.ip)
                self.shutdownSocket()

            try:
                self.transfer = self.parent.transferqueue[self.transfer.id]
                self.transfer.active = 1
                self.transfer.parent = self
            except KeyError:
                # probably send error here - not a valid transfer id
                self.logger.error("Invalid transfer id %s from %s", self.transfer.id, self.ip)
                self.shutdown = 1
                self.shutdownSocket()

            self.logger.debug("Found transfer id %s for %s", self.transfer.id, self.ip)
            self.doTransfer = 1
            try:
                if self.transfer.type == "DOWN":
                    if not self.transfer.doDownload():
                        self.logger.error("Download %s to client %s failed.", self.transfer.id, self.ip)
                    else:
                        self.logger.info("Download %s for client %s finished successfully", self.transfer.id, self.ip)
            except:
                self.logger.debug("Transfer debug MARK1")
                self.shutdownSocket()

            try:
                if self.transfer.type == "UP":
                    if not self.transfer.doUpload():
                        self.logger.error("Upload %s from client %s failed.", self.transfer.id, self.ip)
                    else:
                        self.logger.info("Upload %s for client %s finished successfully", self.transfer.id, self.ip)
            except:
                self.logger.debug("Transfer debug MARK2")
                self.shutdownSocket()

    def shutdownSocket(self):
        try:
            self.lock.acquire(True)
            self.parent.transferqueue.pop(self.transfer.id, None)
            self.lock.release()
            self.shutdown = 1
            self.transferDone = 1
            self.logger.debug("Exit transfer thread")
        except:
            self.logger.error("Failed to remove transfer %s from queue", self.transfer.id)
            pass
        try:
            self.socket.shutdown(SHUT_RDWR)
            self.socket.close()
        except SOCKETERROR:
            self.logger.info("Transfer client %s dropped connection", self.ip)
            raise SystemExit
        self.logger.info("Transfer client %s disconnected", self.ip)
        raise SystemExit
