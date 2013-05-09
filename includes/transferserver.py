import threading
import wiredfunctions
import wireduser
import wiredtransfer
from socket import error as SOCKETERROR
from socket import SHUT_RDWR


class transferServer(threading.Thread):
    def __init__(self, parent, (socket, address)):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.parent = parent
        self.socket = socket
        self.logger = self.parent.logger
        self.shutdown = 0
        self.transferDone = 0
        self.doTransfer = 0
        self.config = self.parent.config
        if address[0][:7] == "::ffff:":
            self.ip = address[0][7:]
        else:
            self.ip = address[0]

    def run(self):
        self.logger.info("Incoming connection on transfer port form %s", self.ip)
        transfer = wiredtransfer.wiredTransfer(self)
        while not self.shutdown or not self.transferDone:
            data = self.socket.recv(8192)
            if not self.doTransfer:
                if not transfer.startTransfer(data):
                    #failed to parse command
                    self.shutdown = 1
                    self.logger.error("Got invalid command on transfer port from %s", self.ip)
                    break
                try:
                    transfer = self.parent.transferqueue[transfer.id]
                    transfer.active = 1
                    transfer.parent = self
                except KeyError:
                    # probably send error here - not a valid transfer id
                    self.logger.error("Invalid transfer id %s from %s", transfer.id, self.ip)
                    self.shutdown = 1
                    break
                self.logger.debug("Found transfer id %s for %s", transfer.id, self.ip)
                self.doTransfer = 1
                if transfer.type == "DOWN":
                    if not transfer.doDownload():
                        self.logger.error("Download %s to client %s failed.", transfer.id, self.ip)
                    else:
                        self.logger.info("Download %s for client %s finished successfully", transfer.id, self.ip)
                if transfer.type == "UP":
                    if not transfer.doUpload():
                        self.logger.error("Upload %s from client %s interrupted.", transfer.id, self.ip)
                    else:
                        self.logger.info("Upload %s for client %s finished successfully", transfer.id, self.ip)
                self.lock.acquire(True)
                self.parent.transferqueue.pop(transfer.id, None)
                self.parent.totaltransfers += 1
                self.lock.release()
                self.shutdown = 1
                self.transferDone = 1
                self.logger.debug("Exit tranfer thread")
                break
            if not data:
                self.shutdown = 1
                break
        try:
            self.socket.shutdown(SHUT_RDWR)
            self.socket.close()
        except SOCKETERROR:
            self.logger.info("Transfer client %s dropped connection", self.ip)

        self.logger.info("Transfer client %s disconnected", self.ip)
