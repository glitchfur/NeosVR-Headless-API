# NeosVR-Headless-API
# Glitch, 2021

# NOTES/GOTCHAS:

# 1. World names can contain newline (\n) characters, and the headless client
# will actually print these and break the line. This can mess up the output of
# any commands that include a world's name, and it even messes up the prompt
# itself. This will need to be carefully handled in the event that it happens.
# 2. On a few occasions I've witnessed the headless client spit out a line or
# two of errors immediately after running a completely unrelated command. It
# seemed like they were world-related, non-fatal errors that were waiting to be
# printed until a command was run. This can make the output of commands
# inconsistent. Very strict parsing rules will have to be put in place to ensure
# that we read only what we want, and nothing that we don't.
# 3. Running commands in very quick succession can make the headless client
# behave as if it's in non-interactive log mode. Particularly, repeatedly
# sending the "users" command and joining a world will print out detailed user
# join information that otherwise would not have been printed, but would show up
# normally if the client was properly put into log mode with the `log` command.
# While it's rare that this could occur, a fix for the previous issue would
# probably fix this one too.

# MISCELLANEOUS NOTES:

# List of valid roles for users:
# Admin, Builder, Moderator, Guest, Spectator

# List of valid access levels for worlds:
# Private, LAN, Friends, FriendsOfFriends, RegisteredUsers, Anyone

# TODOS:

# Handle blank world names.
# Check if no world is currently focused. Could affect all commands.
# Add optional timeout for wait()
# When running commands, funnel unexpected output somewhere to be reviewed
# later as they may be errors.

# TESTING REQUIRED: If there are critical errors and a prompt never comes back,
# Python will hang while waiting to read it. I don't know if this is a situation
# that could occur though. Probably depends on the world.

from threading import Thread, Event
from queue import Queue, Empty
from subprocess import Popen, PIPE
from os import path

from parse import parse, findall

