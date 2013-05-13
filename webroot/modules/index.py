from os import getpid
from resource import getrusage, RUSAGE_SELF, RUSAGE_CHILDREN
from platform import system


def run(markup, parent, query):
    handler = parent.parent
    template = parent.loadfromwebroot('templatefunctions')

    if not template:
        raise ValueError
    title = parent.config['serverName']
    script = """
    <script src="/js/overview.js"></script>
    <script type="text/javascript">
    $(document).ready(function(){
        $('#spinner').show();
        var myVar=setInterval(function(){ $('#log').hide(); update(); $('#log').show(); },60000);
         update();
         $('#spinner').hide();
    });
        </script>"""
    page = markup.page()
    page = template.header(page, title, script)
    page = template.nav(page, title, parent.user, "Overview")
    ## overview content
    page.div.close()
    page.div(class_="container")
    page.h1("Server Overview")

    page.div(class_="row-fluid")
    page.div(class_="span5 well")
    page.h2("Server Log:")
    spinner = '<img id="spinner" src="css/spinner.gif" alt="spinner"/>'
    page.p("Recently logged events %s" % spinner)
    heading = ['Date', 'Event', 'User']

    page = template.table(page, heading, [], 'log')
    page.div.close()

    page.div(class_="span3 well")
    page.h2('Information')
    platform = handler.get_platform()
    if platform:
        platform = "%s %s (%s)" % (platform['OS'], platform['OSVersion'], platform['ARCH'])
    page.p('<span class="label label-info">%s %s</span> running on %s'
           % (parent.config['appName'], parent.config['appVersion'], platform))
    indexer = handler.check_indexer()
    if not indexer:
        indexer = '<span class="label label-important">disabled</span>'
    elif indexer == 'crashed':
        indexer = '<span class="label label-warning">crashed</span>'
    else:
        indexer = '<span class="label label-success">running</span>'

    tracker = handler.check_tracker()
    if not tracker:
        tracker = '<span class="label label-important">disabled</span>'
    elif tracker == 'crashed':
        tracker = '<span class="label label-warning">crashed</span>'
    else:
        tracker = '<span class="label label-success">%s registered</span>' % tracker

    pid, memory = (getpid(), 0)
    try:
        memory = getrusage(RUSAGE_SELF).ru_maxrss
        memory += getrusage(RUSAGE_CHILDREN).ru_maxrss
        if system() == 'Linux':  # bytes on osx, kbytes on linux
            memory *= 1024

    except:
        pass
    memory = handler.format_size(memory)
    content = [
        ['Process ID:', '<span id="pid">%s</span>' % pid],
        ['Memory usage:', '<span id="memory">%s</span>' % memory]
    ]
    page = template.table(page, [''], content)

    content = [
        ['File Indexer:', indexer],
        ['Tracker:', tracker],
        ['HTTP-RPC:', '<span class="label label-important">not implemented</span>']
    ]
    page = template.table(page, ['<span class="h4">Services:</span>'], content)
    page.div.close()

    page.div(class_="span3 well")
    page.h2('Status')
    serverTotal = handler.get_server_size()
    activeUsers = handler.get_active_users()
    activeTransfers = handler.get_active_transfers()
    uptime = handler.get_server_uptime()
    totaltransfers = handler.get_total_transfers()
    content = [
        ['Connected Users:', '<span class="badge" id="activeUsers"> %s </span>' % activeUsers],
        ['Active Downloads:', '<span class="badge" id="activeTransfersdown"> %s </span>' % activeTransfers['down']],
        ['Active Uploads:', '<span class="badge" id="activeTransfersup"> %s </span>' % activeTransfers['up']],
        ['<br /><span class="h4"><strong>Server uptime:</strong></span><p id="uptime">%s</p>' % uptime],
        ['Files:', '<span class="label label-info" id="totalfiles"> %s </span>' % serverTotal['Files']],
        ['Size:', '<span class="label label-info" id="totalsisze"> %s </span>' % serverTotal['Size']],
        ['Total Users:', '<span class="label label-info" id="totalusers"> %s </span>' % handler.get_total_users()],
        ['Total Transfers:', '<span class="label label-info" id="totaltransfers"> %s </span>' % totaltransfers]
    ]
    page = template.table(page, False, content)
    page.div.close()

    page.div.close()
    page = template.close(page)
    return str(page)
