import os
import sys
import shutil
import hashlib
import diskusage
import threading
import wiredfunctions
from fnmatch import fnmatch


class wiredFiles():
    def __init__(self, parent):
        self.parent = parent
        self.rootpath = self.parent.config['fileRoot']
        self.patterns = self.parent.config['excludePatterns']
        self.logger = parent.logger

    def getStat(self, target):
        targetpath = str(self.rootpath) + str(target)
        try:
            stat = os.stat(targetpath)
        except OSError:
            return 0
        hash = ""
        if os.path.isdir(targetpath):
            type = "dir"
            subdir = self.simpleDirList(targetpath)
            size = len(subdir)
        if os.path.isfile(targetpath):
            size = stat.st_size
            type = "file"
            hash = self.hashFile(targetpath)
        return {"name": target, "type": type, "hash": str(hash), "size": size,
                "modified": stat.st_mtime, "created": stat.st_ctime}

    def hashFile(self, target):
        source = open(target, "rb")
        hash = hashlib.sha1()
        hash.update(source.read(1048576))
        source.close()
        return hash.hexdigest()

    def setFolderType(self, target, type):
        target = str(self.rootpath) + str(target)

        if int(type) == 2:
            if not os.path.exists(os.path.join(target, ".wired_upload_folder")):
                touch(os.path.join(target, ".wired_upload_folder"))
                if os.path.exists(os.path.join(target, ".wired_drop_box")):
                    os.unlink(os.path.join(target, ".wired_drop_box"))
            return 1

        if int(type) == 3:
            if not os.path.exists(os.path.join(target, ".wired_drop_box")):
                touch(os.path.join(target, ".wired_drop_box"))
                if os.path.exists(os.path.join(target, ".wired_upload_folder")):
                    os.unlink(os.path.join(target, ".wired_upload_folder"))
            return 1

        if os.path.exists(os.path.join(target, ".wired_upload_folder")):
            os.unlink(os.path.join(target, ".wired_upload_folder"))
        if os.path.exists(os.path.join(target, ".wired_drop_box")):
            os.unlink(os.path.join(target, ".wired_drop_box"))
        return 1

    def getFolderType(self, dir):
        target = str(self.rootpath) + str(dir)
        if not os.path.exists(target):
            return 0
        if os.path.exists(os.path.join(target, ".wired_upload_folder")):
            return 2
        if os.path.exists(os.path.join(target, ".wired_drop_box")):
            return 3
        return 1

    def isUploadFolder(self, dir):
        try:
            target = str(self.rootpath) + str(dir)
            absparent = os.path.split(target)[0]
            relparent = os.path.split(dir)[0]
        except:
            return 0
        if not os.path.exists(absparent):
            return 0
        parenttype = self.getFolderType(relparent)
        if parenttype == 2:
            return 1
        return 0

    def isDropBox(self, dir):
        type = self.getFolderType(dir)
        if type == 3:
            return 1
        return 0

    def checkDropBoxinPath(self, path):
        try:
            if os.path.isdir(path):
                    if self.isDropBox(os.path.normpath(str(path))):
                        return 1
            data = os.path.split(path)

            while data[0] != os.sep:
                if self.isDropBox(str(data[0])):
                    return 1
                data = os.path.split(data[0])

            # check / too - just to be sure
            if self.isDropBox(os.path.normpath(str(data[0]))):
                return 1
        except:
            print "ERROR in checkDropBoxinPath"
            return 1
        return 0

    def getDirList(self, dir):
        dir = str(self.rootpath) + str(dir)
        data = []
        try:
            list = os.listdir(dir)
        except OSError:
            return 0
        for aitem in list:
            if aitem[0] == "." or self.matchPatterns(aitem):     # skip matched file/dirnames
                continue
            if os.path.isdir(os.path.join(dir, aitem)):
                stat = os.stat(os.path.join(dir, aitem))
                subdir = self.simpleDirList(os.path.join(dir, aitem))
                if subdir:
                    size = len(subdir)
                else:
                    size = 0
                data.append({"name": aitem, "type": "dir", "size": size, "modified":
                             stat.st_mtime, "created": stat.st_ctime})
            if os.path.isfile(os.path.join(dir, aitem)):
                stat = os.stat(os.path.join(dir, aitem))
                data.append({"name": aitem, "type": "file", "size": stat.st_size, "modified":
                             stat.st_mtime, "created": stat.st_ctime})
        return data

    def getRecursiveDirList(self, root):
        dir = str(self.rootpath) + str(root)
        data = []
        for (path, dirs, files) in os.walk(dir, followlinks=True):
            for adir in dirs:
                if hasattr(self.parent, 'shutdown') and hasattr(self.parent, 'nextRun'):
                    if self.parent.shutdown:
                        return 0
                if adir[0][:1] == "." or self.matchPatterns(adir):
                    continue
                name = "/" + os.path.relpath(os.path.join(path, adir), self.rootpath)
                stat = os.stat(os.path.join(path, adir))
                size = 0
                data.append({"name": name, "type": "dir", "size": size, "modified":
                             stat.st_mtime, "created": stat.st_ctime})
            for afile in files:
                if afile[0][:1] == "." or self.matchPatterns(afile):
                    continue
                name = "/" + os.path.relpath(os.path.join(path, afile), self.rootpath)
                try:
                    stat = os.stat(os.path.join(path, afile))
                except OSError:
                    print "Invalid File: " + str(os.path.join(path, afile))
                    break
                data.append({"name": name, "type": "file", "size": stat.st_size,
                             "modified": stat.st_mtime, "created": stat.st_ctime})
        return data

    def getComment(self, path):
        path = str(self.rootpath) + str(path)
        path = os.path.split(path)
        if not os.path.exists(path[0] + os.sep + "." + path[1] + "_comment"):
            return ""  # no comment for this file
        file = open(path[0] + os.sep + "." + path[1] + "_comment", 'r')
        comment = file.read()
        file.close()
        return comment

    def setComment(self, path, comment):
        path = str(self.rootpath) + str(path)
        path = os.path.split(path)
        if comment == "" and os.path.exists(path[0] + os.sep + "." + path[1] + "_comment"):
            # remove comment file for emptied comments
            os.unlink(path[0] + os.sep + "." + path[1] + "_comment")
            return 1
        # write new comment
        file = open(path[0] + os.sep + "." + path[1] + "_comment", 'w')
        if not file:
            self.logger.error("Error opening: %s/%s_comment", path[0], path[1])
            return 0
        file.write(comment)
        file.close()
        return 1

    def createFolder(self, path, type=0):
        dir = str(self.rootpath) + str(path)
        if not os.path.exists(dir):
            try:
                os.makedirs(dir)
            except:
                return 0
            if type:
                self.setFolderType(path, int(type))
            return 1
        return 0

    def delete(self, path):
        path = str(self.rootpath) + str(path)
        if not os.path.exists(path):
            return 0
        if os.path.isfile(path):
            try:
                os.unlink(path)
            except OSError:
                return 0
            return 1
        try:
            shutil.rmtree(path)
        except OSError:
            self.logger.error("Recursive delete failed on %s", path)
            return 0
        return 1

    def move(self, src, dest):
        srcpath = str(self.rootpath) + str(src)
        destpath = str(self.rootpath) + str(dest)
        print srcpath
        print destpath
        if not os.path.exists(srcpath) or os.path.exists(destpath):
            if fscase() and srcpath.upper() == destpath.upper():
                # case preserving fs and filename case change
                pass
            else:
                return 0
        try:
            shutil.move(srcpath, destpath)
        except (IOError, OSError) as e:
            self.logger.error("Move failed: %s -> %s: %s", srcpath, destpath, e)
            return 0
        if os.path.exists(srcpath) or not os.path.exists(destpath):
            if fscase() and srcpath.upper() == destpath.upper():
                return 1
            self.logger.error("Something went wrong while trying to move %s -> %s", srcpath, destpath)
            return 0
        return 1

    def uploadCheck(self, file, hash):
        path = str(self.rootpath) + str(file)
        incomplete = path + ".WiredTransfer"
        if os.path.exists(path):
            self.logger.error("%s already exists", path)
            return 521
        if os.path.exists(incomplete):
            stat = os.stat(incomplete)
            if int(stat.st_size) >= 1048576:
                filehash = self.hashFile(incomplete)
                if str(hash) != str(filehash):
                    return 522
                # file seems to be ok - return offset
                return stat.st_size
            # partial file is to small to hash it
            os.unlink(incomplete)
            return 0
        return 0

    def spaceAvail(self, root):
        path = str(self.rootpath) + str(root)
        try:
            space = diskusage.disk_usage(path)
            free = space[2]
        except:
            print "Error!"
            return 0
        return free

    def oldspaceAvail(self, root):
        path = str(self.rootpath) + str(root)
        try:
            stat = os.statvfs(path)
        except:
            return 0
        return stat.f_frsize * stat.f_bavail

    def simpleDirList(self, dir):
        filelist = []
        try:
            list = os.listdir(dir)
        except OSError:
            self.logger.error("Server failed to open %s", dir)
            return 0
        for aitem in list:
            if aitem[0] != "." and not self.matchPatterns(aitem):
                filelist.append(aitem)
        return filelist

    def matchPatterns(self, filename):
        if type(self.patterns) is not list or not len(self.patterns):
            return 0
        for apattern in self.patterns:
            if fnmatch(filename, apattern):
                return 1
        return 0


