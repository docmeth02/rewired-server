def run(parent, query):
    header = parent.loadfromtemplate('header.html')
    nav = parent.loadfromtemplate('nav.html')
    footer = parent.loadfromtemplate('footer.html')

    header = header.replace('%TITLE%', "re:wired Control Panel for server %s" % parent.config['serverName'])
    nav = nav.replace('%SERVERNAME%', parent.config['serverName'])
    nav = nav.replace('%USERNAME%', parent.user)
    nav = nav.replace('%NAVLIST%', '<li class="active"><a href="index.cgi">Overview</a></li>\
              <li><a href="log.cgi">Server Log</a></li>\
              <li><a href="settings.cgi">Settings</a></li>')
    content = """    <div class="container">

      <h1>Hooray - it works!</h1>
      <p>Now get back to work</p>

    </div> <!-- /container -->"""



    return header + nav + content + footer
