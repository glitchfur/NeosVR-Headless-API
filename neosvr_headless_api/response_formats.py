# This file contains format strings that describe how the output of the various
# commands in the headless client should be parsed. If the NeosVR developers
# change the format of any command's response, this file can be easily updated
# so that NeosVR-Headless-API can continue to parse responses properly.

# For more information on how to write these strings, please see:
# https://github.com/r1chardj0n3s/parse
# https://docs.python.org/3/library/string.html#format-string-syntax

# These are for parsing all the startup messages that come BEFORE the prompt.
NEOS_VERSION_FORMAT = "Initializing Neos: {}"
SUPPORTED_TEXTURE_FORMATS_FORMAT = "Supported Texture Formats: {}"
AVAILABLE_LOCALES_FORMAT = "Available locales: {}"
ARGUMENT_FORMAT = "Argument: {}"
COMPATIBILITY_HASH_FORMAT = "Compatibility Hash: {}"
MACHINE_ID_FORMAT = "MachineID: {}"
SUPPORTED_NETWORK_PROTOCOLS_FORMAT = "Supported network protocols: {}"

WORLD_FORMAT = "[{:d}] {name}Users: {users:d}\tPresent: {present:d}\tAccessLevel: {access_level}\tMaxUsers: {max_users:d}"
USER_FORMAT = "{name}\tRole: {role}\tPresent: {present}\tPing: {ping:d} ms\tFPS: {fps:f}"

# This includes "SessionID:" because world names can contain newline characters.
# By including a part of the next line in the format string we can make sure we
# are getting the full world name, even if it includes newlines.
STATUS_NAME_FORMAT = "Name: {}\nSessionID:{}"
# No STATUS_SESSION_ID_FORMAT because it can be None.
STATUS_CURRENT_USERS_FORMAT = "Current Users: {:d}"
STATUS_PRESENT_USERS_FORMAT = "Present Users: {:d}"
STATUS_MAX_USERS_FORMAT = "Max Users: {:d}"
STATUS_UPTIME_FORMAT = "Uptime: {}"
STATUS_ACCESS_LEVEL_FORMAT = "Access Level: {}"
STATUS_HIDDEN_FROM_LISTING_FORMAT = "Hidden from listing: {}"
STATUS_MOBILE_FRIENDLY_FORMAT = "Mobile Friendly: {}"
# No STATUS_DESCRIPTION_FORMAT because it can be None.
# No STATUS_TAGS_FORMAT because it can be empty.
STATUS_USERS_FORMAT = "Users: {}"
