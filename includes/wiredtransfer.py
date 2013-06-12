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
        self.queuepos = 0
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


class wiredTransferQueue():
    def __init__(self, parent):
        self.parent = parent
        self.config = self.parent.config
        self.uploads = {}
        self.downloads = {}

    def queue_transfer(self, transfer):
        queue = self.downloads
        slots = self.config['downloadSlots']
        if transfer.type == "UP":
            queue = self.uploads
            slots = self.config['uploadSlots']

        with self.parent.lock:
            queuepos = len(queue)
            queue[time.time()] = transfer

        activeusertrans = len(self.get_user_transfers(transfer.userid, transfer.type, True))
        if not self.config['allowmultiple'] and activeusertrans:
            # User tries to request multiple files but server rules forbid to do so
            return len(self.get_user_transfers(transfer.userid, transfer.type)) - 1
        elif queuepos >= slots:
            active = self.get_active_count(queue)
            transfer.queuepos = queuepos - active
            return transfer.queuepos  # send queue position

        else:
            return "GO"

    def get_transfer(self, transferid):
        for queue in [self.downloads, self.uploads]:
            for akey, atransfer in queue.items():
                if atransfer.id == transferid:
                    return atransfer
        return 0

    def dequeue(self, transferid):
        removed = 0
        for key, atransfer in self.downloads.items():
            if atransfer.id == transferid:
                with self.parent.lock:
                    del(self.downloads[key])
                removed = 1

        for key, atransfer in self.uploads.items():
            if atransfer.id == transferid:
                with self.parent.lock:
                    del(self.uploads[key])
                removed = 1

        # update queue
        self.update_queue(self.uploads, self.config['uploadSlots'])
        self.update_queue(self.downloads, self.config['downloadSlots'])

        if removed:
            return 1
        return 0

    def get_active_count(self, queue):
        count = 0
        for key, atransfer in queue.items():
            if atransfer.active:
                count += 1
        return count

    def get_active_transfers(self, queue):
        active = []
        for key, atransfer in queue.items():
            if atransfer.active:
                active.append(atransfer)
        return active

    def get_user_transfers(self, userid, ttype=False, active=False):
        transfers = []
        for queue in [self.uploads, self.downloads]:
            for akey, atransfer in queue.items():
                if atransfer.userid == userid:
                    if ttype:
                        if ttype != atransfer.type:
                            continue
                    if active and not atransfer.active:
                        continue
                    transfers.append(atransfer)
        return transfers

    def update_queue(self, queue, slots):
        active, queued = (0, 0)
        for key in sorted(queue.iterkeys()):
            if queue[key].active:  # already running
                active += 1
                continue

            if active < slots:  # free slot available
                if not self.config['allowmultiple']:
                    # take care of clients trying to start multiple transfers but aren't allowed to
                    activeusertf = len(self.get_user_transfers(queue[key].userid, queue[key].type, True))
                    if activeusertf:
                        with self.parent.lock:
                            queue[key].queuepos = activeusertf - 1
                        queue[key].parent.update_transfer(queue[key], queue[key].queuepos)
                        continue
                with self.parent.lock:
                    queue[key].parent.update_transfer(queue[key], "GO")
                active += 1
                continue

            if active >= slots:  # all seats are taken
                queued += 1
                with self.parent.lock:
                    queue[key].parent.update_transfer(queue[key], queued)
                continue
        return 1

    def shutdown_active(self):
        for queue in [self.downloads, self.uploads]:
            for akey, atransfer in queue.items():
                if atransfer.active:
                    with atransfer.parent.lock:
                        try:
                            atransfer.parent.shutdown = 1
                            atransfer.parent.socket.shutdown(socket.SHUT_RDWR)
                        except Exception as e:
                            self.parent.logger.error("Shutdown transfer %s", e)

    def throttle_transferqueue(self, queue, slots, limit):
        transfers = self.get_active_transfers(queue)
        if not transfers:
            return 0
        active = len(transfers)
        speed = round((limit * 1024) / active)
        for atransfer in transfers:
            if atransfer.limit != speed:
                with self.parent.lock:
                    atransfer.limit = speed
                self.parent.logger.debug("Speed of transfer %s set to %s kbytes", atransfer.id, (atransfer.limit / 1024))
        return 1
