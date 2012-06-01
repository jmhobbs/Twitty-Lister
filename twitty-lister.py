#!/usr/bin/env python
import tweepy
import json
import sys
import os
import types
import re

def authorize(config):
    auth = tweepy.OAuthHandler(config['consumer']['key'].encode('ascii','ignore'), config['consumer']['secret'].encode('ascii','ignore'))
    auth_url = auth.get_authorization_url()
    print '==> Please authorize: ' + auth_url
    verifier = raw_input('==> PIN: ').strip()
    auth.get_access_token(verifier)

    config['access'] = {}
    config['access']['key'] = auth.access_token.key
    config['access']['secret'] = auth.access_token.secret

    with open('config.json', 'wb') as handle:
        handle.write(json.dumps(config))

    return config

def get_users(path):
    users = []
    with open( path, 'r' ) as handle:
        for line in handle:
            line = re.sub('[^a-zA-Z0-9_]', '', line)
            if len(line) > 0:
                users.append(line)
    return users

def main():

    if 3 != len(sys.argv):
        sys.stderr.write("""usage: %s <LIST> <FILE>

LIST : The name of the list you want to import members into.
FILE : A file with newline separated screen names.
""" % os.path.basename(sys.argv[0]))
        exit(1)

    with open('config.json', 'rb') as handle:
        config = json.loads(handle.read())

    list_name = sys.argv[1]
    csv = sys.argv[2]
    users = get_users(csv)

    print "==> Loading %d users into \"%s\"" % (len(users), list_name)

    if 'access' not in config or 'key' not in config['access'] or 'secret' not in config['access']:
        config = authorize(config)

    while True:
        try:
            auth = tweepy.OAuthHandler(config['consumer']['key'].encode('ascii','ignore'), config['consumer']['secret'].encode('ascii','ignore'))
            auth.set_access_token(config['access']['key'].encode('ascii','ignore'), config['access']['secret'].encode('ascii','ignore'))
            api = tweepy.API(auth)
            me = api.me()
            break
        except:
            print "==> Existing tokens failed, re-authorizing"
            config = authorize(config)

    the_list = None
    for obj in me.lists():
        if obj.name == list_name:
            the_list = obj
            break

    if not the_list:
        print "==> List doesn't exist, creating it"
        the_list = api.create_list(name=list_name)

    # Okay, so now we have to monkey-patch the api for the lists/members/create_all
    # We only need this until the module gets updated
    if 'add_list_members' not in dir(api):
        def add_list_members (self, *args, **kargs):
                return tweepy.binder.bind_api(
                    path = '/lists/members/create_all.json',
                    method = 'POST',
                    payload_type = 'list',
                    allowed_param = ['list_id','slug','owner_id','owner_screen_name','screen_name','user_id'],
                    require_auth = True
                )(self, *args, **kargs)

        api.add_list_members = types.MethodType( add_list_members, api )

    offset = 0
    while offset < len(users):
        print "==> Sending #%d through #%d" % (offset, offset+100)
        api.add_list_members(list_id=the_list.id, screen_name=','.join(users[offset:offset+100]))
        offset += 100

    print "==> Done!"

if __name__ == "__main__":
    main()
