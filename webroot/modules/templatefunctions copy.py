def header(page, title):
    page.init(title="%s web interface" % title,
                    css=('css/bootstrap.css', 'css/bootstrap-responsive.css'),
                    metainfo = {'viewport': 'width=device-width, initial-scale=1.0',
                    'description': '', 'author': 'docmeth02'},
                    charset = 'UTF-8',
                    doctype = "<!DOCTYPE html>",
                    footer = """<script src="js/jquery.js"></script>
    <script src="js/bootstrap-transition.js"></script>
    <script src="js/bootstrap-alert.js"></script>
    <script src="js/bootstrap-modal.js"></script>
    <script src="js/bootstrap-dropdown.js"></script>
    <script src="js/bootstrap-scrollspy.js"></script>
    <script src="js/bootstrap-tab.js"></script>
    <script src="js/bootstrap-tooltip.js"></script>
    <script src="js/bootstrap-popover.js"></script>
    <script src="js/bootstrap-button.js"></script>
    <script src="js/bootstrap-collapse.js"></script>
    <script src="js/bootstrap-carousel.js"></script>
    <script src="js/bootstrap-typeahead.js"></script>""")
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
