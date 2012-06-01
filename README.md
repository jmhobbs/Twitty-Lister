# Twitty-Lister

This program is a simple tool to import users from a file into a Twitter
list.

# Installation

  1. Download <tt>twitty-lister.py</tt>
  2. <tt>pip install -r requirements.txt</tt>

# Usage

To run twitty-lister you will need two files.  The first is a
<tt>config.json</tt> which will contain your app keys.

```json
{
  "consumer": {
    "secret": "YOUR-SECRET-HERE",
    "key": "YOUR-KEY-HERE"
  }
}
```

You will also need a list file with all of your screen names to import.
This can be fairly dirty as twitty-lister will clean them up for you.

```text
@jmhobbs
whatcheer
    @alexpgates
@iliveinomaha
bnispel  
  @iloveinomaha
johnhenrymuller  
```

Next, you will need to run <tt>twitty-lister.py</tt> and authorize the
account through the PIN mechanism.  After you authorize, it will add the
users in blocks of 100.

```bash
(venv)jmhobbs@Cordelia~/twitty-lister$ python twitty-lister.py "What Cheer" screen_names 
==> Loading 7 users into "What Cheer"
==> Please authorize: http://api.twitter.com/oauth/authorize?oauth_token=xzKc2CHt22Xf3yqP3R0e9D3ACCIoPbNmOxfbLZaPWE
==> PIN: 9546060
==> List doesn't exist, creating it
==> Sending #0 through #100
==> Done!
```

That's it!

