def run(markup, parent, query):
    handler = parent.parent
    template = parent.loadfromwebroot('templatefunctions')

    if not template:
        raise ValueError
    title = parent.config['serverName']
    page = markup.page()
    page = template.header(page, title)
    page = template.nav(page, title, parent.user, "Overview")
    ## overview content
    page.div(class_="container")
    page.h1("Server Overview")

    page.div(class_="row-fluid")
    page.div(class_="span5 well")
    page.h2("Server Log:")
    page.p("Recently logged events")
    heading = ['Date', 'Event', 'User']
    content = [
        ['00/00 - 00:00:00', 'dummy data for now', 'docmeth02'],
        ['05/09 - 13:35:18', 'Started download', 'guest'],
        ['05/09 - 13:36:01', 'Connected', 'admin'],
        ['05/09 - 13:36:12', 'Info on user guest', 'admin'],
        ['05/09 - 13:36:20', 'Kicked user guest', 'admin']
    ]
    page = template.table(page, heading, content)
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

    content = [
        ['File Indexer', indexer],
        ['Tracker', tracker],
        ['HTTP-RPC', '<span class="label label-important">not implemented</span>']
    ]
    page = template.table(page, ['<span class="h4">Services:</span>'], content)
    page.div.close()

    page.div(class_="span3 well")
    page.h2('Status')
    activeUsers = handler.get_active_users()
    activeTransfers = handler.get_active_transfers()
    content = [
        ['Connected Users', '<span class="badge">%s</span>' % activeUsers],
        ['Active Downloads', '<span class="badge">%s</span>' % activeTransfers['down']],
        ['Active Uploads', '<span class="badge">%s</span>' % activeTransfers['up']],
        ['<br /><span class="h4"><strong>Server uptime: 01:20:32</strong></span>'],
        ['Total Users', '<span class="badge">%s</span>' % handler.get_total_users()],
        ['Total Transfers', '<span class="badge">WIP</span>']
    ]
    page = template.table(page, False, content)
    page.div.close()

    page.div.close()

    page.div.close()
    page = template.close(page)
    return str(page)
