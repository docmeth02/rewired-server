from json import dumps
from os import getpid, name
from resource import getrusage, RUSAGE_SELF, RUSAGE_CHILDREN
from platform import system

def run(markup, parent, query):
    handler = parent.parent

    if not 'type' in query:
        return "Invalid request"

    if query['type'][0] == 'overview':
        data = handler.get_log_events(5, 0, 0)
        if not data:
            return "{'data': false}"
        logoutput = []
        for aevent in data:
            parsed = handler.format_event(aevent)
            if parsed:
                logoutput.append(parsed)

        status = {}
        serverTotal = handler.get_server_size()
        activeUsers = handler.get_active_users()
        activeTransfers = handler.get_active_transfers()
        uptime = handler.get_server_uptime()
        totaltransfers = handler.get_total_transfers()
        status['pid'] = getpid()
        memory = 0
        try:
            memory = getrusage(RUSAGE_SELF).ru_maxrss
            memory += getrusage(RUSAGE_CHILDREN).ru_maxrss
            if system() == 'Linux':  # bytes on osx, kbytes on linux
                memory *= 1024
        except:
            pass
        status['memory'] = handler.format_size(memory)
        status['activeUsers'] = activeUsers
        status['activeTransfersdown'] = activeTransfers['down']
        status['activeTransfersup'] = activeTransfers['up']
        status['uptime'] = uptime
        status['totalfiles'] = serverTotal['Files']
        status['totalsisze'] = serverTotal['Size']
        status['totalusers'] = handler.get_total_users()
        status['totaltransfers'] = totaltransfers
        return dumps({'log': logoutput, 'status': status})

    if query['type'][0] == 'log':
        count = handler.get_event_count()
        offset = 0
        if 'offset' in query:
            try:
                offset = int(query['offset'][0])
            except:
                pass
        data = handler.get_log_events(25, 0, offset)
        if not data:
            return "{'data': false}"
        logdata = []
        for aevent in data:
            aevent = handler.format_event(aevent, True)
            if aevent:
                logdata.append(aevent)
        return dumps({'count': count, 'log': logdata})

    return "{'data': false}"
