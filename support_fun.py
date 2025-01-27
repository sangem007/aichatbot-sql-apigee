def responseContentCheck(message):
    if message.content is None:
        return ""
    else:
        return message.content