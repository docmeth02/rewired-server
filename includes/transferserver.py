import threading
import wiredfunctions
import wireduser
import wiredtransfer
from ssl import SSLError, wrap_socket, PROTOCOL_TLSv1
from socket import error as SOCKETERROR
from socket import SHUT_RDWR


class transferServer(threading.Thread):
    def __init__(self, parent, (socket, address)):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.parent = parent
        self.wiredlog = self.parent.wiredlog
        self.client = None
        self.connection = socket
        self.config = self.parent.config
        self.socket = wrap_socket(self.connection, server_side=True, certfile=str(self.config['cert']), keyfile=str(
            self.config['cert']), ssl_version=PROTOCOL_TLSv1)
        self.logger = self.parent.logger
        self.shutdown = 0
        self.transferDone = 0
        self.doTransfer = 0
        if address[0][:7] == "::ffff:":
            self.ip = address[0][7:]
        else:
            self.ip = address[0]

    def run(self):
        self.logger.info("Incoming connection on transfer port form %s", self.ip)
        transfer = wiredtransfer.wiredTransfer(self)
        self.socket.settimeout(30)
        while not self.shutdown or not self.transferDone:
            data = self.socket.recv(8192)
            if not self.doTransfer:
                if not transfer.startTransfer(data):
                    #failed to parse command
                    self.shutdown = 1
                    self.logger.error("Got invalid command on transfer port from %s", self.ip)
                    break
                transfer = self.parent.transferqueue.get_transfer(transfer.id)
                if not transfer:
                    # probably send error here - not a valid transfer id
                    self.logger.error("Invalid transfer id %s from %s", transfer.id, self.ip)
                    self.shutdown = 1
                    break
                self.logger.debug("Found transfer id %s for %s", transfer.id, self.ip)
                with self.parent.lock:
                    try:
                        self.client = self.parent.clients[int(transfer.userid)]
                    except KeyError:
                        self.logger.error("got transfer for invalid user id %s", transfer.userid)
                        self.shutdown = 1
                        break
                with self.lock:
                    transfer.active = 1
                    transfer.parent = self
                    self.doTransfer = 1
                if transfer.type == "DOWN":
                    if self.config["downlimit"]:
                        self.parent.transferqueue.throttle_transferqueue(self.parent.transferqueue.uploads,
                                                                         self.config["downloadSlots"], self.config["downlimit"])
                    if not transfer.doDownload():
                        self.logger.error("Download %s to client %s failed.", transfer.id, self.ip)
                        self.wiredlog.log_event('DOWNLOAD', {'RESULT': 'ABORTED', 'USER': self.client.user.user,
                                                             'NICK': self.client.user.nick, 'FILE': transfer.file,
                                                             'SIZE': transfer.bytesdone})
                    else:
                        self.logger.info("Download %s for client %s finished successfully", transfer.id, self.ip)
                        self.wiredlog.log_event('DOWNLOAD', {'RESULT': 'COMPLETE', 'USER': self.client.user.user,
                                                             'NICK': self.client.user.nick, 'FILE': transfer.file,
                                                             'SIZE': transfer.bytesdone})
                if transfer.type == "UP":
                    if self.config["uplimit"]:
                        self.parent.transferqueue.throttle_transferqueue(self.parent.transferqueue.uploads,
                                                                         self.config["uploadSlots"], self.config["uplimit"])
                    if not transfer.doUpload():
                        self.logger.error("Upload %s from client %s interrupted.", transfer.id, self.ip)
                        self.wiredlog.log_event('UPLOAD', {'RESULT': 'ABORTED', 'USER': self.client.user.user,
                                                           'NICK': self.client.user.nick, 'FILE': transfer.file,
                                                           'SIZE': transfer.bytesdone})
                    else:
                        self.logger.info("Upload %s for client %s finished successfully", transfer.id, self.ip)
                        self.wiredlog.log_event('UPLOAD', {'RESULT': 'COMPLETE', 'USER': self.client.user.user,
                                                           'NICK': self.client.user.nick, 'FILE': transfer.file,
                                                           'SIZE': transfer.bytesdone})
                with self.lock:
                    if not self.parent.transferqueue.dequeue(transfer.id):
                        self.logger.error("Failed to remove transfer %s from queue", transfer.id)
                    del(transfer)
                self.shutdown = 1
                self.transferDone = 1
                if self.config["downlimit"]:
                    self.parent.transferqueue.throttle_transferqueue(self.parent.transferqueue.uploads,
                                                                         self.config["downloadSlots"], self.config["downlimit"])
                if self.config["uplimit"]:
                    self.parent.transferqueue.throttle_transferqueue(self.parent.transferqueue.uploads,
                                                                         self.config["uploadSlots"], self.config["uplimit"])
                self.logger.debug("Exit tranfer thread")
                break
            if not data:
                self.logger.error("Timeout wating for data on transfer port")
                self.shutdown = 1
                break
        try:
            self.socket.shutdown(SHUT_RDWR)
            self.socket.close()
        except SOCKETERROR:
            self.logger.info("Transfer client %s dropped connection", self.ip)

        with self.parent.lock:
            self.parent.totaltransfers += 1
        self.logger.info("Transfer client %s disconnected", self.ip)
        raise SystemExit
