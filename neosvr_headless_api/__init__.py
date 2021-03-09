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

# List of valid access levels for worlds:
# Private, LAN, Friends, FriendsOfFriends, RegisteredUsers, Anyone

# TODOS:

# Test if really long session name breaks the format of `worlds`.
# Handle blank world names.
# Check if no world is currently focused. Could affect all commands.
# Add optional timeout for wait()
# Thread safeness
# Add ability to load config from other location.
# When running commands, funnel unexpected output somewhere to be reviewed
# later as they may be errors.

# TESTING REQUIRED: If there are critical errors and a prompt never comes back,
# Python will hang while waiting to read it. I don't know if this is a situation
# that could occur though. Probably depends on the world.

from threading import Thread, Event
from queue import Queue, Empty
from subprocess import Popen, PIPE

from parse import parse, findall

from .response_formats import *

class HeadlessProcess:
    """
    Handles direct control of the NeosVR headless client. This class is not
    intended to be used directly. `HeadlessClient` should be used instead.
    """
    def __init__(self, neos_dir, config=None):
        self.neos_dir = neos_dir
        self.process = Popen(["mono", "Neos.exe"],
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
            thread.daemon = True
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
        self.neos_dir = neos_dir
        self.process = HeadlessProcess(self.neos_dir, config=config)
        self.ready = Event()

        def init():
            """Parse startup output and determine when it's ready."""
            # `almost_ready` is set to True when at least one world is
            # running. Only then do we look for the ">" character in the
            # prompt, to prevent false positives.
            almost_ready = False
            while True:
                ln = self.process.readline()
                if ln.endswith(">") and almost_ready:
                    self.ready.set()
                    break
                elif ln == "World running...":
                    almost_ready = True

        init_thread = Thread(target=init)
        init_thread.start()

    def wait(self):
        """Block until the process becomes ready."""
        return self.ready.wait()

    def send_command(self, cmd):
        """Sends a command to the console, returns the output."""
        # TODO: Probably still not thread-safe.
        # TODO: Raise an exception if client is not ready yet.
        self.process.write("%s\n" % cmd)
        res = []
        while True:
            ln = self.process.readline()
            if ln.endswith(">"):
                break
            res.append(ln)
        return res

    # BEGIN HEADLESS CLIENT COMMANDS

    # TODO: Implement `saveConfig` here
    # TODO: Implement `login` here
    # TODO: Implement `logout` here

    def message(self, friend_name, message):
        """Message user in friends list"""
        cmd = self.send_command("message %s \"%s\"" % (friend_name, message))
        if cmd[0] == "Message sent!":
            return {"success": True, "message": cmd[0]}
        else:
            return {"success": False, "message": cmd[0]}

    def invite(self, friend_name):
        """Invite a friend to the currently focused world"""
        cmd = self.send_command("invite %s" % friend_name)
        if cmd[0] == "Invite sent!":
            return {"success": True, "message": cmd[0]}
        else:
            return {"success": False, "message": cmd[0]}

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

    # TODO: Implement `focus` here
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
            user["present"] = True if user["present"] == True else False
            users.append(user)
        return users

    # TODO: Implement `close` here
    # TODO: Implement `save` here
    # TODO: Implement `restart` here

    def kick(self, username):
        """Kicks given user from the session"""
        cmd = self.send_command("kick %s" % username)
        for ln in cmd:
            if ln.endswith("kicked!"):
                return {"success": True, "message": ln}
        else:
            return {"success": False, "message": cmd[0]}

    def silence(self, username):
        """Silences given user in the session"""
        cmd = self.send_command("silence %s" % username)
        for ln in cmd:
            if ln.endswith("silenced!"):
                return {"success": True, "message": ln}
        else:
            return {"success": False, "message": cmd[0]}

    def unsilence(self, username):
        """Removes silence from given user in the session"""
        cmd = self.send_command("unsilence %s" % username)
        for ln in cmd:
            if ln.endswith("unsilenced!"):
                return {"success": True, "message": ln}
        else:
            return {"success": False, "message": cmd[0]}

    # TODO: Implement `ban` here
    # TODO: Implement `unban` here
    # TODO: Implement `banByName` here
    # TODO: Implement `unbanByName` here
    # TODO: Implement `banByID` here
    # TODO: Implement `unbanByID` here
    # TODO: Implement `respawn` here
    # TODO: Implement `role` here

    def name(self, new_name):
        """Sets a new world name"""
        self.send_command("name \"%s\"" % new_name)
        return {"success": "True"}

    # TODO: Implement `accessLevel` here
    # TODO: Implement `hideFromListing` here

    def description(self, new_description):
        """Sets a new world description"""
        self.send_command("description \"%s\"" % new_description)
        return {"success": "True"}

    def max_users(self, max_users):
        """Sets user limit"""
        cmd = self.send_command("maxusers %s" % max_users)
        if cmd:
            return {"success": False, "message": cmd[0]}
        else:
            return {"success": True}

    def away_kick_interval(self, interval_in_minutes):
        """Sets the away kick interval"""
        cmd = self.send_command("awaykickinterval %s" % interval_in_minutes)
        if cmd:
            return {"success": False, "message": cmd[0]}
        else:
            return {"success": True}

    # TODO: Implement `import` here
    # TODO: Implement `dynamicImpulse` here
    # TODO: Implement `dynamicImpulseString` here
    # TODO: Implement `dynamicImpulseInt` here
    # TODO: Implement `dynamicImpulseFloat` here
    # TODO: Implement `spawn` here

    def gc(self):
        """Forces full garbage collection"""
        cmd = self.send_command("gc")
        if cmd[0] == "GC finished":
            return {"success": True, "message": cmd[0]}
        else:
            return {"success": False, "message": cmd[0]}

    def shutdown(self):
        """Shuts down the headless client"""
        # TODO: Do a SIGTERM if the client doesn't close in a reasonable time.
        self.process.write("shutdown\n")
        # TODO: Do something with `stdout` and `stderr` from this point forward.
        # TODO: Make asynchronous?
        return self.process.wait()

    # TODO: Implement `tickRate` here

    # `log` is not supported.

    # END HEADLESS CLIENT COMMANDS
