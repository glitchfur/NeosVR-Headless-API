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

"""
**NeosVR-Headless-API** is a Python wrapper and API for the NeosVR headless client.
The project can be found on [GitHub](https://github.com/glitchfur/NeosVR-Headless-API)
and the [wiki](https://github.com/glitchfur/NeosVR-Headless-API/wiki) can help you
get started in the right direction.
"""

from __future__ import annotations
from typing import Union

from threading import Thread, Event
from queue import Queue, Empty
from subprocess import Popen, PIPE
from concurrent.futures import ThreadPoolExecutor
from os import path

from parse import parse, findall

from .response_formats import *

# Constants for "role" command
ADMIN = "Admin"
BUILDER = "Builder"
MODERATOR = "Moderator"
GUEST = "Guest"
SPECTATOR = "Spectator"

# Constants for "accessLevel" command
PRIVATE = "Private"
LAN = "LAN"
FRIENDS = "Friends"
FRIENDS_OF_FRIENDS = "FriendsOfFriends"
REGISTERED_USERS = "RegisteredUsers"
ANYONE = "Anyone"

# Maximum time to wait for RPC responses (in seconds)
SYNC_REQUEST_TIMEOUT = 60


class HeadlessClient:
    """
    High-level API to the NeosVR headless client. This class shouldn't be
    instantiated directly. You'll want to use the `LocalHeadlessClient` or
    `RemoteHeadlessClient` subclasses.
    """

    def __init__(self, neos_dir: str, config: str = None):
        """
        Start a headless client using `Neos.exe` in `neos_dir` using `config`
        as the configuration file, if provided. `LocalHeadlessClient` or
        `RemoteHeadlessClient` decides how the process is attached, but
        everything else is the same.
        """
        try:
            self.process
        except AttributeError:
            raise RuntimeError(
                "Please use either `LocalHeadlessClient` or "
                "`RemoteHeadlessClient` instead."
            )
        self.neos_dir = neos_dir
        # Config is pulled from the parent `HeadlessProcess` instance as it
        # may not necessarily be the same as what was provided for
        # the `config` keyword.
        self.config = self.process.config
        self.command_queue = Queue()
        self.ready = Event()

        self.version = None
        self.supported_texture_formats = None
        self.available_locales = None
        self.argument = None
        self.compatibility_hash = None
        self.machine_id = None
        self.supported_network_protocols = None

        def init():
            """Parse startup messages and determine when it's ready."""
            # `almost_ready` is set to True when at least one world is
            # running. Only then do we look for the ">" character in the
            # prompt, to prevent false positives.
            almost_ready = False
            while True:
                # If the timeout is hit, assume that startup has halted due to
                # some sort of error, ex. network issues or incorrect Neos
                # password. Don't bother collecting other startup info, and
                # never mark the headless client as ready.
                try:
                    ln = self.process.readline(timeout=30)
                except CommandTimeout:
                    break
                self._check_startup_line(ln)
                if ln.endswith(">") and almost_ready:
                    self.ready.set()
                    break
                elif ln == "World running...":
                    almost_ready = True

        init_thread = Thread(target=init)
        init_thread.start()

        self._command_thread = Thread(target=self._command_processor)
        self._command_thread.daemon = True
        self._command_thread.start()

        # TODO: Implement proper shutdown.
        self._async_thread = ThreadPoolExecutor(max_workers=1)

    def _check_startup_line(self, ln):
        """Extracts info from startup messages."""
        fmt = parse(NEOS_VERSION_FORMAT, ln)
        if fmt:
            self.version = fmt[0]
            return
        fmt = parse(SUPPORTED_TEXTURE_FORMATS_FORMAT, ln)
        if fmt:
            self.supported_texture_formats = fmt[0].split(", ")
            return
        fmt = parse(AVAILABLE_LOCALES_FORMAT, ln)
        if fmt:
            self.available_locales = fmt[0].split(", ")
            return
        fmt = parse(ARGUMENT_FORMAT, ln)
        if fmt:
            self.argument = fmt[0]
            return
        fmt = parse(COMPATIBILITY_HASH_FORMAT, ln)
        if fmt:
            self.compatibility_hash = fmt[0]
            return
        fmt = parse(MACHINE_ID_FORMAT, ln)
        if fmt:
            self.machine_id = fmt[0]
            return
        fmt = parse(SUPPORTED_NETWORK_PROTOCOLS_FORMAT, ln)
        if fmt:
            self.supported_network_protocols = fmt[0].split(", ")
            return

    def _command_processor(self):
        """Dedicated thread for processing command queue."""
        while True:
            hcmd = self.command_queue.get()

            # If a world is specified, try to focus it. If it doesn't exist,
            # pass along an exception and don't execute the next command.

            execute_command = True

            if hcmd.world != None:
                if isinstance(hcmd.world, int):
                    self.process.write("focus %d\n" % hcmd.world)
                else:
                    self.process.write('focus "%s"\n' % hcmd.world)

                errors = [
                    "World with this name does not exist",
                    "World index out of range",
                ]

                while True:
                    try:
                        ln = self.process.readline(timeout=30)
                    except CommandTimeout as e:
                        # Recreate the exception to avoid rpyc proxying issues.
                        hcmd.set_result(CommandTimeout(e.args[0]))
                        execute_command = False
                        break
                    if ln in errors:
                        # Pass the exception, caller is responsible for raising.
                        hcmd.set_result(NeosError(ln))
                        # Signal to skip the remainder of the parent loop.
                        execute_command = False
                    elif ln.endswith(">"):
                        break

            # If a world to focus was specified and focusing that world failed,
            # the command intended to be run after it should not be executed.

            if not execute_command:
                self.command_queue.task_done()
                continue

            # Execute the actual command here.

            command_timeout = False

            self.process.write("%s\n" % hcmd.cmd)
            res = []
            while True:
                try:
                    ln = self.process.readline(timeout=30)
                except CommandTimeout as e:
                    # Recreate the exception to avoid rpyc proxying issues.
                    hcmd.set_result(CommandTimeout(e.args[0]))
                    command_timeout = True
                    break
                if ln.endswith(">"):
                    break
                res.append(ln)

            if command_timeout:
                self.command_queue.task_done()
                continue

            hcmd.set_result(res)
            self.command_queue.task_done()

    def is_ready(self) -> bool:
        """
        Returns `True` if the headless client is ready to accept commands.
        Otherwise returns `False`. Alias for `self.ready.is_set()`
        """
        return self.ready.is_set()

    def wait_for_ready(self, timeout: int = None) -> bool:
        """
        Block until the headless client is ready to accept commands. Returns
        `True` when ready. If `timeout` is specified and the headless client
        takes longer than `timeout` seconds to become ready, returns `False`.
        """
        return self.ready.wait(timeout=timeout)

    def wait_for_shutdown(self, timeout: int = None) -> int:
        """
        Block until the headless client has shut down. Returns the exit code
        when the client has exited. If `timeout` is specified and the headless
        client takes longer than `timeout` seconds to shut down, raises a
        `TimeoutExpired` exception.
        """
        return self.process.wait(timeout=timeout)

    def sigint(self):
        """
        Send a SIGINT to the headless client.

        This is an implementation-specific function, so it is overridden by
        the `LocalHeadlessClient` and `RemoteHeadlessClient` subclasses.
        """
        pass

    def terminate(self):
        """
        Send a SIGTERM to the headless client.

        This is an implementation-specific function, so it is overridden by
        the `LocalHeadlessClient` and `RemoteHeadlessClient` subclasses.
        """
        pass

    def kill(self):
        """
        Send a SIGKILL to the headless client.

        This is an implementation-specific function, so it is overridden by
        the `LocalHeadlessClient` and `RemoteHeadlessClient` subclasses.
        """
        pass

    def send_command(self, cmd: str, world: Union[str, int] = None) -> list:
        """
        Sends a command to the console, returns the output as a `list`. Each
        item of the `list` is a single line of command output, exactly as returned
        by the headless client. You can use this method to run commands that
        haven't been added to the API yet.
        """
        if not self.is_ready():
            raise HeadlessNotReady("The headless client is still starting up.")
        hcmd = HeadlessCommand(cmd, world=world)
        self.command_queue.put(hcmd)
        # This will block until it is this command's turn in the queue, and it
        # will return the result as soon as it is available.
        # See the `HeadlessCommand` class for more info.
        result = hcmd.result()
        if isinstance(result, (NeosError, CommandTimeout)):
            raise result
        return result

    def async_(self, func, *args, **kwargs):
        """
        Wait for the results of a function asynchronously. Pass the `func` that
        you want to execute as well as any required `args` or `kwargs`. This
        returns a `Future` object from `concurrent.futures`. See Python's
        documentation for information on how to use it.
        """
        fut = self._async_thread.submit(func, *args, **kwargs)
        return fut

    # BEGIN HEADLESS CLIENT COMMANDS

    # TODO: Implement `saveConfig` here
    def save_config(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    def login(self, username_or_email: str, password: str) -> str:
        """
        Log into a Neos account.

        Returns the success message, or raises `NeosError` if the login failed.
        """
        cmd = self.send_command('login "%s" "%s"' % (username_or_email, password))
        errors = ["Invalid credentials", "Already logged in!"]
        for ln in cmd:
            if ln == "Logged in successfully!":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def logout(self) -> str:
        """
        Log out from the current Neos account.

        Returns the success message, or raises `NeosError` if already logged out.
        """
        cmd = self.send_command("logout")
        for ln in cmd:
            if ln == "Logged out!":
                return ln
            elif ln == "Not logged in!":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def message(self, friend_name: str, message: str) -> str:
        """
        Message user in friends list.

        Returns the success message, or raises `NeosError` if there was a problem.
        """
        cmd = self.send_command('message "%s" "%s"' % (friend_name, message))
        errors = ["No friend with this username", "Not logged in!"]
        for ln in cmd:
            if ln == "Message sent!":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def invite(self, friend_name: str, world: Union[str, int] = None) -> str:
        """
        Invite a friend to the currently focused world. If `world` is specified,
        they are invited to that world instead. `world` can be a world index,
        world name, or session ID.

        Returns the success message or raises `NeosError` if there was a problem.
        """
        cmd = self.send_command('invite "%s"' % friend_name, world=world)
        errors = ["No friend with this username", "Not logged in!"]
        for ln in cmd:
            if ln == "Invite sent!":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def friend_requests(self) -> List[str]:
        """
        List current friend requests

        Return the list of the user who have send a friend request
        """
        return self.send_command('friendRequests')

    # TODO: Implement `acceptFriendRequest` here
    def accept_friend_request(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    def worlds(self) -> list[dict]:
        """
        Lists all active worlds. Returns a `list` of `dict`.

        Each `dict` corresponds to a world with the following keys:

        - **name**: `str`
          - Name of the world
        - **users**: `int`
          - How many users are *connected* to the world
        - **present**: `int`
          - How many users are *present* in the world
        - **access_level**: `str`
          - The access level setting of the world. Ex. "Anyone" or "Friends"
        - **max_users**: `int`
          - The maximum number of users allowed to connect
        """
        cmd = self.send_command("worlds")

        # World names can contain newline characters, so we have to put the
        # whole command output back together and examine the whole thing.
        cmd = "\n".join(cmd)
        worlds = []
        for world in findall(WORLD_FORMAT, cmd):
            world = world.named
            world["name"] = world["name"].rstrip()
            worlds.append(world)

        return worlds

    def focus(self, world_name_or_number: Union[str, int]):
        """
        Switch focus to another world.

        Returns nothing on success, or raises `NeosError` on error.
        """
        # This command prints nothing on a successful switch.
        try:
            world_number = int(world_name_or_number)
            cmd = self.send_command("focus %d" % world_number)
        except ValueError:
            cmd = self.send_command('focus "%s"' % world_name_or_number)
        errors = ["World index out of range", "World with this name does not exist"]
        for ln in cmd:
            if ln in errors:
                raise NeosError(ln)

    # TODO: Implement `startWorldURL` here
    def start_world_url(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    def start_world_template(self, world_template: str):
        """
        Start a wolrd based on a given world template name

        Return nothing on success

        Raise `NeosError` if the world template name is invalid
        Raise `UnhandledError` for any unknown errors
        """
        templates_name = [
            "SpaceWorld",
            "Basic Empty",
            "GridSpace",
            "Microworld",
            "Testing Scaling",
            "ScratchSpace",
            "ScratchSpace (mobile)",
        ]
        if not world_template not in templates_name:
            raise NeosError(
                'Invalid preset name. Choose between: %s' % ', '.join(
                    templates_name
                )
            )
        cmd = self.send_command('startWorldTemplate  "%s"' % (world_template))
        errors = ['Invalid preset name']
        for ln in cmd:
            if ln == "World running...":
                return
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def status(self, world: Union[str, int] = None) -> dict:
        """
        Shows the status of the current world, or `world` if it is specified.
        `world` can be a world index, world name, or session ID.

        Returns a `dict` with the following keys:

        - **name**: `str`
          - The name of the session or world
        - **session_id**: `str`
          - The session ID, including the `S-` prefix
        - **current_users**: `int`
          - How many users are *connected* to the session
        - **present_users**: `int`
          - How many users are *present* in the session
        - **max_users**: `int`
          - The maximum number of users allowed to connect
        - **uptime**: `str`
          - Session uptime as returned by the headless client
            Ex. `00:42:54.4241170`
        - **access_level**: `str`
          - The access level setting of the session.
            Ex. "Anyone" or "Friends"
        - **hidden_from_listing**: `bool`
          - Whether this session is displayed in the public world listing
        - **mobile_friendly**: `bool`
          - Whether this session is marked as being "mobile friendly"
        - **description**: `str`
          - A description of the session or world
        - **tags**: `list[str]`
          - A list of tags for the current world
        - **users**: `list[str]`
          - A list of usernames connected to the session (**without** the `U-` prefix)
        """
        cmd = self.send_command("status", world=world)

        format_status_mapping = [
            (STATUS_SESSION_ID_FORMAT, "session_id"),
            (STATUS_CURRENT_USERS_FORMAT, "current_users"),
            (STATUS_PRESENT_USERS_FORMAT, "present_users"),
            (STATUS_MAX_USERS_FORMAT, "max_users"),
            (STATUS_UPTIME_FORMAT, "uptime"),
            (STATUS_ACCESS_LEVEL_FORMAT, "access_level"),
            (STATUS_HIDDEN_FROM_LISTING_FORMAT, "hidden_from_listing"),
            (STATUS_MOBILE_FRIENDLY_FORMAT, "mobile_friendly"),
            (STATUS_USERS_FORMAT, "users"),
        ]

        status = {}
        for ln in cmd:
            # Parse the world name. This should catch almost any name: Normal
            # world names, world names with XML formatting, world names that are
            # multiple lines, and even world names that are blank.
            # Known bug: World names with any line ending with a ">" character
            # should be avoided, as this interferes with prompt detection.
            if ln.startswith("Name: "):
                name = ln.split(": ")[1]
                # Set name to `None` if the world name is empty.
                if name == "":
                    status["name"] = None
                    continue
                # Ignore any errors that may have been printed to the console by
                # finding out what line the world name is on, and cutting off
                # everything else before it. This is a Neos bug.
                # See: https://github.com/Neos-Metaverse/NeosPublic/issues/2436
                name_index = cmd.index(ln)
                # Put everything back together, to catch multi-line names.
                trimmed_cmd = "\n".join(cmd[name_index:])
                # Finally, pull out the world name.
                status["name"] = parse(STATUS_NAME_FORMAT, trimmed_cmd)[0]

            # Parse everything else, except for the if-statements below this.
            for i, j in format_status_mapping:
                fmt = parse(i, ln)
                if fmt:
                    status[j] = fmt[0]
                    break

            # Parse the description. It could be empty, or could be multi-line.
            if ln.startswith("Description: "):
                description = ln.split(": ")[1]
                # Set description to `None` if the description is empty.
                if description == "":
                    status["description"] = None
                    continue
                # Remove all lines before the description, so that it lines up
                # with the parsing string.
                description_index = cmd.index(ln)
                trimmed_cmd = "\n".join(cmd[description_index:])
                status["description"] = parse(STATUS_DESCRIPTION_FORMAT, trimmed_cmd)[0]

            # Parse tags. It could be empty, or a comma-delimited list.
            if ln.startswith("Tags: "):
                tags = ln.split(": ")[1]
                if tags == "":  # No tags
                    status["tags"] = []
                    continue
                status["tags"] = parse(STATUS_TAGS_FORMAT, ln)[0].split(", ")

        # Finally, some type conversions.

        status["hidden_from_listing"] = (
            True if status["hidden_from_listing"] == "True" else False
        )
        status["mobile_friendly"] = (
            True if status["mobile_friendly"] == "True" else False
        )
        status["users"] = status["users"].split(", ")

        return status

    def session_url(self, world: Union[str, int] = None) -> str:
        """
        Returns the URL of the current session or specified `world`.

        `world` can be a world index, world name, or session ID.
        """
        cmd = self.send_command("sessionurl", world=world)
        for ln in cmd:
            if ln.startswith("http"):
                return ln
        raise UnhandledError("\n".join(cmd))

    def session_id(self, world: Union[str, int] = None) -> str:
        """
        Returns the ID of the current session or specified `world`.

        `world` can be a world index, world name, or session ID.
        """
        cmd = self.send_command("sessionid", world=world)
        for ln in cmd:
            if ln.startswith("S-"):
                return ln
        raise UnhandledError("\n".join(cmd))

    # `copySessionURL` is not supported.
    # `copySessionID` is not supported.

    def users(self, world: Union[str, int] = None) -> list[dict]:
        """
        Lists all users in the current world, or `world` if specified.
        `world` can be a world index, world name, or session ID.
        Returns a `list` of `dict`.

        The user listing includes the headless user hosting the session.

        Each `dict` corresponds to a user with the following keys:

        - **name**: `str`
          - The name of the user
        - **user_id**: `str` or None
          - The user ID of the user
          - There is a special case for the headless user. Its user ID is always `None`.
        - **role**: `str`
          - The current role or permission level of the user. Ex. "Admin" or "Builder"
        - **present**: `bool`
          - Whether the user is present in the world
        - **ping**: `int`
          - The user's current ping, in milliseconds
        - **fps**: `float`
          - The user's current FPS
        - **silenced**: `bool`
          - Whether the user is currently silenced
        """
        cmd = self.send_command("users", world=world)

        users = []
        for ln in cmd:
            user = parse(USER_FORMAT, ln)
            if user == None:  # Invalid output
                continue
            user = user.named
            # Check if a user has a user ID and set it to `None` if they don't.
            # This should only happen for the headless user if it is not logged
            # into a Neos account.
            user_id = user["user_id"].lstrip()
            if user_id == "":
                user["user_id"] = None
            else:
                user["user_id"] = user_id
            user["present"] = True if user["present"] == "True" else False
            if user["fps"].is_integer():
                user["fps"] = int(user["fps"])
            user["silenced"] = True if user["silenced"] == "True" else False
            users.append(user)

        return users

    def close(self, world: Union[str, int] = None):
        """
        Closes the currently focused world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns nothing on success.
        """
        # This command doesn't print anything, so there's nothing to return.
        self.send_command("close", world=world)

    def save(self, world: Union[str, int] = None) -> str:
        """
        Saves the currently focused world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns the success message.

        **TODO:** Needs to be tested with cloud saved worlds.
        """
        # TODO: See if this still works if world is saved to cloud.
        cmd = self.send_command("save", world=world)
        for ln in cmd:
            if ln == "World saved!":
                return ln
        raise UnhandledError("\n".join(cmd))

    def restart(self, world: Union[str, int] = None):
        """
        Restarts the current world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        **NOTE:** This is currently not implemented due to a bug in the headless
        client. Calling this function will raise an exception. For info, see:
        https://github.com/Neos-Metaverse/NeosPublic/issues/1841
        """
        # cmd = self.send_command("restart", world=world)
        raise NotImplementedError(
            "Restarting is temporarily disabled due to a headless client bug. "
            "See https://github.com/Neos-Metaverse/NeosPublic/issues/1841 "
            "for more information."
        )

    def kick(self, username: str, world: Union[str, int] = None) -> str:
        """
        Kicks given user from the session, or from `world` if it is specified.
        `world` can be a world index, world name, or session ID.

        Returns the success message, or raises `NeosError` if the user wasn't found.
        """
        cmd = self.send_command('kick "%s"' % username, world=world)
        for ln in cmd:
            if ln.endswith("kicked!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def silence(self, username: str, world: Union[str, int] = None) -> str:
        """
        Silences given user in the session, or from `world` if it is specified.
        `world` can be a world index, world name, or session ID.

        Returns the success message, or raises `NeosError` if the user wasn't found.
        """
        cmd = self.send_command('silence "%s"' % username, world=world)
        for ln in cmd:
            if ln.endswith("silenced!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def unsilence(self, username: str, world: Union[str, int] = None) -> str:
        """
        Removes silence from given user in the session, or from `world` if it is specified.
        `world` can be a world index, world name, or session ID.

        Returns the success message, or raises `NeosError` if the user wasn't found.
        """
        cmd = self.send_command('unsilence "%s"' % username, world=world)
        for ln in cmd:
            if ln.endswith("unsilenced!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def ban(self, username: str, world: Union[str, int] = None) -> str:
        """
        Bans the user in this session (or in `world` if specified) from all sessions
        hosted by this server, then kicks them. `world` can be a world index, world name,
        or session ID.

        Returns the success message, or raises `NeosError` if the user wasn't found.
        """
        cmd = self.send_command('ban "%s"' % username, world=world)
        for ln in cmd:
            if ln.endswith("banned!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def unban(self, username: str) -> str:
        """
        Removes ban for user with given username.

        Returns the success message, or raises `NeosError` if the user wasn't found.
        """
        cmd = self.send_command('unban "%s"' % username)
        for ln in cmd:
            if ln == "Ban removed!":
                return ln
            elif ln.startswith("No ban with given username found."):
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def list_bans(self) -> list[dict]:
        """
        Lists all active bans. Returns a `list` of `dict`.

        Each `dict` corresponds to a banned user and has the following keys:

        - **name**: `str`
          - The name of the banned user
        - **user_id**: `str`
          - The user ID of the banned user
        - **machine_id**: `str`
          - The machine ID of the banned user, if applicable
          - This value may be "N/A" if the machine ID was not known at the time of the ban.
        """
        cmd = self.send_command("listbans")
        bans = []
        for ln in cmd:
            banned = parse(BAN_FORMAT, ln)
            if banned == None:  # Invalid output
                continue
            bans.append(banned.named)
        return bans

    def ban_by_name(self, neos_username: str) -> str:
        """
        Bans user with given Neos username from all sessions hosted by this server.

        Returns the success message, or raises `NeosError` if there was a problem.
        """
        cmd = self.send_command('banbyname "%s"' % neos_username)
        errors = ["User not found", "Already banned"]
        for ln in cmd:
            if ln == "User banned":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def unban_by_name(self, neos_username: str) -> str:
        """
        Unbans user with given Neos username from all sessions hosted by this server.

        Returns the success message, or raises `NeosError` if the user wasn't found.
        """
        cmd = self.send_command('unbanbyname "%s"' % neos_username)
        for ln in cmd:
            if ln == "Ban removed":
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def ban_by_id(self, user_id: str) -> str:
        """
        Bans user with given Neos User ID from all sessions hosted by this server.

        Returns the success message, or raises `NeosError` if there was a problem.
        """
        cmd = self.send_command('banbyid "%s"' % user_id)
        errors = ["User not found", "Already banned"]
        for ln in cmd:
            if ln == "User banned":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def unban_by_id(self, user_id: str) -> str:
        """
        Unbans user with given Neos User ID from all sessions hosted by this server.

        Returns the success message, or raises `NeosError` if the user wasn't found.
        """
        cmd = self.send_command('unbanbyid "%s"' % user_id)
        for ln in cmd:
            if ln == "Ban removed":
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def respawn(self, username: str, world: Union[str, int] = None) -> str:
        """
        Respawns given user in the current world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns the success message, or raises `NeosError` if the user wasn't found.
        """
        cmd = self.send_command('respawn "%s"' % username, world=world)
        for ln in cmd:
            if ln.endswith("respawned!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def role(self, username: str, role: str, world: Union[str, int] = None) -> str:
        """
        Assigns a role to given user in this world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns the success message, or raises `NeosError` if the user or role wasn't found.
        """
        cmd = self.send_command('role "%s" "%s"' % (username, role), world=world)
        for ln in cmd:
            if " now has role " in ln and ln.endswith("!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
            elif ln.startswith("Role ") and ln.endswith("isn't available"):
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def name(self, new_name: str, world: Union[str, int] = None):
        """
        Sets a new world name for the current world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns nothing on success.
        """
        # Command prints nothing on success. Nothing to return.
        self.send_command('name "%s"' % new_name, world=world)

    def access_level(
        self, access_level_name: str, world: Union[str, int] = None
    ) -> str:
        """
        Set the access level of the currently focused world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns the success message, or raises `NeosError` is the access level is invalid.
        """
        cmd = self.send_command('accesslevel "%s"' % access_level_name, world=world)
        for ln in cmd:
            if ln.startswith("World ") and " now has access level " in ln:
                return ln
            elif ln.startswith("Invalid access level."):
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def hide_from_listing(self, true_false: bool, world: Union[str, int] = None) -> str:
        """
        Hide or unhide the currently focused world from public listing, or hide/unhide
        `world` if it is given. `world` can be a world index, world name, or session ID.

        Returns the success message, or raises `NeosError` if a non-boolean value is given.
        """
        cmd = self.send_command(
            'hidefromlisting "%s"' % str(true_false).lower(), world=world
        )
        for ln in cmd:
            if ln.endswith("listing") and (
                " now hidden from " in ln or " will now show in " in ln
            ):
                return ln
            elif ln == "Invalid value. Must be either true or false":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def description(self, new_description: str, world: Union[str, int] = None):
        """
        Sets a new world description for the current world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns nothing on success.
        """
        # Command prints nothing on success. Nothing to return.
        self.send_command('description "%s"' % new_description, world=world)

    def max_users(self, max_users: int, world: Union[str, int] = None):
        """
        Sets user limit for the current world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns nothing on success, but raises `NeosError` if the number is out of range.
        """
        # Nothing printed on command success.
        cmd = self.send_command('maxusers "%s"' % max_users, world=world)
        for ln in cmd:
            if ln == "Invalid number. Must be within 1 and 256":
                raise NeosError(ln)

    def away_kick_interval(
        self, interval_in_minutes: int, world: Union[str, int] = None
    ):
        """
        Sets the away kick interval for the current world, or `world` if it is given.
        `world` can be a world index, world name, or session ID.

        Returns nothing on success, but raises `NeosError` if the number is invalid.
        """
        # Nothing printed on command success.
        cmd = self.send_command(
            'awaykickinterval "%s"' % interval_in_minutes, world=world
        )
        for ln in cmd:
            if ln == "Invalid number":
                raise NeosError(ln)

    # TODO: Implement `import` here
    def import_(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    # TODO: Implement `importMinecraft` here
    def import_minecraft(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    # TODO: Implement `dynamicImpulse` here
    def dymanic_impulse(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    # TODO: Implement `dynamicImpulseString` here
    def dynamic_impulse_string(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    # TODO: Implement `dynamicImpulseInt` here
    def dynamic_impulse_int(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    # TODO: Implement `dynamicImpulseFloat` here
    def dynamic_impulse_float(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    # TODO: Implement `spawn` here
    def spawn(self, *args, **kwargs):
        """
        Not yet implemented

        Raises `NotImplementedError`
        """
        raise NotImplementedError("Not yet implemented")

    def gc(self) -> str:
        """Forces full garbage collection. Returns the success message."""
        cmd = self.send_command("gc")
        for ln in cmd:
            if ln == "GC finished":
                return ln
        raise UnhandledError("\n".join(cmd))

    def shutdown(self):
        """
        Shuts down the headless client.

        This is an implementation-specific function, so it is overridden by
        the `LocalHeadlessClient` and `RemoteHeadlessClient` subclasses.
        """
        pass

    def tick_rate(self, ticks_per_second: int) -> str:
        """
        Sets the maximum simulation rate for the servers.

        Returns the success message, or raises `NeosError` if the number is invalid.
        """
        cmd = self.send_command('tickrate "%s"' % ticks_per_second)
        for ln in cmd:
            if ln == "Tick Rate Set!":
                return ln
            elif ln == "Invalid number":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    # `log` is not supported.

    # END HEADLESS CLIENT COMMANDS


class LocalHeadlessClient(HeadlessClient):
    """
    Class representing a locally running headless client. Methods overridden
    here relate to control of the headless client process itself. See
    `HeadlessClient` for documentation on Neos console commands/functions.
    """

    def __init__(self, neos_dir: str, config: str = None):
        """
        Start a headless client on the local machine. `neos_dir` must be the
        directory to the headless client software, containing `Neos.exe`. Make
        sure that you have the correct version of Mono installed as well.

        Optionally specify `config` as a path to a configuration JSON file for
        the headless client to use. If this is not provided, Neos will use the
        default one instead in `Config/Config.json`, or if that does not exist,
        it will run with a completely default config.
        """
        self.process = HeadlessProcess(neos_dir, config=config)
        super().__init__(neos_dir, config)

    def shutdown(self, timeout: int = None, wait: bool = True) -> int:
        """
        Shut down the headless client using the "shutdown" command. If `wait` is
        `True`, wait up to `timeout` seconds for the process to exit and return
        the exit code. If the process doesn't exit in time, a `TimeoutExpired`
        exception is raised.
        """
        return self.process.shutdown(timeout=timeout, wait=wait)

    def sigint(self, timeout: int = None, wait: bool = True) -> int:
        """
        Send a SIGINT to the headless client, same as pressing Ctrl+C.
        If `wait` is `True`, block until the process exits and return the exit
        code. If `timeout` is specified, raise a `TimeoutExpired` exception if
        the process doesn't exit in time. Should close the client cleanly.
        """
        return self.process.sigint(timeout=timeout, wait=wait)

    def terminate(self, timeout: int = None, wait: bool = True) -> int:
        """
        Send a SIGTERM to the headless client, politely asking it to close.
        If `wait` is `True`, block until the process exits and return the exit
        code. If `timeout` is specified, raise a `TimeoutExpired` exception if
        the process doesn't exit in time. May not properly close on Linux.
        """
        return self.process.terminate(timeout=timeout, wait=wait)

    def kill(self, timeout: int = None, wait: bool = True) -> int:
        """
        Send a SIGKILL to the headless client, immediately force closing it.
        If `wait` is `True`, block until the process exits and return the exit
        code. If `timeout` is specified, raise a `TimeoutExpired` exception if
        the process doesn't exit in time. This should be a last resort option.
        """
        return self.process.kill(timeout=timeout, wait=wait)


class RemoteHeadlessClient(HeadlessClient):
    """
    Start a headless client on a remote machine, by connecting to an RPC server
    (included in this package as `rpc_server.py`) and interacting with a remote
    headless client object as if it were local. When passing `neos_dir` and `config`
    arguments, these directories and files **must** already exist on the destination
    side. Files do not get copied over upon connecting.
    """

    def __init__(self, host: str, port: int, neos_dir: str, config: str = None):
        # This import is here to effectively make `rpyc` an optional dependency.
        from rpyc import connect, core

        _gec = core.vinegar._generic_exceptions_cache
        _gec["neosvr_headless_api.CommandTimeout"] = CommandTimeout
        self.host, self.port = host, port
        self.connection = connect(
            host, port, config={"sync_request_timeout": SYNC_REQUEST_TIMEOUT}
        )
        self.remote_pid, self.process = self.connection.root.start_headless_process(
            neos_dir, config
        )
        super().__init__(neos_dir, config)

    def shutdown(self) -> int:
        """Shut down the headless client."""
        return self.connection.root.stop_headless_process(self.remote_pid)

    def sigint(self) -> int:
        """
        Send a SIGINT to the headless client, same as pressing Ctrl+C.
        """
        return self.connection.root.send_signal_headless_process(self.remote_pid, 2)

    def terminate(self) -> int:
        """
        Send a SIGTERM to the headless client, politely asking it to close.
        """
        return self.connection.root.send_signal_headless_process(self.remote_pid, 15)

    def kill(self) -> int:
        """
        Send a SIGKILL to the headless client, immediately force closing it.
        """
        return self.connection.root.send_signal_headless_process(self.remote_pid, 9)


class HeadlessProcess:
    """
    Handles direct control of the NeosVR headless client. This class is not
    intended to be used directly. `HeadlessClient` should be used instead.
    """

    def __init__(self, neos_dir, config=None):
        self.neos_dir = neos_dir

        # If no configuration file is specified, then Neos will load it from its
        # default location at "Config/Config.json" (relative to the directory
        # Neos is running from). However, if this file does not exist, Neos will
        # run using all default values without creating a configuration file.
        # For the former case, `config` is set to the absolute path of this
        # configuration file. For the latter, `config` is left at `None`.
        self.args = ["mono", "Neos.exe"]  # TODO: Windows doesn't use Mono.
        if config:
            if not path.exists(config):
                raise FileNotFoundError('Configuration file not found: "%s"' % config)
            self.config = config
            self.args.extend(["--config", config])
        else:
            dft_loc = path.join(neos_dir, "Config", "Config.json")
            if path.exists(dft_loc):
                self.config = dft_loc
            else:
                self.config = None

        self.process = Popen(
            self.args,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            bufsize=0,  # Unbuffered
            cwd=self.neos_dir,
        )
        self.running = True

        self._stdin_queue = Queue()
        self._stdout_queue = Queue()
        self._stderr_queue = Queue()

        self._threads = [
            Thread(target=self._stdin_writer),
            Thread(target=self._stdout_reader),
            Thread(target=self._stderr_reader),
        ]

        for thread in self._threads:
            thread.daemon = True  # TODO: Does this need to be a daemon thread?
            thread.start()

    def write(self, data):
        """Write `data` to the process's stdin."""
        self._stdin_queue.put(data)

    def readline(self, timeout=None):
        """
        Read a line from the process's stdout. Optionally wait up to `timeout`
        seconds and if there is no line to be read, raise `CommandTimeout`.
        """
        try:
            res = self._stdout_queue.get(timeout=timeout)
            self._stdout_queue.task_done()
        except Empty:
            raise CommandTimeout("Command didn't complete within %d seconds" % timeout)
        return res

    def shutdown(self, timeout=None, wait=True):
        """
        Shut down the headless client by sending the "shutdown" command. If
        `wait` is `True`, block until the process exits and returns the exit
        code. You can specify `timeout` to wait up to a number of seconds for
        the process to exit, else `TimeoutExpired` will be raised. `timeout` has
        no effect if `wait` is `False`.
        """
        self.write("shutdown\n")
        if wait:
            return self.wait(timeout=timeout)

    def sigint(self, timeout=None, wait=True):
        """
        Send a SIGINT (2) signal to the process, i.e. Ctrl+C.
        If `wait` is `True` and `timeout` is not `None`, block and wait up to
        `timeout` seconds for the process to exit and return the exit code,
        otherwise `TimeoutExpired` will be raised. `timeout` has no effect if
        `wait` is `False`.
        """
        self.process.send_signal(2)
        if wait:
            return self.wait(timeout=timeout)

    def terminate(self, timeout=None, wait=True):
        """
        Send a SIGTERM (15) signal to the process.
        If `wait` is `True` and `timeout` is not `None`, block and wait up to
        `timeout` seconds for the process to exit and return the exit code,
        otherwise `TimeoutExpired` will be raised. `timeout` has no effect if
        `wait` is `False`.
        """
        self.process.terminate()
        if wait:
            return self.wait(timeout=timeout)

    def kill(self, timeout=None, wait=True):
        """
        Send a SIGKILL (9) signal to the process.
        If `wait` is `True` and `timeout` is not `None`, block and wait up to
        `timeout` seconds for the process to exit and return the exit code,
        otherwise `TimeoutExpired` will be raised. `timeout` has no effect if
        `wait` is `False`.
        """
        # NOTE: It's probably not be necessary to "wait" for a SIGKILL since it
        # should be immediate, but it's here anyway for consistency.
        self.process.kill()
        if wait:
            return self.wait(timeout=timeout)

    def wait(self, timeout=None):
        """
        Alias for `self.process.wait()`
        Block until the process exits and return the exit code. If `timeout` is
        not `None`, wait up to `timeout` seconds, otherwise `TimeoutExpired`
        will be raised.
        """
        return self.process.wait(timeout=timeout)

    def _stdin_writer(self):
        while True:
            try:
                cmd = self._stdin_queue.get(timeout=0.5)
            except Empty:
                if self.running:
                    continue
                else:
                    break
            self.process.stdin.write(cmd.encode("utf8"))
            self._stdin_queue.task_done()

    def _stdout_reader(self):
        line_buffer = ""
        while True:
            data = self.process.stdout.read(4096).decode("utf8")
            if data == "":
                # Stream has ended, trigger shutdown of other threads.
                self.running = False
                break
            lines = (line_buffer + data).split("\n")
            line_buffer = ""

            if lines[-1] == "":
                lines.pop()
            elif not lines[-1].endswith(">"):
                line_buffer = lines.pop()

            for ln in lines:
                self._stdout_queue.put(ln)

    def _stderr_reader(self):
        line_buffer = ""
        while True:
            data = self.process.stderr.read(4096).decode("utf8")
            if data == "":
                break
            lines = (line_buffer + data).split("\n")
            line_buffer = ""

            if lines[-1] == "":
                lines.pop()
            else:
                line_buffer = lines.pop()

            for ln in lines:
                self._stderr_queue.put(ln)


class HeadlessCommand:
    """
    Represents a headless client command and its eventual corresponding output.
    This class may seem like a stripped down version of a "future", but its only
    purpose is to keep the output of a command tied to the command that produced
    it, without having to maintain synced lists/queues for both input and
    output. This is used internally in the command queue to ensure commands are
    executing synchronously and in chronological order of submission. There is
    no need to use it directly for anything.

    If `world` is set, the command queue processing thread will try to focus or
    "switch" to a different world immediately before executing the command. If
    the specified world doesn't exist, the command will not execute.
    """

    def __init__(self, cmd, world=None):
        self.cmd = cmd
        self.world = world
        self._result = None
        self._complete = Event()

    def set_result(self, result):
        self._result = result
        self._complete.set()

    def result(self, timeout=None):
        self._complete.wait(timeout=timeout)
        return self._result


class NeosError(Exception):
    """
    Raised when a "soft" error message is printed to the headless client console
    as a direct result of a command being executed, such as "User not found" or
    "World with this name does not exist".
    """

    pass


class UnhandledError(Exception):
    """
    Raised when a command produces an error that is not accounted for in this
    API. The full output of the command is passed as the exception message. Note
    that this could contain log messages, and consequently data such as IP
    addresses, so be aware of this if you are going to forward these messages to
    an end user. If an error raises this exception that you feel should raise a
    `NeosError` exception instead, feel free to open an issue or submit a pull
    request to have it implemented.
    """

    pass


class CommandTimeout(Exception):
    """
    Raised when a command takes too long to return any output. If this is raised
    multiple times in a row, the headless client may be frozen.
    NOTE: The headless client itself doesn't have a concept of "command
    timeouts" so this exception is more so an indicator of the headless client
    not responding. 20-25 seconds is the recommended timeout period. Commands do
    take upwards of 10 seconds to complete sometimes when the headless client is
    under heavy load, but any more than that and it should be assumed the
    headless client is unresponsive and may not be recoverable.
    """

    pass


class HeadlessNotReady(Exception):
    """
    Raised when a command is attempted to be executed before the headless
    client has fully finished starting up. Use `wait_for_ready()` to block until
    the headless client is ready to accept commands.
    """

    pass


__all__ = [
    LocalHeadlessClient,
    RemoteHeadlessClient,
    HeadlessClient,
    NeosError,
    UnhandledError,
    CommandTimeout,
    HeadlessNotReady,
]
