# NeosVR-Headless-API
# Copyright (C) 2022  GlitchFur

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
# Note the lack of space between "ID:" and "{user_id}" in the format string
# below. This is intentional. If the headless user is not logged into a Neos
# account, the ID field will be blank. In this case, "{user_id}" will catch the
# single space character, which we can then interpret as no ID. If we left the
# space in the format string, then `parse()` would fail entirely. This also
# means in all other cases, valid IDs will have an extra space before them, but
# that can be easily trimmed off.
USER_FORMAT = "{name}\tID:{user_id}\tRole: {role}\tPresent: {present}\tPing: {ping:d} ms\tFPS: {fps:g}\tSilenced: {silenced}"
BAN_FORMAT = "[{:d}]\tUsername: {name}\tUserID: {user_id}\tMachineId: {machine_id}"

# STATUS_NAME_FORMAT and STATUS_DESCRIPTION_FORMAT contain "SessionID:" and
# "Tags:" at the end of their format strings respectively because it allows for
# parsing world names and descriptions that contain newline characters. By
# "reading into" the next line of the output like this, we can detect the true
# end of those values.
STATUS_NAME_FORMAT = "Name: {}\nSessionID:{}"
STATUS_SESSION_ID_FORMAT = "SessionID: {}"
STATUS_CURRENT_USERS_FORMAT = "Current Users: {:d}"
STATUS_PRESENT_USERS_FORMAT = "Present Users: {:d}"
STATUS_MAX_USERS_FORMAT = "Max Users: {:d}"
STATUS_UPTIME_FORMAT = "Uptime: {}"
STATUS_ACCESS_LEVEL_FORMAT = "Access Level: {}"
STATUS_HIDDEN_FROM_LISTING_FORMAT = "Hidden from listing: {}"
STATUS_MOBILE_FRIENDLY_FORMAT = "Mobile Friendly: {}"
STATUS_DESCRIPTION_FORMAT = "Description: {}\nTags:{}"
STATUS_TAGS_FORMAT = "Tags: {}"
STATUS_USERS_FORMAT = "Users: {}"