def fscase():
    if os.path.normcase('A') == os.path.normcase('a'):
        return False
    return True


def touch(fname, times=None):
    if not open(fname, 'w').close():
        return 0
    return 1


class LISTgetter(threading.Thread):
    def __init__(self, parent, user, indexer, path, datasink):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.parent = parent
        self.user = user
        self.indexer = indexer
        self.logger = self.parent.logger
        self.config = self.parent.config
        self.path = path
        self.sink = datasink

    def run(self):
        files = wiredFiles(self)
        data = ""
        if files.isDropBox(self.path) and not self.user.checkPrivs("viewDropboxes"):
            # send empty result for this dropbox
            self.logger.debug("no access to dropbox %s", self.path)
            spaceAvail = files.spaceAvail(self.path)
            self.sink('411 ' + str(self.path) + chr(28) + str(spaceAvail) + chr(4))
            self.shutdown()

        filelist = files.getDirList(self.path)
        if not type(filelist) is list:
            self.logger.error("invalid value in LIST for %s", self.path)
            self.parent.reject(520)
            self.shutdown()
        for aitem in filelist:
            dirpath = os.path.join(str(self.path), str(aitem['name']))
            ftype = 0
            if aitem['type'] == 'dir':
                ftype = files.getFolderType(dirpath)
            data += ('410 ' + wiredfunctions.normWiredPath(dirpath) + chr(28) + str(ftype) + chr(28) +
                     str(aitem['size']) + chr(28) + wiredfunctions.wiredTime(aitem['created']) +
                     chr(28) + wiredfunctions.wiredTime(aitem['modified']) + chr(4))
        spaceAvail = files.spaceAvail(self.path)
        data += ('411 ' + str(self.path) + chr(28) + str(spaceAvail) + chr(4))
        if data:
            self.sink(data)
        self.shutdown()

    def shutdown(self):
        #self.logger.debug("EXIT LISTgetter Thread")
        sys.exit()


