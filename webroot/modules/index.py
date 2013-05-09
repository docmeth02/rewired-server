def run(markup, parent, query):
    template = parent.loadfromwebroot('templatefunctions')
    if not template:
        raise ValueError
    title = parent.config['serverName']
    page = markup.page()
    page = template.header(page, title)
    page = template.nav(page, title, parent.user, "Overview")

    page.div(class_="container")
    page.h1("Hooray - it works!")
    page.p("Now back to work!")
    page.div.close()
    page = template.close(page)
    return str(page)