from .response_formats import *

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

    def wait(self):
        """Block until the process exits. Alias for `self.process.wait()`"""
        return self.process.wait()

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
            self.process.write("%s\n" % hcmd.cmd)
            res = []
            while True:
                ln = self.process.readline()
                if ln.endswith(">"):
                    break
                res.append(ln)
            hcmd.set_result(res)
            self.command_queue.task_done()

    def wait(self):
        """Block until the process becomes ready."""
        return self.ready.wait()

    def send_command(self, cmd):
        """Sends a command to the console, returns the output."""
        # TODO: Raise an exception if client is not ready yet.
        hcmd = HeadlessCommand(cmd)
        self.command_queue.put(hcmd)
        # This will block until it is this command's turn in the queue, and it
        # will return the result as soon as it is available.
        # See the `HeadlessCommand` class for more info.
        return hcmd.result()

    # BEGIN HEADLESS CLIENT COMMANDS

    # TODO: Implement `saveConfig` here

    def login(self, username_or_email, password):
        """Log into a Neos account"""
        cmd = self.send_command("login \"%s\" \"%s\"" %
            (username_or_email, password))
        if cmd[-1] == "Logged in successfully!":
            return cmd[-1]
        else:
            raise NeosError(cmd[-1])

    def logout(self):
        """Log out from the current Neos account"""
        cmd = self.send_command("logout")
        if cmd[-1] == "Logged out!":
            return cmd[-1]
        else:
            raise NeosError(cmd[0])

    def message(self, friend_name, message):
        """Message user in friends list"""
        cmd = self.send_command("message \"%s\" \"%s\"" % (friend_name, message))
        if cmd[0] == "Message sent!":
            return cmd[0]
        else:
            raise NeosError(cmd[0])

    def invite(self, friend_name):
        """Invite a friend to the currently focused world"""
        cmd = self.send_command("invite \"%s\"" % friend_name)
        if cmd[0] == "Invite sent!":
            return cmd[0]
        else:
            raise NeosError(cmd[0])

    # TODO: Implement `friendRequests` here
    # TODO: Implement `acceptFriendRequest` here

    def worlds(self):
        """Lists all active worlds"""
        # TODO: This will ignore unexpected output as desired, but there is not
        # an option to direct this unexpected output anywhere with `findall()`.
        cmd = self.send_command("worlds")
        cmd = "\n".join(cmd)
        worlds = []
        for world in findall(WORLD_FORMAT, cmd):
            world = world.named
            world["name"] = world["name"].rstrip()
            worlds.append(world)
        return worlds

    def focus(self, world_name_or_number):
        """Focus world"""
        try:
            world_number = int(world_name_or_number)
            cmd = self.send_command("focus %d" % world_number)
        except ValueError:
            cmd = self.send_command("focus \"%s\"" % world_name_or_number)
        errors = [
            "World with this name does not exist",
            "World index out of range"
        ]
        if cmd and cmd[0] in errors:
            raise NeosError(cmd[0])

    # TODO: Implement `startWorldURL` here
    # TODO: Implement `startWorldTemplate` here

    def status(self):
        """Shows the status of the current world"""
        # Beware, this function does some funky stuff. It is to catch world
        # names with newlines, and ignore lines that shouldn't be there.
        # TODO: Capture unexpected output.
        cmd = self.send_command("status")

        format_status_mapping = [
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
        status["name"] = parse(STATUS_NAME_FORMAT, "\n".join(cmd))[0]
        for ln in cmd:
            if ln.startswith("SessionID"):
                session_id = ln.split(": ")[1]
                if session_id == "":
                    session_id = None
                status["session_id"] = session_id
                continue
            for i, j in format_status_mapping:
                fmt = parse(i, ln)
                if fmt:
                    status[j] = fmt[0]
                    break
            if ln.startswith("Description"):
                description = ln.split(": ")[1]
                if description == "":
                    description = None
                status["description"] = description
                continue
            if ln.startswith("Tags"):
                tags = ln.split(": ")[1]
                if tags == "":
                    tags = []
                status["tags"] = tags
                continue
        status["hidden_from_listing"] = \
            True if status["hidden_from_listing"] == "True" else False
        status["mobile_friendly"] = \
            True if status["mobile_friendly"] == "True" else False
        status["users"] = status["users"].split(", ")

        return status

    def session_url(self):
        """Prints the URL of the current session"""
        cmd = self.send_command("sessionurl")
        return cmd[0]

    def session_id(self):
        """Prints the ID of the current session"""
        cmd = self.send_command("sessionid")
        return cmd[0]

    # `copySessionURL` is not supported.
    # `copySessionID` is not supported.

    def users(self):
        """Lists all users in the world"""
        # TODO: Pipe unexpected output somewhere.
        cmd = self.send_command("users")
        users = []
        for ln in cmd:
            user = parse(USER_FORMAT, ln)
            if user == None: # Invalid output
                continue
            user = user.named
            user["name"] = user["name"].rstrip()
            user["present"] = True if user["present"] == "True" else False
            if user["fps"].is_integer():
                user["fps"] = int(user["fps"])
            users.append(user)
        return users

    def close(self):
        """Closes the currently focused world"""
        cmd = self.send_command("close")

    def save(self):
        """Saves the currently focused world"""
        # TODO: See if this still works if world is saved to cloud.
        cmd = self.send_command("save")
        for ln in cmd:
            if ln == "World saved!":
                return ln
        else:
            raise NeosError(cmd[0])

    def restart(self):
        """
        Restarts the current world

        NOTE: This is currently not implemented due to a bug in the headless
        client. Calling this function will raise an exception. For info, see:
        https://github.com/Neos-Metaverse/NeosPublic/issues/1841
        """
        # cmd = self.send_command("restart")
        raise NotImplementedError(
            "Restarting is temporarily disabled due to a headless client bug. "
            "See https://github.com/Neos-Metaverse/NeosPublic/issues/1841 "
            "for more information.")

    def kick(self, username):
        """Kicks given user from the session"""
        cmd = self.send_command("kick \"%s\"" % username)
        for ln in cmd:
            if ln.endswith("kicked!"):
                return ln
        else:
            raise NeosError(cmd[0])

    def silence(self, username):
        """Silences given user in the session"""
        cmd = self.send_command("silence \"%s\"" % username)
        for ln in cmd:
            if ln.endswith("silenced!"):
                return ln
        else:
            raise NeosError(cmd[0])

    def unsilence(self, username):
        """Removes silence from given user in the session"""
        cmd = self.send_command("unsilence \"%s\"" % username)
        for ln in cmd:
            if ln.endswith("unsilenced!"):
                return ln
        else:
            raise NeosError(cmd[0])

    def ban(self, username):
        """Bans the user from all sessions hosted by this server"""
        cmd = self.send_command("ban \"%s\"" % username)
        for ln in cmd:
            if ln.endswith("banned!"):
                return ln
        else:
            raise NeosError(cmd[0])

    def unban(self, username):
        """Removes ban for user with given username"""
        cmd = self.send_command("unban \"%s\"" % username)
        if cmd[0] == "Ban removed!":
            return cmd[0]
        else:
            raise NeosError(cmd[0])

    def list_bans(self):
        """Lists all active bans"""
        cmd = self.send_command("listbans")
        bans = []
        for ln in cmd:
            banned = parse(BAN_FORMAT, ln)
            if banned == None:
                continue
            bans.append(banned.named)
        return bans

    def ban_by_name(self, neos_username):
        """
        Bans user with given Neos username from
        all sessions hosted by this server
        """
        cmd = self.send_command("banbyname \"%s\"" % neos_username)
        if cmd[-1] == "User banned":
            return cmd[-1]
        else:
            raise NeosError(cmd[-1])

    def unban_by_name(self, neos_username):
        """
        Unbans user with given Neos username from
        all sessions hosted by this server
        """
        cmd = self.send_command("unbanbyname \"%s\"" % neos_username)
        if cmd[-1] == "Ban removed":
            return cmd[-1]
        else:
            raise NeosError(cmd[-1])

    def ban_by_id(self, user_id):
        """
        Bans user with given Neos User ID from
        all sessions hosted by this server
        """
        cmd = self.send_command("banbyid \"%s\"" % user_id)
        if cmd[-1] == "User banned":
            return cmd[-1]
        else:
            raise NeosError(cmd[-1])

    def unban_by_id(self, user_id):
        """
        Unbans user with given Neos User ID from
        all sessions hosted by this server
        """
        cmd = self.send_command("unbanbyid \"%s\"" % user_id)
        if cmd[-1] == "Ban removed":
            return cmd[-1]
        else:
            raise NeosError(cmd[-1])

    def respawn(self, username):
        """Respawns given user"""
        cmd = self.send_command("respawn \"%s\"" % username)
        if cmd[-1].endswith("respawned!"):
            return cmd[-1]
        else:
            raise NeosError(cmd[-1])

    def role(self, username, role):
        """Assigns a role to given user"""
        cmd = self.send_command("role \"%s\" \"%s\"" % (username, role))
        if "now has role" in cmd[0]:
            return cmd[0]
        else:
            raise NeosError(cmd[0])

    def name(self, new_name):
        """Sets a new world name"""
        self.send_command("name \"%s\"" % new_name)

    def access_level(self, access_level_name):
        """Sets a new world access level"""
        cmd = self.send_command("accesslevel \"%s\"" % access_level_name)
        if "now has access level" in cmd[0]:
            return cmd[0]
        else:
            raise NeosError(cmd[0])

    def hide_from_listing(self, true_false):
        """Sets whether the session should be hidden from listing or not"""
        cmd = self.send_command("hidefromlisting \"%s\"" %
            str(true_false).lower())
        if cmd[0].startswith("World") and cmd[0].endswith("listing"):
            return cmd[0]
        else:
            raise NeosError(cmd[0])

    def description(self, new_description):
        """Sets a new world description"""
        self.send_command("description \"%s\"" % new_description)

    def max_users(self, max_users):
        """Sets user limit"""
        cmd = self.send_command("maxusers \"%s\"" % max_users)
        if cmd:
            raise NeosError(cmd[0])

    def away_kick_interval(self, interval_in_minutes):
        """Sets the away kick interval"""
        cmd = self.send_command("awaykickinterval \"%s\"" % interval_in_minutes)
        if cmd:
            raise NeosError(cmd[0])

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
        if cmd[0] == "GC finished":
            return cmd[0]
        else:
            raise NeosError(cmd[0])

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
        if cmd[0] == "Tick Rate Set!":
            return cmd[0]
        else:
            raise NeosError(cmd[0])

    # `log` is not supported.

    # END HEADLESS CLIENT COMMANDS

class LocalHeadlessClient(HeadlessClient):
    def __init__(self, neos_dir, config=None):
        self.process = HeadlessProcess(neos_dir, config=config)
        super().__init__(neos_dir, config)

    def shutdown(self):
        """Shuts down the headless client"""
        # TODO: Do a SIGTERM if the client doesn't close in a reasonable time.
        self.process.write("shutdown\n")
        # TODO: Do something with `stdout` and `stderr` from this point forward.
        # TODO: Make asynchronous?
        return self.process.wait()

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
        """Shuts down the headless client"""
        return self.connection.root.stop_headless_process(self.remote_pid)

class HeadlessCommand:
    """
    Represents a headless client command and its eventual corresponding output.
    This class may seem like a stripped down version of a "future", but its only
    purpose is to keep the output of a command tied to the command that produced
    it, without having to maintain synced lists/queues for both input and
    output. This is used internally in the command queue to ensure commands are
    executing synchronously and in chronological order of submission. There is
    no need to use it directly for anything.
    """
    def __init__(self, cmd):
        self.cmd = cmd
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
