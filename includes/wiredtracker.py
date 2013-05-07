import time
import socket
import threading
import ssl
import sys
import wireduser
try:
    from M2Crypto import X509, RSA
except:
    print "Failed to load required module. Please install python M2crypto."
    raise SystemExit


class wiredTracker(threading.Thread):
    def __init__(self, parent, trackerurl):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.parent = parent
        self.keepalive = 1
        self.indexer = self.parent.indexer
        self.logger = self.parent.logger
        self.clients = self.parent.clients
        self.config = self.parent.config
        self.db = self.parent.db
        self.tcpsock = None
        self.tlssock = None
        self.udpsock = None
        self.tracker = trackerurl
        self.name = self.tracker
        self.servername = None
        self.desc = None
        self.category = self.config['trackerCategory']
        self.uri = "wired://" + str(self.config['host']) + ":" + str(self.config['port']) + "/"
        if self.config['trackerDNS']:
            self.uri = "wired://" + str(self.config['trackerDNS']) + ":" + str(self.config['port']) + "/"
        self.files = 0
        self.size = 0
        self.download = 0
        self.guest = 0
        self.onlineUsers = 0
        self.bandwidth = self.config['trackerBandwidth']
        self.port = 2002
        self.registered = 0
        self.connected = 0
        self.cert = None
        self.hash = None
        self.nextUpdate = 0
        self.regrefresh = time.time() + 3600  # Refresh registration every 60 minutes
        self.retry = 10

    def run(self):
        if not self.config['trackerRegister']:
            self.logger.info("Tracker disabled in config file.")
            return 1
        self.checkPrivs()
        self.updateInfo()
        while not self.registered and self.keepalive:
            self.connectTCPSocket()
            if not self.register():
                self.logger.error("Error while registering with tracker %s", self.tracker)
                for num in range(1, self.retry):
                    if not self.keepalive:
                        break
                    self.retry += 1
                    time.sleep(1)
            else:
                time.sleep(1)
        self.disconnectTCPSocket()

        while self.keepalive:
            if time.time() >= self.nextUpdate:
                self.updateInfo()
                self.updateTracker()
                self.nextUpdate = time.time() + 60

            if time.time() >= self.regrefresh:
                self.logger.debug("Refreshing tracker registration")
                self.updateRegistration()
                self.regrefresh = time.time() + 3600  # 60 minutes
                self.nextUpdate = time.time() + 60
                self.logger.debug("Refresh successful!")

            time.sleep(1)
        self.logger.debug("Tracker %s stopped", self.tracker)

    def checkPrivs(self):
        self.parent.lock.acquire()
        users = self.db.loadUsers()
        for auser in users:
            if auser[0] == "guest":
                guest = wireduser.wiredPrivs(self)
                guest.stringToPrivs(auser[4])
                self.download = int(guest.download)
                self.guest = 1
        self.parent.lock.release()
        return 1

    def updateInfo(self):
        self.onlineUsers = len(self.clients)
        self.servername = self.config['serverName']
        self.desc = self.config['serverDesc']
        self.files = self.indexer.files
        self.size = self.indexer.size
        return 1

    def register(self):
        if not self.connected:
            self.logger.error("Register: Not connected!")
            return 0
        try:
            self.tlssock.write("HELLO" + chr(4))
            response = self.tlssock.recv(4096)
            if int(response[:3]) != 200:
                self.logger.error("Invalid response to HELLO command from tracker %s", self.tracker)
                return 0
            if not self.keepalive:
                return 0
            self.logger.debug("Connected to tracker %s", self.tracker)
            self.tlssock.write("REGISTER " + str(self.category) + chr(28) + str(self.uri) + chr(28) + str(self.servername)\
                               + chr(28) + str(self.bandwidth) + chr(28) + str(self.desc) + chr(4))
            response = self.tlssock.recv(8096)
            if int(response[:3]) != 700:
                self.logger.error("Error registering to tracker %s", self.tracker)
                return 0
            response = response.replace(chr(4), '')
            self.hash = response[4:]

        except:
            self.logger.error("Unkown error while registering to tracker %s", self.tracker)
            return 0
        self.registered = 1
        self.logger.info("Successfully registered with tracker %s", self.tracker)
        return 1

    def updateRegistration(self):
        self.connectTCPSocket()
        if not self.connected:
            self.logger.error("updateRegistration: no connection to tracker %s", self.tracker)
            return 0
        self.register()
        self.disconnectTCPSocket()
        return 1

    def connectTCPSocket(self):
        try:
            self.tcpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcpsock.connect((self.tracker, self.port))
            self.tlssock = ssl.wrap_socket(self.tcpsock, server_side=False, ssl_version=ssl.PROTOCOL_TLSv1)
            self.cert = self.tlssock.getpeercert(binary_form=True)
        except:
            return 0
        self.connected = 1
        return 1

    def updateTracker(self):
        if not self.cert:
            self.logger.error("updateTracker: No certificate found!")
            return 0
        self.udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = "UPDATE " + str(self.hash) + chr(28) + str(self.onlineUsers) + chr(28) + str(self.guest) + chr(28) +\
        str(self.download) + chr(28) + str(self.files) + chr(28) + str(self.size) + chr(4)
        try:
            cert = ""
            cert = X509.load_cert_string(self.cert, X509.FORMAT_DER)  # parse the cert

        except X509.X509Error:
            self.logger.error("Error in X509.load_cert. cert: %s pem: %s", repr(cert), repr(self.cert))
            return 0
        pub_key = cert.get_pubkey()
        rsa_key = pub_key.get_rsa()
        msg = rsa_key.public_encrypt(msg, RSA.pkcs1_oaep_padding)
        if not self.udpsock.sendto(msg, (self.tracker, self.port)):
            self.logger.error("Error sending update packet to tracker %s", self.tracker)
            return 0
        self.logger.debug("Updated tracker %s", self.tracker)
        self.udpsock = None
        return 1

    def disconnectTCPSocket(self):
        if not self.connected:
            return 0
        self.connected = 0
        self.tcpsock.shutdown(socket.SHUT_RDWR)
        self.tcpsock.close()
        self.tcpsock = None
        return 1