class LISTRECURSIVEgetter(threading.Thread):
    def __init__(self, parent, user, indexer, path, datasink):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.parent = parent
        self.user = user
        self.indexer = indexer
        self.logger = self.parent.logger
        self.config = self.parent.config
        self.path = path
        self.sink = datasink

    def run(self):
        files = wiredFiles(self)
        filelist = files.getRecursiveDirList(self.path)
        data = ""
        if not type(filelist) is list:
            self.logger.error("invalid value in LISTRECURSIVEgetter for %s", self.path)
            self.parent.reject(520)
            self.shutdown()
        if len(filelist) != 0:
            for aitem in filelist:
                dirpath = os.path.join(str(self.path), str(aitem['name']))
                ftype = 0
                if aitem['type'] == 'dir':
                    ftype = files.getFolderType(dirpath)
                data += ('410 ' + wiredfunctions.normWiredPath(dirpath) + chr(28) + str(ftype) + chr(28) +
                         str(aitem['size']) + chr(28) + wiredfunctions.wiredTime(aitem['created']) +
                         chr(28) + wiredfunctions.wiredTime(aitem['modified']) + chr(4))

        spaceAvail = files.spaceAvail(self.path)
        data += ('411 ' + str(self.path) + chr(28) + str(spaceAvail) + chr(4))
        if data:
            self.sink(data)
        self.shutdown()

    def shutdown(self):
        #self.logger.debug("EXIT LISTRECURSIVEgetter Thread")
        sys.exit()
