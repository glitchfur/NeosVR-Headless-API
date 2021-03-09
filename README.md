# NeosVR-Headless-API

**NeoVR-Headless-API** is a Python wrapper for the NeosVR headless client. It allows for issuing console commands and gathering responses in a Pythonic way.

It has been tested on Python 3.8.5 and later, and supports Neos version Beta 2021.3.9.130 and later. It should work the same on both Windows and Linux systems, but it has not been heavily tested on Windows.

_This project is in very early development stages._ Not all commands have been implemented yet, and further testing needs to be done to ensure that nothing breaks when unexpected console output is encountered.

This project is not officially affiliated with Neos or the Neos development team in any way.

## Usage

```python
from neosvr_headless_api import HeadlessClient
client = HeadlessClient("/path/to/NeosVR/HeadlessClient")
```

Methods of `client` are commands that are available when running the headless client natively. See [commands.txt](commands.txt) to see what has been implemented so far. Commands that were originally `camelCase` instead have `snake_case` methods associated with them.
