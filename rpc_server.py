#!/usr/bin/env python3

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

# This is the RPC server which can be used to control headless clients remotely.

import logging
import argparse

from rpyc import Service, restricted
from neosvr_headless_api import HeadlessProcess

logging.basicConfig(
    format="[%(asctime)s][%(levelname)s] %(message)s",
    level=logging.INFO
)

def main():
    parser = argparse.ArgumentParser(
        description="RPC server for controlling multiple headless clients"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="The host or IP address to bind to. (Default: 127.0.0.1)"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=16881,
        help="The TCP port to bind to. (Default: 16881)"
    )
    args = parser.parse_args()

    from rpyc.utils.server import ThreadedServer
    server = ThreadedServer(
        HeadlessProcessService(),
        hostname=args.host,
        port=args.port
    )
    server.start()

class HeadlessProcessService(Service):
    def __init__(self):
        super().__init__()
        self.processes = {}
        self.current_id = 0

    def on_connect(self, conn):
        host, port = conn._config["endpoints"][1]
        logging.info("Client connected from %s:%d" % (host, port))

    def on_disconnect(self, conn):
        host, port = conn._config["endpoints"][1]
        logging.info("Client disconnected from %s:%d" % (host, port))

    def exposed_start_headless_process(self, *args, **kwargs):
        """
        Start a new instance of a `HeadlessProcess`. Returns a tuple in the form
        of (id, `HeadlessProcess` instance). All arguments and keyword arguments
        are passed to `HeadlessProcess` as-is.

        The id can be used to get the `HeadlessProcess` instance again at a
        later time with `get_headless_process()`.
        """
        allowed_access = ("neos_dir", "config", "write", "readline", "shutdown",
            "sigint", "terminate", "kill", "wait")
        process = restricted(HeadlessProcess(*args, **kwargs), allowed_access)
        self.current_id += 1
        self.processes[self.current_id] = process
        logging.info("Starting headless process with ID: %d" % self.current_id)
        logging.info("Neos Dir: %s" % process.neos_dir)
        logging.info("Config: %s" % process.config)
        logging.info("Total processes running: %d" % len(self.processes))
        return (self.current_id, process)

    def exposed_stop_headless_process(self, pid):
        """
        Stops the `HeadlessProcess` with the given `pid` and removes it from the
        process list. Returns the exit code of the process.
        """
        process = self.processes[pid]
        exit_code = process.shutdown()
        del(self.processes[pid])
        logging.info(
            "Headless process with ID %d terminated with return code %d." %
            (pid, exit_code)
        )
        logging.info("Total processes running: %d" % len(self.processes))
        return exit_code

    def exposed_send_signal_headless_process(self, pid, sig):
        """
        Send a signal to the `HeadlessProcess` with the given `pid` and removes
        it from the process list. `sig` is an integer which can be either
        SIGINT (2), SIGTERM (15), or SIGKILL (9). If `sig` is not one of these
        integers, `ValueError` will be raised. Returns the signal used to
        terminate the process as a negative integer.
        """
        process = self.processes[pid]
        if not sig in (2, 9, 15):
            raise ValueError("Signal not allowed: %d" % sig)
        if sig == 2:
            func = process.sigint
        elif sig == 9:
            func = process.kill
        elif sig == 15:
            func = process.terminate
        exit_code = func()
        # TODO: The following code is identical to that of
        # `exposed_stop_headless_process()`
        del(self.processes[pid])
        logging.info(
            "Headless process with ID %d terminated with return code %d." %
            (pid, exit_code)
        )
        logging.info("Total processes running: %d" % len(self.processes))
        return exit_code

    def exposed_get_headless_process(self, pid):
        """Returns an existing `HeadlessProcess` with the given `pid`."""
        return self.processes[pid]

if __name__ == "__main__":
    main()
