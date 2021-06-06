# Changelog

## 2021-06-06
* Added a custom class to substitute the supposedly improper use of Python's `Future` objects in regards to command queueing. This shouldn't have any effect on API usage.
* The `async_` keyword argument has been removed from `send_command()`. Asynchronous command execution will be implemented in a better way in the near future.

## 2021-06-05
* **Breaking change:** Calling any function that produces an error in the headless client will now raise an exception instead of returning the old format of `{"success": bool, "message": str}`. Applications should catch these exceptions to handle these errors and display the error message to the user.
  * Commands that run successfully will simply return their success message as a `str`.
  * Commands that don't print any messages on success will return `None`.
* The `restart` function has been temporarily disabled due to a bug in the headless client preventing its use. Please see [this GitHub issue](https://github.com/Neos-Metaverse/NeosPublic/issues/1841) for more information. Calling `restart` will raise a `NotImplementedError` exception for now.

## 2021-05-28
* Added `host` and `port` attributes to the `RemoteHeadlessClient` class.

## 2021-05-26
* Fixed two bugs related to the parsing of the `users` command:
  * Users will now correctly show as being present or not in a session, instead of always showing as not present.
  * Users whose FPS is an integer rather than a float (ex. 60 FPS exactly) at the time `users` is run will now show in the list instead of not showing at all. This was a conditional bug.
* New command added: `listbans`

## 2021-03-31
* Remote headless clients can now be controlled via a RPC interface. You can run the server with [rpc_server.py](rpc_server.py).
* [rpyc](https://github.com/tomerfiliba-org/rpyc) is required to be able to use RPC. It is intentionally not listed in [requirements.txt](requirements.txt), effectively making it an optional dependency.
* At the moment, no form of authentication or encryption is utilized. Do not use the RPC server in public-facing environments.
* The `HeadlessClient` class is now subclasssed by `LocalHeadlessClient` and `RemoteHeadlessClient`. These should now be used instead of instantiating `HeadlessClient`.
  * `LocalHeadlessClient` will start a headless client on the local machine, as the name implies. This was previously the behavior of the `HeadlessClient` class.
  * `RemoteHeadlessClient` will connect to an RPC server at the given `host` and `port` and start a headless client on that host. All paths provided, including the directory Neos is in and the location of the configuration file, should be those of the remote host.
  * Command queueing and parsing still happens on the local host regardless of whether the headless client is local or remote, the only thing that changes is where the data streams are coming from.

## 2021-03-19
* The following commands have been added:
  * `close`
  * `save`
  * `restart`

## 2021-03-18
* Added the ability to provide a configuration file in another location using Neos' `--config` parameter.

## 2021-03-17
* The following commands have been added:
  * `ban`
  * `unban`
  * `banByName`
  * `unbanByName`
  * `banByID`
  * `unbanByID`
  * `accessLevel`
  * `hideFromListing`
* Fixed some boolean values that were strings.
* Encased all user-provided input in commands with double quotations, so that usernames, world names, etc. containing spaces will work properly.
* Fixed a bug that caused the `role` function to always throw an exception due to an incorrect variable name.

## 2021-03-12
* Commands are now queued so that they are guaranteed to be run in order, and can optionally be executed asynchronously.
  * Execute commands asynchronously by setting the `async_` keyword argument to `True` when calling `send_command()`. At the moment, the higher-level functions do not support asynchronous calls.
  * The keyword argument is named `async_` so that it does not conflict with Python's built-in `async` keyword.
* Several variables are now set in the `HeadlessClient` class which contain information obtained from the headless client's startup messages, such as `self.version`, `self.compatibility_hash`, and `self.machine_id`.

## 2021-03-11
* The following commands have been added:
  * `login`
  * `logout`
  * `focus`
  * `respawn`
  * `role`
  * `tickRate`

## 2021-03-09
* Added this changelog
* A bug in the headless client that [allowed closing the Userspace world, causing the client to hang](https://github.com/Neos-Metaverse/NeosPublic/issues/1811) was resolved by removing access to the Userspace world from the headless client console entirely. Checks to make sure that `close`, among other commands, are not executed on the Userspace world are no longer needed. This bug is resolved as of Neos version Beta 2021.3.9.130, so the README has been updated to reflect this.

## 2021-03-08
* The following commands have been added:
  * `name`
  * `description`
  * `maxUsers`
  * `awayKickInterval`
  * `gc`

## 2021-03-05
* The [parse](https://github.com/r1chardj0n3s/parse) package is now used for more robust parsing of command output.
* Attempting to get the session URL or session ID for the Userspace world now returns `None`, as this world has no session ID.

## 2021-03-04
* A new class called `HeadlessProcess` has been created for the sole purpose of handling the headless client's `stdin`, `stdout`, and `stderr` streams. It is only intended to be used by the `HeadlessClient` class, which contains the higher-level functions for executing commands and parsing their responses into objects. This is likely to be further optimized in the future.
* Renamed the `HeadlessClient` function `_send_command()` to `send_command()`, to indicate it may be used directly if necessary.
* Add `wait()` to `HeadlessClient` which blocks until the process exits. `shutdown()` now uses this call.
* Fix another function call in `shutdown()`

## 2021-02-22
* Initial commit, with support for the following commands:
  * `message`
  * `invite`
  * `worlds`
  * `status`
  * `sessionUrl`
  * `sessionID`
  * `users`
  * `kick`
  * `silence`
  * `unsilence`
  * `shutdown`
