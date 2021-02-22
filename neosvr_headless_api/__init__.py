# NOTE: List of valid access levels for worlds:
# Private, LAN, Friends, FriendsOfFriends, RegisteredUsers, Anyone

# TODO: Test if really long session name breaks the format of `worlds`.
# TODO: Look into Python's `isatty` stuff.
# TODO: Don't allow closing Userspace world. This halts the client.
# TODO: Figure out how to reliably detect prompt. It doesn't always update when
# it is supposed to, like when changing worlds. Seems like a race condition.
# TODO: Test Unicode names, somehow.
# TODO: Add optional timeout for wait()

# TESTING REQUIRED: If there are critical errors and a prompt never comes back,
# Python will hang while waiting to read it. I don't know if this is a situation
# that could occur though. Probably depends on the world.

from threading import Thread, Event
from subprocess import Popen, PIPE

class HeadlessClient:
    def __init__(self, neos_dir):
        self.neos_dir = neos_dir
        self.ready = Event()

        def run():
            self.process = Popen(["mono", "Neos.exe"],
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE, # TODO: Is anything useful printed to `stderr`?
                text=True,
                bufsize=1,
                encoding="UTF-8",
                cwd=self.neos_dir
            )
            self.focused_world = None

            for ln in self.process.stdout:
                if ln.startswith("User Joined"):
                    self.focused_world = ln[12:ln.index(". Username")]
                # TODO: Make this support multiple worlds.
                elif ln == "World running...\n":
                    break

            self.ready.set()

            # Skip the prompt
            self._read_until_prompt()

        self.thread = Thread(target=run)
        self.thread.daemon = True # TODO: Implement clean shutdown
        self.thread.start()

    def _read_until_prompt(self):
        output, ln = [], []
        while True:
            # TODO: Figure out if there is a cleaner way of reading `stdout`
            # than reading one byte at a time. However, I don't think there is a
            # better cross-platform way of doing it because of the way Python
            # blocks on read() if there is no more output to be read. So this is
            # the only way we can read output without running over the edge.
            # TODO: This may not be thread-safe.
            c = self.process.stdout.read(1)
            if c == "\n":
                output.append("".join(ln))
                ln = []
            elif c == ">":
                s = "".join(ln)
                if s == "Glitch Test Session": # TODO: Remove hardcoded value
                    break
                else:
                    ln.append(c)
            else:
                ln.append(c)
        return output

    def _send_command(self, cmd):
        """Sends a command to the console, returns the output."""
        # TODO: This may not be thread-safe.
        self.process.stdin.write("%s\n" % cmd)
        return self._read_until_prompt()

    def wait(self):
        """Blocks until the headless client is ready to receive input."""
        return self.ready.wait()

    # BEGIN HEADLESS CLIENT COMMANDS

    # TODO: Implement `saveConfig` here
    # TODO: Implement `login` here
    # TODO: Implement `logout` here

    def message(self, friend_name, message):
        """Message user in friends list"""
        cmd = self._send_command("message %s \"%s\"" % (friend_name, message))
        if cmd[0] == "Message sent!":
            return {"success": True, "message": cmd[0]}
        else:
            return {"success": False, "message": cmd[0]}

    def invite(self, friend_name):
        """Invite a friend to the currently focused world"""
        cmd = self._send_command("invite %s" % friend_name)
        if cmd[0] == "Invite sent!":
            return {"success": True, "message": cmd[0]}
        else:
            return {"success": False, "message": cmd[0]}

    # TODO: Implement `friendRequests` here
    # TODO: Implement `acceptFriendRequest` here

    def worlds(self):
        """Lists all active worlds"""
        cmd = self._send_command("worlds")
        worlds = []
        for ln in cmd:
            world = {}
            world["name"] = ln[4:36].rstrip()
            ln = ln[36:].split("\t")
            world["users"] = int(ln[0].split()[1])
            world["present"] = int(ln[1].split()[1])
            world["access_level"] = ln[2].split()[1]
            world["max_users"] = int(ln[3].split()[1])
            worlds.append(world)
        return worlds

    # TODO: Implement `focus` here
    # TODO: Implement `startWorldURL` here
    # TODO: Implement `startWorldTemplate` here

    def status(self):
        """Shows the status of the current world"""
        cmd = self._send_command("status")
        cmd_dict = {}
        for ln in cmd:
            ln = ln.split(": ", 1)
            cmd_dict[ln[0]] = ln[1]
        # Some remapping and type conversion
        status = {}
        status["name"] = cmd_dict["Name"]
        status["session_id"] = cmd_dict["SessionID"]
        status["current_users"] = int(cmd_dict["Current Users"])
        status["present_users"] = int(cmd_dict["Present Users"])
        status["max_users"] = int(cmd_dict["Max Users"])
        status["uptime"] = cmd_dict["Uptime"]
        status["access_level"] = cmd_dict["Access Level"]
        status["hidden_from_listing"] = \
            True if cmd_dict["Hidden from listing"] == "True" else False
        status["mobile_friendly"] = \
            True if cmd_dict["Mobile Friendly"] == "True" else False
        status["description"] = cmd_dict["Description"]
        status["tags"] = cmd_dict["Tags"].split(", ")
        status["users"] = cmd_dict["Users"].split(", ")
        return status

    def session_url(self):
        """Prints the URL of the current session"""
        cmd = self._send_command("sessionurl")
        return cmd[0]

    def session_id(self):
        """Prints the ID of the current session"""
        cmd = self._send_command("sessionid")
        return cmd[0]

    # `copySessionURL` is not supported.
    # `copySessionID` is not supported.

    def users(self):
        """Lists all users in the world"""
        cmd = self._send_command("users")
        users = []
        for ln in cmd:
            ln = ln.split("\t")
            user = {}
            user["name"] = ln[0]
            user["role"] = ln[1].split()[1] # TODO: Make Python objects?
            user["present"] = True if ln[2].split()[1] == "True" else False
            user["ping"] = int(ln[3].split()[1]) # in milliseconds
            user["fps"] = float(ln[4].split()[1])
            users.append(user)
        return users

    # TODO: Implement `close` here
    # TODO: Implement `save` here
    # TODO: Implement `restart` here

    def kick(self, username):
        """Kicks given user from the session"""
        cmd = self._send_command("kick %s" % username)
        for ln in cmd:
            if ln.endswith("kicked!"):
                return {"success": True, "message": ln}
        else:
            return {"success": False, "message": cmd[0]}

    def silence(self, username):
        """Silences given user in the session"""
        cmd = self._send_command("silence %s" % username)
        for ln in cmd:
            if ln.endswith("silenced!"):
                return {"success": True, "message": ln}
        else:
            return {"success": False, "message": cmd[0]}

    def unsilence(self, username):
        """Removes silence from given user in the session"""
        cmd = self._send_command("unsilence %s" % username)
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
    # TODO: Implement `name` here
    # TODO: Implement `accessLevel` here
    # TODO: Implement `hideFromListing` here
    # TODO: Implement `description` here
    # TODO: Implement `maxUsers` here
    # TODO: Implement `awayKickInterval` here
    # TODO: Implement `import` here
    # TODO: Implement `dynamicImpulse` here
    # TODO: Implement `dynamicImpulseString` here
    # TODO: Implement `dynamicImpulseInt` here
    # TODO: Implement `dynamicImpulseFloat` here
    # TODO: Implement `spawn` here
    # TODO: Implement `gc` here

    def shutdown(self):
        """Shuts down the headless client"""
        # TODO: Do a SIGTERM if the client doesn't close in a reasonable time.
        self.process.stdin.write("shutdown\n")
        # Empty buffers
        # TODO: Read them to a file? Make asyncronous?
        self.process.stdout.read()
        self.process.stderr.read()
        return self.process.wait()

    # TODO: Implement `tickRate` here

    # `log` is not supported.

    # END HEADLESS CLIENT COMMANDS
