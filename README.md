# NeosVR-Headless-API

**NeosVR-Headless-API** is a Python wrapper and API for the NeosVR headless client. With it, you can programmatically control headless clients both locally and remotely.

It aims to be easy to use by doing the heavy work of parsing command output for you and turns it into Python objects that you can use any way you like.

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

For more information, including how to get started with NeosVR-Headless-API, please visit the [wiki](https://github.com/glitchfur/NeosVR-Headless-API/wiki).
