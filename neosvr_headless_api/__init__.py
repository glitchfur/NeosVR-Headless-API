# NeosVR-Headless-API
# Glitch, 2021

# KNOWN BUGS:

# World names that have any line ending with a ">" character will trip up the
# prompt detector and cause undesirable behavior, particularly when running the
# `status` command. Avoid using world names that fit this criteria.
# Specifically, be careful when using text formatting in world names.

# TODOS:

# Check if no world is currently focused. Could affect all commands.

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
        self.args = ["mono", "Neos.exe"] # TODO: Windows doesn't use Mono.
        if config:
            if not path.exists(config):
                raise FileNotFoundError(
                    "Configuration file not found: \"%s\"" % config)
            self.config = config
            self.args.extend(["--config", config])
        else:
            dft_loc = path.join(neos_dir, "Config", "Config.json")
            if path.exists(dft_loc):
                self.config = dft_loc
            else:
                self.config = None

        self.process = Popen(self.args,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            bufsize=0, # Unbuffered
            cwd=self.neos_dir
        )
        self.running = True

        self._stdin_queue = Queue()
        self._stdout_queue = Queue()
        self._stderr_queue = Queue()

        self._threads = [
            Thread(target=self._stdin_writer),
            Thread(target=self._stdout_reader),
            Thread(target=self._stderr_reader)
        ]

        for thread in self._threads:
            thread.daemon = True # TODO: Does this need to be a daemon thread?
            thread.start()

    def write(self, data):
        """Write `data` to the process's stdin."""
        self._stdin_queue.put(data)

    def readline(self):
        """Read a line from the process's stdout."""
        res = self._stdout_queue.get()
        self._stdout_queue.task_done()
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
                cmd = self._stdin_queue.get(timeout=.5)
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

