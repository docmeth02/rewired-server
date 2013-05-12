from json import dumps


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
        status['activeUsers'] = activeUsers
        status['activeTransfersdown'] = activeTransfers['down']
        status['activeTransfersup'] = activeTransfers['up']
        status['uptime'] = uptime
        status['totalfiles'] = serverTotal['Files']
        status['totalsisze'] = serverTotal['Size']
        status['totalusers'] = handler.get_total_users()
        status['totaltransfers'] = totaltransfers
        return dumps({'log': logoutput, 'status': status})

    return "{'data': false}"
