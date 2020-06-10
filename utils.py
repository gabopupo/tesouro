def toLower(s):
    s = str(s)
    return s.lower()

def purge(update, context, bot=True):
    if bot:
        context.user_data['bot'].delete()
    update.message.delete()

def exists(person, people):
    return (any(person == p['alias'] for p in people) or any(person == p['handle'] for p in people))