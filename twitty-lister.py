#!/usr/bin/env python
from twython import Twython

import json
import sys
import os
import re


def authorize(config):
    twitter = Twython(config['consumer']['key'], config['consumer']['secret'])
    auth_tokens = twitter.get_authentication_tokens()
    print '==> Please authorize: ' + auth_tokens['auth_url']
    verifier = raw_input('==> PIN: ').strip()
    auth = twitter.get_authorized_tokens(verifier)

    config['access'] = {}
    config['access']['key'] = auth['oauth_token']
    config['access']['secret'] = auth['oauth_token_secret']

    with open('config.json', 'wb') as handle:
        handle.write(json.dumps(config))

    return config


def get_users(path):
    users = []
    with open(path, 'r') as handle:
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
    api = None
    me = None

    print "==> Loading %d users into \"%s\"" % (len(users), list_name)

    if 'access' not in config or 'key' not in config['access'] or 'secret' not in config['access']:
        config = authorize(config)

    while True:
        try:
            api = Twython(config['consumer']['key'], config['consumer']['secret'],
                          config['access']['key'], config['access']['secret'])
            me = api.verify_credentials()
            break
        except:
            print "==> Existing tokens failed, re-authorizing"
            config = authorize(config)

    the_list = None
    for obj in api.show_lists(user_id=me["id_str"]):
        if obj["name"] == list_name:
            the_list = obj
            break

    if not the_list:
        print "==> List doesn't exist, creating it"
        the_list = api.create_list(name=list_name)

    offset = 0
    while offset < len(users):
        print "==> Sending #%d through #%d" % (offset, offset+100)
        api.create_list_members(list_id=the_list["id_str"], screen_name=users[offset:offset+100])
        offset += 100

    print "==> Done!"

if __name__ == "__main__":
    main()
