# -*- coding: utf-8 -*-
from functools import wraps
import string
import math
import os

from flask import Flask, session, redirect, url_for, request, render_template, jsonify
from flask_redis import Redis

from twython import Twython

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['TWITTER_KEY'] = os.environ['TWITTER_KEY']
app.config['TWITTER_SECRET'] = os.environ['TWITTER_SECRET']
app.config['REDIS_URL'] = os.environ[os.environ.get('REDIS_URL_ENV', 'REDIS_URL')]
app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME')
app.config['DEBUG'] = (os.environ.get('ENV') == 'DEVELOPMENT')

redis = Redis(app)


def _logout():
    '''Flush all the stuff from the session.'''
    if 'TWITTER_ID' in session:
        redis.delete("tl:%s:usernames" % session['TWITTER_ID'])
    session.clear()


def twitter_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'TWITTER_ID' not in session:
            _logout()
            return redirect(url_for("twitter_auth_pre"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/twitter/authenticate/deep-breath")
def twitter_auth_pre():
    return render_template("preauth.html")


@app.route("/twitter/authenticate")
def twitter_auth():
    _logout()
    twitter = Twython(app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'])
    auth = twitter.get_authentication_tokens(callback_url=url_for("twitter_auth_callback", _external=True))
    session['OAUTH_TOKEN'] = auth['oauth_token']
    session['OAUTH_TOKEN_SECRET'] = auth['oauth_token_secret']
    return redirect(auth['auth_url'])


@app.route("/twitter/authenticate/callback")
def twitter_auth_callback():
    twitter = Twython(app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'], session['OAUTH_TOKEN'], session['OAUTH_TOKEN_SECRET'])

    del session['OAUTH_TOKEN']
    del session['OAUTH_TOKEN_SECRET']

    if 'denied' in request.args:
        _logout()
        return redirect(url_for('index'))

    final_step = twitter.get_authorized_tokens(request.args['oauth_verifier'])
    session['SESSION_OAUTH_TOKEN'] = final_step['oauth_token']
    session['SESSION_OAUTH_TOKEN_SECRET'] = final_step['oauth_token_secret']

    twitter = Twython(app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'], session['SESSION_OAUTH_TOKEN'], session['SESSION_OAUTH_TOKEN_SECRET'])
    me = twitter.verify_credentials()
    session['TWITTER_ID'] = me['id_str']
    session['TWITTER_AVATAR'] = me['profile_image_url_https']
    session['NAME'] = me['name']

    return redirect(url_for('upload'))


@app.route("/upload", methods=('GET', 'POST'))
@twitter_auth_required
def upload():
    usernames = []  # TODO: Load from redis?
    error = None
    if request.method == 'POST':
        usernames = request.form.get('usernames', '')
        usernames = filter(None, map(string.strip, usernames.replace("\r", "").replace("@", "").replace(",", "").split("\n")))
        if usernames:
            key = "tl:%s:usernames" % session['TWITTER_ID']
            redis.delete(key)
            redis.lpush(key, *usernames)
            redis.expire(key, 86400)
            return redirect(url_for("list"))
        else:
            error = "You need some usernames."
    return render_template("upload.html", usernames=usernames, error=error)


@app.route("/list", methods=('GET', 'POST'))
@twitter_auth_required
def list():
    if not redis.exists("tl:%s:usernames" % session['TWITTER_ID']):
        return redirect(url_for("upload"))

    twitter = Twython(app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'], session['SESSION_OAUTH_TOKEN'], session['SESSION_OAUTH_TOKEN_SECRET'])
    lists = twitter.show_lists(user_id=session['TWITTER_ID'])

    error = None

    if request.method == 'POST':
        list_id = request.form.get('list')
        list_name = None
        list_uri = None
        new_list_name = request.form.get('name')
        if not list_id:
            error = "You need to pick a list."
        elif list_id == "NEW":
            if not new_list_name:
                error = "A new list needs a name."
            else:
                new_list = twitter.create_list(name=new_list_name)
                list_id = new_list['id_str']
                list_name = new_list['name']
                list_uri = new_list['uri']
        else:
            for tlist in lists:
                if tlist['id_str'] == list_id:
                    list_name = tlist['name']
                    list_uri = tlist['uri']
                    break
            if not list_name:
                error = "Unknown List"

        if not error:
            job_id = redis.incr("tl:job_counter")

            print "New job:", job_id

            redis.rename("tl:%s:usernames" % session['TWITTER_ID'], "tl:job:%s:usernames" % job_id)
            redis.hmset("tl:job:%s" % job_id, {"list_id": list_id, "list_name": list_name, "list_url": "https://twitter.com%s" % list_uri, "usernames": redis.llen("tl:job:%s:usernames" % job_id), "index": 0})

            redis.expire("tl:job:%s:usernames" % job_id, 86400)
            redis.expire("tl:job:%s" % job_id, 86400)

            return redirect(url_for("watch", job_id=job_id))

    return render_template("list.html", lists=lists, error=error)


@twitter_auth_required
@app.route("/wait/<job_id>")
def watch(job_id):
    job = redis.hgetall("tl:job:%s" % job_id)
    if not job:
        return render_template("404.html", message="Job Not Found")

    size = int(job['usernames'])
    index = int(job['index'])

    return render_template(
        "watch.html",
        job=job,
        work_url=url_for("work", job_id=job_id),
        progress=int(math.floor(min(index, size)/float(size)*100))
    )


@twitter_auth_required
@app.route("/work/<job_id>")
def work(job_id):
    job = redis.hgetall("tl:job:%s" % job_id)
    if not job:
        return jsonify(error="Job Not Found")

    twitter = Twython(app.config['TWITTER_KEY'], app.config['TWITTER_SECRET'], session['SESSION_OAUTH_TOKEN'], session['SESSION_OAUTH_TOKEN_SECRET'])
    index = int(job['index'])
    usernames = redis.lrange("tl:job:%s:usernames" % job_id, index, index + 100)
    if usernames:
        print "usernames:", usernames
        print twitter.create_list_members(list_id=job["list_id"], screen_name=','.join(usernames))

    index = index + 100
    redis.hset("tl:job:%s" % job_id, "index", index)
    size = int(job['usernames'])

    return jsonify(progress=int(math.floor(min(index, size)/float(size)*100)))


if __name__ == "__main__":
    app.run(debug=True)
