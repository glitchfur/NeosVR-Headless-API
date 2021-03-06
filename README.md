# NeosVR-Headless-API

**NeosVR-Headless-API** is a Python wrapper and API for the NeosVR [headless client](https://wiki.neos.com/Headless_Client). With it, you can programmatically control headless clients both locally and remotely.

It aims to be easy to use by doing the heavy work of parsing command output for you and turns it into Python objects that you can use any way you like.

The [wiki](https://github.com/glitchfur/NeosVR-Headless-API/wiki) has more information about NeosVR-Headless-API, or if you want to get started right away you can jump into [Getting started](https://github.com/glitchfur/NeosVR-Headless-API/wiki/Getting-started). The [online documentation](https://docs.glitchfur.net/NeosVR-Headless-API) has a detailed explanation of all the methods available and how to use them.

```python
In [1]: from neosvr_headless_api import LocalHeadlessClient

In [2]: hc = LocalHeadlessClient("/home/glitch/Servers/NeosVR")

In [3]: hc.wait_for_ready()
Out[3]: True

In [4]: hc.status()
Out[4]: 
{'name': "Glitch's World",
 'session_id': 'S-1462cabf-9ac4-46b7-80b4-3921455093e1',
 'current_users': 1,
 'present_users': 0,
 'max_users': 8,
 'uptime': '00:00:18.9775300',
 'access_level': 'Anyone',
 'hidden_from_listing': False,
 'mobile_friendly': False,
 'description': 'This is where a cat knocks a bunch of stuff over.',
 'tags': ["computer", "cat", "code", "coffee", "chaos"],
 'users': ['GlitchHost']}

In [5]: hc.shutdown()
Out[5]: 0
```

This project uses the [GNU GPLv3](/LICENSE.txt) license.
