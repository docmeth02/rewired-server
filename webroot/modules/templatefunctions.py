def header(page, title, footer=False):
    defaultfooter = """
    <script src="//ajax.googleapis.com/ajax/libs/jquery/2.0.0/jquery.min.js"></script>
    <script src="//netdna.bootstrapcdn.com/twitter-bootstrap/2.3.1/js/bootstrap.min.js"></script>"""
    if footer:
        defaultfooter += footer
    page.init(title="%s web interface" % title,
                    css=('css/styles.css',
                         '//netdna.bootstrapcdn.com/twitter-bootstrap/2.3.1/css/bootstrap-combined.min.css'),
                    metainfo = {'viewport': 'width=device-width, initial-scale=1.0',
                    'description': '', 'author': 'docmeth02'},
                    charset = 'UTF-8',
                    doctype = "<!DOCTYPE html>",
                    footer = defaultfooter)
    return page


def nav(page, title, user, active):
    page.div(class_="navbar navbar-inverse navbar-fixed-top")
    page.div(class_="navbar-inner")
    page.div(class_="container")
    page.button(class_="btn btn-navbar", data_toggle="collapse", data_target=".nav-collapse")
    for i in range(0, 3):
        page.span(class_="icon-bar")
        page.span.close()
    page.button.close()
    page.a(title, class_="brand", href="/index.cgi")
    page.div(class_="nav-collapse collapse")
    page.p("Logged in as %s" % user, class_="navbar-text pull-right")
    page.ul(class_="nav")
    nav = {'Overview': '/index.cgi', 'Server Log': '/log.cgi', 'Settings': '/settings.cgi'}
    for anavitem, anavlink in nav.items():
        if anavitem == active:
            page.li(class_="active")
        else:
            page.li()
        page.a(str(anavitem), href=anavlink)
        page.li.close()
    page.ul.close()
    for i in range(0, 3):
        page.div.close()
    return page


def close(page):
    page.div.close()
    return page


def table(page, heading, content, id=False):
    if id:
        page.table(class_="table table-condensed", id=id)
    else:
        page.table(class_="table table-condensed")
    if heading:
        page.thead()
        page.tr()
        for item in heading:
            page.th(str(item))
        page.tr.close()
        page.thead.close()
    page.tbody()
    if content:
        for arow in content:
            page.tr()
            for item in arow:
                page.td(item)
            page.tr.close()
    page.tbody.close()
    page.table.close()
    return page
