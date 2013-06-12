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
        self.bytesdone = 0
        self.limit = 0
        self.rate = 0
        self.checksum = ""

    def getAbsolutePath(self, file):
        return str(self.config['fileRoot']) + os.sep + str(file)

    def genID(self):
        return str(uuid.uuid4())

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

    def doUpload(self):
        file = self.getAbsolutePath(self.file)
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
        if not self.process(self.parent.socket, f):
            f.close()
            return 0
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
            self.bytesdone = int(self.offset)
        if self.process(f, self.parent.socket):
            f.close()
            return 1
        f.close()
        return 0

    def process(self, input, output):
        interval, data_count, lastbytes, sleep_for = (1.0, 0, 0, 0)
        time_next = time.time() + interval
        while not self.parent.shutdown:
            buf = ""
            try:
                buf = input.read(512)  # smaller chunks = smoother, more accurate
            except:
                break
            if not buf:  # empty string means dead socket or eof
                break
            data_count += len(buf)
            if self.limit and data_count >= self.limit * interval:
                lastbytes = data_count
                data_count = 0
                sleep_for = time_next - time.time()
                if sleep_for < 0:
                    sleep_for = 0
            elif not self.limit and time.time() >= time_next:
                self.rate = int(data_count)
                data_count = 0
                time_next = time.time() + interval

            if sleep_for > 0 and self.limit:
                time.sleep(sleep_for)
                time_next = time.time() + interval
                sleep_for = 0
                self.rate = lastbytes
            elif self.limit and time.time() > time_next:
                lastbytes = data_count
                data_count = 0
                self.rate = lastbytes
                time_next = time.time() + interval
            try:
                output.write(buf)
            except:
                break

            self.bytesdone += len(buf)

        if self.size == self.bytesdone:
            return 1
        return 0