class HeadlessClient:
    """
    High-level API to the NeosVR headless client. Functions exist for most
    commands and the output will be parsed and returned as Python objects.
    """
    def __init__(self, neos_dir, config=None):
        try:
            self.process
        except AttributeError:
            raise RuntimeError("Please use either `LocalHeadlessClient` or "
                "`RemoteHeadlessClient` instead.")
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
            # TODO: This loop will never end if there are no worlds enabled
            # in the configuration file.
            almost_ready = False
            while True:
                ln = self.process.readline()
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
                    self.process.write("focus \"%s\"\n" % hcmd.world)

                errors = [
                    "World with this name does not exist",
                    "World index out of range"
                ]

                while True:
                    ln = self.process.readline()
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

            self.process.write("%s\n" % hcmd.cmd)
            res = []
            while True:
                ln = self.process.readline()
                if ln.endswith(">"):
                    break
                res.append(ln)
            hcmd.set_result(res)
            self.command_queue.task_done()

    def is_ready(self):
        """
        Returns `True` if the headless client is ready to accept commands.
        Otherwise returns `False`. Alias for `self.ready.is_set()`
        """
        return self.ready.is_set()

    def wait_for_ready(self, timeout=None):
        """
        Block until the headless client is ready to accept commands. Returns
        `True` when ready. If `timeout` is specified and the headless client
        takes longer than `timeout` seconds to become ready, returns `False`.
        """
        return self.ready.wait(timeout=timeout)

    def wait_for_shutdown(self, timeout=None):
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

    def send_command(self, cmd, world=None):
        """Sends a command to the console, returns the output."""
        if not self.is_ready():
            raise HeadlessNotReady("The headless client is still starting up.")
        hcmd = HeadlessCommand(cmd, world=world)
        self.command_queue.put(hcmd)
        # This will block until it is this command's turn in the queue, and it
        # will return the result as soon as it is available.
        # See the `HeadlessCommand` class for more info.
        result = hcmd.result()
        if isinstance(result, NeosError):
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

    def login(self, username_or_email, password):
        """Log into a Neos account"""
        cmd = self.send_command("login \"%s\" \"%s\"" %
            (username_or_email, password))
        errors = [
            "Invalid credentials",
            "Already logged in!"
        ]
        for ln in cmd:
            if ln == "Logged in successfully!":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def logout(self):
        """Log out from the current Neos account"""
        cmd = self.send_command("logout")
        for ln in cmd:
            if ln == "Logged out!":
                return ln
            elif ln == "Not logged in!":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def message(self, friend_name, message):
        """Message user in friends list"""
        cmd = self.send_command(
            "message \"%s\" \"%s\"" % (friend_name, message))
        errors = [
            "No friend with this username",
            "Not logged in!"
        ]
        for ln in cmd:
            if ln == "Message sent!":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def invite(self, friend_name, world=None):
        """Invite a friend to the currently focused world"""
        cmd = self.send_command("invite \"%s\"" % friend_name, world=world)
        errors = [
            "No friend with this username",
            "Not logged in!"
        ]
        for ln in cmd:
            if ln == "Invite sent!":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    # TODO: Implement `friendRequests` here
    # TODO: Implement `acceptFriendRequest` here

    def worlds(self):
        """Lists all active worlds"""
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

    def focus(self, world_name_or_number):
        """Focus world"""
        # This command prints nothing on a successful switch.
        try:
            world_number = int(world_name_or_number)
            cmd = self.send_command("focus %d" % world_number)
        except ValueError:
            cmd = self.send_command("focus \"%s\"" % world_name_or_number)
        errors = [
            "World index out of range",
            "World with this name does not exist"
        ]
        for ln in cmd:
            if ln in errors:
                raise NeosError(ln)

    # TODO: Implement `startWorldURL` here
    # TODO: Implement `startWorldTemplate` here

    def status(self, world=None):
        """Shows the status of the current world"""
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
            (STATUS_USERS_FORMAT, "users")
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
                status["description"] = parse(
                    STATUS_DESCRIPTION_FORMAT,
                    trimmed_cmd
                )[0]

            # Parse tags. It could be empty, or a comma-delimited list.
            if ln.startswith("Tags: "):
                tags = ln.split(": ")[1]
                if tags == "": # No tags
                    status["tags"] = []
                    continue
                status["tags"] = parse(STATUS_TAGS_FORMAT, ln)[0].split(", ")

        # Finally, some type conversions.

        status["hidden_from_listing"] = \
            True if status["hidden_from_listing"] == "True" else False
        status["mobile_friendly"] = \
            True if status["mobile_friendly"] == "True" else False
        status["users"] = status["users"].split(", ")

        return status

    def session_url(self, world=None):
        """Prints the URL of the current session"""
        cmd = self.send_command("sessionurl", world=world)
        for ln in cmd:
            if ln.startswith("http"):
                return ln
        raise UnhandledError("\n".join(cmd))

    def session_id(self, world=None):
        """Prints the ID of the current session"""
        cmd = self.send_command("sessionid", world=world)
        for ln in cmd:
            if ln.startswith("S-"):
                return ln
        raise UnhandledError("\n".join(cmd))

    # `copySessionURL` is not supported.
    # `copySessionID` is not supported.

    def users(self, world=None):
        """Lists all users in the world"""
        cmd = self.send_command("users", world=world)

        users = []
        for ln in cmd:
            user = parse(USER_FORMAT, ln)
            if user == None: # Invalid output
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
            users.append(user)

        return users

    def close(self, world=None):
        """Closes the currently focused world"""
        # This command doesn't print anything, so there's nothing to return.
        self.send_command("close", world=world)

    def save(self, world=None):
        """Saves the currently focused world"""
        # TODO: See if this still works if world is saved to cloud.
        cmd = self.send_command("save", world=world)
        for ln in cmd:
            if ln == "World saved!":
                return ln
        raise UnhandledError("\n".join(cmd))

    def restart(self, world=None):
        """
        Restarts the current world

        NOTE: This is currently not implemented due to a bug in the headless
        client. Calling this function will raise an exception. For info, see:
        https://github.com/Neos-Metaverse/NeosPublic/issues/1841
        """
        # cmd = self.send_command("restart", world=world)
        raise NotImplementedError(
            "Restarting is temporarily disabled due to a headless client bug. "
            "See https://github.com/Neos-Metaverse/NeosPublic/issues/1841 "
            "for more information.")

    def kick(self, username, world=None):
        """Kicks given user from the session"""
        cmd = self.send_command("kick \"%s\"" % username, world=world)
        for ln in cmd:
            if ln.endswith("kicked!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def silence(self, username, world=None):
        """Silences given user in the session"""
        cmd = self.send_command("silence \"%s\"" % username, world=world)
        for ln in cmd:
            if ln.endswith("silenced!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def unsilence(self, username, world=None):
        """Removes silence from given user in the session"""
        cmd = self.send_command("unsilence \"%s\"" % username, world=world)
        for ln in cmd:
            if ln.endswith("unsilenced!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def ban(self, username, world=None):
        """Bans the user from all sessions hosted by this server"""
        cmd = self.send_command("ban \"%s\"" % username, world=world)
        for ln in cmd:
            if ln.endswith("banned!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def unban(self, username):
        """Removes ban for user with given username"""
        cmd = self.send_command("unban \"%s\"" % username)
        for ln in cmd:
            if ln == "Ban removed!":
                return ln
            elif ln.startswith("No ban with given username found."):
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def list_bans(self):
        """Lists all active bans"""
        cmd = self.send_command("listbans")
        bans = []
        for ln in cmd:
            banned = parse(BAN_FORMAT, ln)
            if banned == None: # Invalid output
                continue
            bans.append(banned.named)
        return bans

    def ban_by_name(self, neos_username):
        """
        Bans user with given Neos username from
        all sessions hosted by this server
        """
        cmd = self.send_command("banbyname \"%s\"" % neos_username)
        errors = ["User not found", "Already banned"]
        for ln in cmd:
            if ln == "User banned":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def unban_by_name(self, neos_username):
        """
        Unbans user with given Neos username from
        all sessions hosted by this server
        """
        cmd = self.send_command("unbanbyname \"%s\"" % neos_username)
        for ln in cmd:
            if ln == "Ban removed":
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def ban_by_id(self, user_id):
        """
        Bans user with given Neos User ID from
        all sessions hosted by this server
        """
        cmd = self.send_command("banbyid \"%s\"" % user_id)
        errors = ["User not found", "Already banned"]
        for ln in cmd:
            if ln == "User banned":
                return ln
            elif ln in errors:
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def unban_by_id(self, user_id):
        """
        Unbans user with given Neos User ID from
        all sessions hosted by this server
        """
        cmd = self.send_command("unbanbyid \"%s\"" % user_id)
        for ln in cmd:
            if ln == "Ban removed":
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def respawn(self, username, world=None):
        """Respawns given user"""
        cmd = self.send_command("respawn \"%s\"" % username, world=world)
        for ln in cmd:
            if ln.endswith("respawned!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def role(self, username, role, world=None):
        """Assigns a role to given user"""
        cmd = self.send_command(
            "role \"%s\" \"%s\"" % (username, role),
            world=world
        )
        for ln in cmd:
            if " now has role " in ln and ln.endswith("!"):
                return ln
            elif ln == "User not found":
                raise NeosError(ln)
            elif ln.startswith("Role ") and ln.endswith("isn't available"):
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def name(self, new_name, world=None):
        """Sets a new world name"""
        # Command prints nothing on success. Nothing to return.
        self.send_command("name \"%s\"" % new_name, world=world)

    def access_level(self, access_level_name, world=None):
        """Sets a new world access level"""
        cmd = self.send_command(
            "accesslevel \"%s\"" % access_level_name,
            world=world
        )
        for ln in cmd:
            if ln.startswith("World ") and " now has access level " in ln:
                return ln
            elif ln.startswith("Invalid access level."):
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def hide_from_listing(self, true_false, world=None):
        """Sets whether the session should be hidden from listing or not"""
        cmd = self.send_command(
            "hidefromlisting \"%s\"" % str(true_false).lower(),
            world=world
        )
        for ln in cmd:
            if ln.endswith("listing") and \
                (" now hidden from " in ln or " will now show in " in ln):
                return ln
            elif ln == "Invalid value. Must be either true or false":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    def description(self, new_description, world=None):
        """Sets a new world description"""
        # Command prints nothing on success. Nothing to return.
        self.send_command("description \"%s\"" % new_description, world=world)

    def max_users(self, max_users, world=None):
        """Sets user limit"""
        # Nothing printed on command success.
        cmd = self.send_command("maxusers \"%s\"" % max_users, world=world)
        for ln in cmd:
            if ln == "Invalid number. Must be within 1 and 256":
                raise NeosError(ln)

    def away_kick_interval(self, interval_in_minutes, world=None):
        """Sets the away kick interval"""
        # Nothing printed on command success.
        cmd = self.send_command(
            "awaykickinterval \"%s\"" % interval_in_minutes,
            world=world
        )
        for ln in cmd:
            if ln == "Invalid number":
                raise NeosError(ln)

    # TODO: Implement `import` here
    # TODO: Implement `importMinecraft` here
    # TODO: Implement `dynamicImpulse` here
    # TODO: Implement `dynamicImpulseString` here
    # TODO: Implement `dynamicImpulseInt` here
    # TODO: Implement `dynamicImpulseFloat` here
    # TODO: Implement `spawn` here

    def gc(self):
        """Forces full garbage collection"""
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

    def tick_rate(self, ticks_per_second):
        """Sets the maximum simulation rate for the servers"""
        cmd = self.send_command("tickrate \"%s\"" % ticks_per_second)
        for ln in cmd:
            if ln == "Tick Rate Set!":
                return ln
            elif ln == "Invalid number":
                raise NeosError(ln)
        raise UnhandledError("\n".join(cmd))

    # `log` is not supported.

    # END HEADLESS CLIENT COMMANDS

class LocalHeadlessClient(HeadlessClient):
    def __init__(self, neos_dir, config=None):
        self.process = HeadlessProcess(neos_dir, config=config)
        super().__init__(neos_dir, config)

    def shutdown(self, timeout=None, wait=True):
        """
        Shut down the headless client using the "shutdown" command. If `wait` is
        `True`, wait up to `timeout` seconds for the process to exit and return
        the exit code. If the process doesn't exit in time, a `TimeoutExpired`
        exception is raised.
        """
        return self.process.shutdown(timeout=timeout, wait=wait)

    def sigint(self, timeout=None, wait=True):
        """
        Send a SIGINT to the headless client, same as pressing Ctrl+C.
        If `wait` is `True`, block until the process exits and return the exit
        code. If `timeout` is specified, raise a `TimeoutExpired` exception if
        the process doesn't exit in time. Should close the client cleanly.
        """
        return self.process.sigint(timeout=timeout, wait=wait)

    def terminate(self, timeout=None, wait=True):
        """
        Send a SIGTERM to the headless client, politely asking it to close.
        If `wait` is `True`, block until the process exits and return the exit
        code. If `timeout` is specified, raise a `TimeoutExpired` exception if
        the process doesn't exit in time. May not properly close on Linux.
        """
        return self.process.terminate(timeout=timeout, wait=wait)

    def kill(self, timeout=None, wait=True):
        """
        Send a SIGKILL to the headless client, immediately force closing it.
        If `wait` is `True`, block until the process exits and return the exit
        code. If `timeout` is specified, raise a `TimeoutExpired` exception if
        the process doesn't exit in time. This should be a last resort option.
        """
        return self.process.kill(timeout=timeout, wait=wait)

class RemoteHeadlessClient(HeadlessClient):
    def __init__(self, host, port, neos_dir, config=None):
        # This import is here to effectively make `rpyc` an optional dependency.
        from rpyc import connect
        self.host, self.port = host, port
        self.connection = connect(host, port)
        self.remote_pid, self.process = \
            self.connection.root.start_headless_process(neos_dir, config)
        super().__init__(neos_dir, config)

    def shutdown(self):
        """Shut down the headless client."""
        return self.connection.root.stop_headless_process(self.remote_pid)

    def sigint(self):
        """
        Send a SIGINT to the headless client, same as pressing Ctrl+C.
        """
        return self.connection.root.send_signal_headless_process(
            self.remote_pid, 2
        )

    def terminate(self):
        """
        Send a SIGTERM to the headless client, politely asking it to close.
        """
        return self.connection.root.send_signal_headless_process(
            self.remote_pid, 15
        )

    def kill(self):
        """
        Send a SIGKILL to the headless client, immediately force closing it.
        """
        return self.connection.root.send_signal_headless_process(
            self.remote_pid, 9
        )

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

class HeadlessNotReady(Exception):
    """
    Raised when a command is attempted to be executed before the headless
    client has fully finished starting up. Use `wait()` to block until the
    headless client is ready to accept commands.
    """
    pass
