from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from ssl import wrap_socket, SSLError
from base64 import b64encode, b64decode
from urlparse import urlparse, parse_qs
from mimetypes import guess_type
from time import sleep, time
from hashlib import sha1
import markup
import select
import threading
import os


class rewiredWebHandler:
    def __init__(self, rewiredserver, config):
        self.rewiredserver = rewiredserver
        self.logger = self.rewiredserver.logger
        self.config = config
        self.webroot = 'webroot/'

    def __call__(self, request, client_address, server):
        requesthandler = rewiredRequestHandler(request, client_address, server, self, self.webroot, self.config)
        return requesthandler

    def checkLogin(self, user, passw):
        hash = sha1()
        hash.update(str(passw))
        if self.rewiredserver.users.checkLogin(user, hash.hexdigest().lower(), True):
            return 1
        return 0

    def check_indexer(self):
        if not self.config['doIndex']:
            return 0
        if not self.rewiredserver.indexer.isAlive():
            return 'crashed'
        return "ok"

    def check_tracker(self):
        if not self.config['trackerRegister']:
            return 0
        count = 0
        for key, atracker in enumerate(self.rewiredserver.tracker):
            if not atracker.isAlive():
                return "crashed"
            count += 1
        return count

    def get_platform(self):
        from includes import wiredfunctions
        return wiredfunctions.getPlatform()

    def get_active_users(self):
        return len(self.rewiredserver.clients)

    def get_active_transfers(self):
        up = 0
        down = 0
        for akey, aitem in self.rewiredserver.transferqueue.items():
            if aitem.type == "UP":
                up += 1
            else:
                down += 1
        return {'up': up, 'down': down}

    def get_total_users(self):
        return self.rewiredserver.globalUserID

    def get_server_size(self):
        size, skip = (self.rewiredserver.indexer.size, 0)
        for x in [' bytes', ' KB', ' MB', ' GB']:
            if size < 1024.0 and size > -1024.0:
                size = "%3.1f%s" % (size, x)
                skip = 1
                break
            size /= 1024.0
        if not skip:
            size = "%3.1f%s" % (size, ' TB')

        return {'Files': self.rewiredserver.indexer.files,
                'Size': size}

    def get_server_uptime(self):
        seconds = time() - self.config['serverStarted']
        days = int(seconds // (3600 * 24))
        hours = int((seconds // 3600) % 24)
        minutes = int((seconds // 60) % 60)
        seconds = int(seconds % 60)
        return "%s days, %s:%s:%s" % (days, str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2))

    def get_total_transfers(self):
        return self.rewiredserver.totaltransfers


class rewiredRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server, parent, webroot, config):
        self.parent = parent
        self.logger = self.parent.logger
        self.webroot = webroot
        self.config = config
        self.user = 0
        self.passw = 0

        self.query = 0
        self.path = 0

        self.mimetype = ('text/html', None)
        try:
            BaseHTTPRequestHandler.__init__(self, request, client_address, server)
        except SSLError as e:
            self.logger.error("rewiredRequestHandler: %s", e)

    def defaultHeaders(self, cache=True):
        self.send_response(200)
        self.send_header("Content-type", self.mimetype[0])
        if cache:
            self.send_header('Cache-Control', 'max-age=3600, must-revalidate')
        self.end_headers()

    def authHeaders(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"%s https auth\"' % self.config['serverName'])
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def sendError(self, code):
        self.send_response(code)
        if code == 401:
            self.send_error(401, 'Unauthorized')
        elif code == 404:
            self.send_error(404, 'File Not Found: %s ' % self.path)
        elif code == 500:
            self.send_error(500, 'Internal Server Error')

    def do_Redirect(self, to):
        self.send_response(301)
        self.send_header('Location', str(to))
        self.end_headers()

    def do_GET(self):
        if self.headers.getheader('Authorization') is None:
            self.authHeaders()
            self.sendError(401)
            return

        elif self.authenticate(self.headers.getheader('Authorization')):
            ## we are authed!
            if not self.getUser(self.headers.getheader('Authorization')):
                self.sendError(500)  # w00t - something smells fishy here?
                return 0
            self.parseRequest(self.path)

            if not len(self.path):  # empty path -> redirect
                self.do_Redirect('/index.cgi')
                return

            ## python module
            if self.path.upper()[len(self.path)-4:] == ".CGI":
                modulename = self.path.lower()[:(len(self.path)-4)]
                try:
                    loader = __import__("webroot.modules.%s" % modulename)
                    module = getattr(loader.modules, modulename)
                except ImportError:
                    self.sendError(500)
                    self.logger.error("request for invalid module %s", modulename)
                    return
                if hasattr(module, 'run'):
                    try:
                        data = ""
                        data = module.run(markup, self, self.query)
                    except Exception as e:
                        self.logger.error("Error in module %s: %s", modulename, e)
                    self.defaultHeaders(False)
                    if data:
                        self.wfile.write(data)
                        self.logger.debug("webif: served module %s to user %s", modulename, self.user)
                    return
                else:
                    self.logger.error("Invalid module %s", modulename)
                    return

            ## plain file from webroot
            abspath = os.path.join(self.webroot, self.path)
            if not os.path.exists(abspath):
                self.logger.error("webif: 404: %s", abspath)
                self.sendError(404)
                return
            try:
                with open(abspath, 'r') as filecontent:
                    content = filecontent.read()
            except IOError:
                self.sendError(500)
                return
            self.mimetype = guess_type(abspath)
            self.defaultHeaders()
            self.wfile.write(content)
            self.logger.debug("webif: Served %s (%s)", abspath, self.mimetype[0])
            pass
        else:
            self.authHeaders()
            self.sendError(403)
            return

    def authenticate(self, hash):
        if not self.getUser(hash):
            return 0
        if not str(self.user) in self.config['webIfUsers']:
            self.logger.info("User %s not allowed to access web interface", self.user)
        if self.parent.checkLogin(self.user, self.passw):
            return 1
        return 0

    def parseRequest(self, request):
        request = urlparse(request)
        if hasattr(request, 'path'):
            self.path = request.path
            if self.path[0:1] == '/':
                # remove trailing / for being able to use os.path.join
                self.path = self.path[1:]
        if hasattr(request, 'query'):
            self.query = parse_qs(request.query)
        return 1

    def getUser(self, hashstring):
        try:
            hash = hashstring[6:]
        except IndexError:
            return 0
        string = b64decode(hash)
        string = string.split(":")
        try:
            self.user = string[0]
            self.passw = string[1]
        except IndexError:
            return 0
        return 1

    def loadfromwebroot(self, name):
        try:
            asset = __import__("webroot.modules.%s" % name)
            asset = getattr(asset.modules, name)
        except ImportError as e:
            return 0
        return asset

    def log_message(self, format, *args):
        return


class rewiredHTTPServer(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.parent = parent
        self.logger = self.parent.logger
        self.config = self.parent.config
        self.shutdown = 0

    def run(self):
        self.webhandler = rewiredWebHandler(self.parent, self.config)
        try:
            self.httpd = HTTPServer((self.config['webIfBind'], int(self.config['webIfPort'])), self.webhandler)
            self.httpd.socket = wrap_socket(self.httpd.socket, certfile=self.config['cert'], server_side=True)
        except:
            self.logger.error("rewiredHTTPServer:%s:%s bind failed", self.config['webIfBind'], self.config['webIfPort'])
            raise SystemExit
        while not self.shutdown:
            read, write, excep = select.select([self.httpd.socket.fileno()], [], [], .25)
            if read:
                self.httpd.handle_request()
        self.logger.info("Web interface shutdown complete")
        raise SystemExit
