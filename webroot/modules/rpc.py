from json import dumps


def run(markup, parent, query):
    handler = parent.parent

    if not 'type' in query:
        return "Invalid request"

    if query['type'][0] == 'shortlog':
        data = handler.get_log_events(5, 0, 0)
        if not data:
            return "{'data': false}"
        output = []
        for aevent in data:
            parsed = handler.format_event(aevent)
            if parsed:
                output.append(parsed)
        return dumps(output)

    return "{'data': false}"
