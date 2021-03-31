#!/usr/bin/env python3

# NeosVR-Headless-API
# Glitch, 2021

# This is the RPC server which can be used to control headless clients remotely.

import logging

from rpyc import Service, restricted
from neosvr_headless_api import HeadlessProcess

logging.basicConfig(
    format="[%(asctime)s][%(levelname)s] %(message)s",
    level=logging.INFO
)

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
        allowed_access = ("config", "neos_dir", "write", "readline", "wait")
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
        process.write("shutdown\n")
        exit_code = process.wait()
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
    from rpyc.utils.server import ThreadedServer
    server = ThreadedServer(HeadlessProcessService(), port=16881)
    server.start()
