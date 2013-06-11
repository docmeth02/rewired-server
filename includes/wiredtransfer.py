import uuid
import os
import sys
import time
import wiredfunctions
import wiredfiles
import socket
import shutil


class wiredTransfer():
    def __init__(self, parent):
        self.parent = parent
        self.logger = parent.logger
        self.config = self.parent.config
        self.time = time.time()
        self.active = 0
        self.type = None
        self.userid = 0
        self.id = None
        self.file = ""
        self.size = 0
        self.offset = 0
        self.tx = 0
        self.rx = 0
        self.txLimit = 0
        self.rxLimit = 0
        self.txRate = 0
        self.rxRate = 0
        self.checksum = ""

    def getAbsolutePath(self, file):
        return str(self.config['fileRoot']) + str(file)

    def genID(self):
        return str(uuid.uuid4())

    def doUpload(self):
        self.rx = 0
        file = str(self.getAbsolutePath(self.file))
        tempfile = file + ".WiredTransfer"
        if self.offset:
            self.logger.debug("Transfer Offset set to: %s bytes (%s)", self.offset, self.file)
            try:
                f = open(tempfile, "a+b")
            except IOError:
                self.logger.error("doUpload: failed to open requested path: %s", tempfile)
                return 0
            self.rx = int(self.offset)
        else:
            try:
                f = open(tempfile, "w+b")
            except IOError:
                self.logger.error("doUpload: failed to open requested path: %s", tempfile)
                return 0
        if self.rxLimit:
            self.throttledReceive(self.parent.socket, f)
        else:
            self.unthrottledReceive(self.parent.socket, f)
        f.close()
        stat = os.stat(tempfile)
        if int(stat.st_size) != int(self.size):
            self.logger.debug("Incomplete upload %s", self.file)
            return 0
        check = wiredfiles.wiredFiles(self)
        checksum = check.hashFile(tempfile)
        if str(checksum) != str(self.checksum):
            self.logger.error("Checksum mismatch for transfer %s", self.id)
            return 0
        shutil.move(tempfile, file)
        self.logger.info("Upload of file %s finished successfully", self.file)
        return 1

    def doDownload(self):
        file = str(self.getAbsolutePath(self.file))
        if not os.path.exists(file):
            #file not found
            return 0
        stat = os.stat(file)
        self.size = int(stat.st_size)
        try:
            f = open(file, "rb")
        except IOError:
            self.logger.error("doDownload: failed to open requested file: %s", file)
            return 0

        if self.offset:
            self.logger.debug("Transfer Offset set to: %s bytes (%s)", self.offset, self.file)
            f.seek(int(self.offset), 0)
            self.tx += int(self.offset)
        if self.txLimit:
            self.throttledSend(f, self.parent.socket)
        else:
            self.unthrottledSend(f, self.parent.socket)
        f.close()
        return 1

    def throttledReceive(self, input, output):
        interval = 1.0
        max_speed = self.rxLimit
        data_count = 0
        time_next = time.time() + interval
        sleep_for = 0
        while 1:
            try:
                buf = ""
                buf = input.read(512)  # smaller chunks = smoother, more accurate
                if len(buf) == 0:
                    break
                data_count += len(buf)
                if data_count >= max_speed * interval:
                    self.rx += int(data_count)
                    lastrx = data_count
                    data_count = 0
                    sleep_for = time_next - time.time()
                    if sleep_for < 0:
                        sleep_for = 0
                if sleep_for:
                    time.sleep(sleep_for)
                    time_next = time.time() + interval
                    sleep_for = 0
                    self.rxRate = lastrx
                output.write(buf)
            except:
                return 0
        return 1

    def unthrottledReceive(self, input, output):
        next = time.time() + 1
        bytes = 0
        byte = None
        try:
            while byte != "":
                byte = input.read(1500)
                if byte != "":
                    output.write(byte)
                    bytes += len(byte)
                    self.rx += int(len(byte))
                if time.time() >= next:
                    self.rxRate = bytes
                    bytes = 0
                    next = time.time() + 1
        except:
            return 0
        return 1

    def unthrottledSend(self, input, output):
        next = time.time() + 1
        bytes = 0
        byte = None
        try:
            while byte != "":
                byte = input.read(1500)
                if byte != "":
                    output.send(byte)
                    bytes += len(byte)
                    self.tx += int(len(byte))
                if time.time() >= next:
                    self.txRate = bytes
                    bytes = 0
                    next = time.time() + 1
        except:
            return 0
        return 1

    def throttledSend(self, input, output):
        interval = 1.0
        max_speed = self.txLimit
        data_count = 0
        time_next = time.time() + interval
        sleep_for = 0
        while 1:
            try:
                buf = input.read(512)  # smaller chunks = smoother, more accurate
                if len(buf) == 0:
                    break
                data_count += len(buf)
                if data_count >= max_speed * interval:
                    self.tx += int(data_count)
                    lasttx = data_count
                    data_count = 0
                    sleep_for = time_next - time.time()
                    if sleep_for < 0:
                        sleep_for = 0
                if sleep_for:
                    time.sleep(sleep_for)
                    time_next = time.time() + interval
                    sleep_for = 0
                    self.txRate = lasttx
                output.write(buf)
            except:
                return 0
        return 1

    def startTransfer(self, data):
        data = (str(data).strip())
        if data.count(chr(4)) == 0:
            return 0
        split = wiredfunctions.tsplit(data, chr(4))
        for data in split:
            if not data:
                break
            data = data.replace(chr(4), '')
            command = data
            parameters = {}
            if data.count(' ') != 0:
                end = data.index(' ')
                parameters = data[end + 1:]
                command = data[:end]
                parameters = wiredfunctions.tsplit(parameters, chr(28))

            if not command == "TRANSFER":
                self.logger.error("Received invalid command %s on transfer socket", command)
                return 0
            self.logger.error("%s requested transfer id %s", self.parent.ip, parameters[0])
            self.id = str(parameters[0])
            return 1
