def run(markup, parent, query):
    handler = parent.parent
    template = parent.loadfromwebroot('templatefunctions')

    if not template:
        raise ValueError
    title = parent.config['serverName']
    script = """<script src="/js/log.js"></script>
<script type="text/javascript">
$(document).ready(function() {
    window.offset = 0;
    window.perpage = 25;
    if (window.offset == 0) {
        getlog();
        window.updatetimer = setInterval(function() {
            getlog();
        }, 60000);
    }
});
</script>"""
    page = markup.page()
    page = template.header(page, title, script)
    page = template.nav(page, title, parent.user, "Overview")
    ## overview content
    page.div.close()
    page.div(class_="container")
    page.h1("Log View")

    page.div(class_="row-fluid")
    page.div(class_="span12 well")
    page.div(class_="pagination pagination-centered", id="pagenavtop")
    page.div.close()

    page.table(class_="table table-striped", id="log")
    page.thead()
    page.tr()
    page.th("Date", style="width: 20%")
    page.th("User", style="width: 20%")
    page.th("Event", style="width: 40%")
    page.th("Result", style="width: 20%")
    page.tr.close()
    page.thead.close()
    page.tbody("")
    page.table.close()
    page.div(class_="pagination pagination-centered", id="pagenavbot")
    page.div.close()
    page.div.close()
    page.div.close()
    page = template.close(page)
    return str(page)
