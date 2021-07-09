# Changelog

## 2021-07-09
* Add `CommandTimeout` exception which is raised when a command takes too long to return any output.

## 2021-07-02
* Overhauled the shutdown methods of the headless client:
  * `shutdown()` now accepts an optional `timeout` keyword argument to specify how long to wait (in seconds) for the headless client to shut down before raising a `TimeoutExpired` exception. `wait` can also be set to `False` to make the call non-blocking, in which case `timeout` is ignored and returns immediately, but without an exit code.
  * `sigint()` can be called to issue a `SIGINT` signal to the headless client, which should emulate pressing `Ctrl+C` in the console and cleanly shut down the headless client. This also accepts the `timeout` and `wait` keyword arguments mentioned above. Returns `-2`, if `wait` is `True`.
  * `terminate()` can be called to issue a `SIGTERM` signal to the headless client. This also accepts the `timeout` and `wait` keyword arguments mentioned above. Returns `-15`, if `wait` is `True`.
  * `kill()` can be called to issue a `SIGKILL` signal to the headless client. This also accepts the `timeout` and `wait` keyword arguments mentioned above. Returns `-9`, if `wait` is `True`.
  * `wait_for_shutdown()` is a blocking call that will wait for the headless client to shut down. The `timeout` keyword argument can be specified to wait up to `timeout` seconds for the headless client to shut down before raising a `TimeoutExpired` exception. Returns the exit code. This can be used after using any of the above functions in non-blocking mode (when `wait` is `False`).
* New methods exist for waiting on the headless client's "ready" state:
  * **Breaking change:** `wait()` has been renamed to `wait_for_ready()` and now accepts a `timeout` keyword argument. Blocks and returns `True` when the headless client is ready to accept commands. If `timeout` is specified, the call will return `False` if the headless client does not enter a ready state within `timeout` seconds.
  * `is_ready()` can be called to immediately check whether the headless client is ready or not without blocking. Returns either `True` if it is ready, or `False` if it is not ready.
* The `users()` function will now show whether the users in a session are silenced or not, which is a feature that was added in Neos version [2021.7.1.437](https://github.com/Neos-Metaverse/NeosPublic/issues/2517#issuecomment-871997486).

## 2021-06-27
* Defined constants for Neos' roles and access levels.
  * For user roles, they are: `ADMIN`, `BUILDER`, `MODERATOR`, `GUEST`, and `SPECTATOR`.
  * For session/world access levels, they are: `PRIVATE`, `LAN`, `FRIENDS`, `FRIENDS_OF_FRIENDS`, `REGISTERED_USERS`, and `ANYONE`.

## 2021-06-23
* Added an argument parser to the RPC server. It now accepts the following arguments:
  * `--host`: Specify the host or IP to bind to. Defaults to `127.0.0.1` (previously `0.0.0.0`).
  * `-p` or `--port`: Specify the TCP port to bind to. Defaults to `16881`.

## 2021-06-21
* Fixed a conditional parsing bug in the `users()` function where a headless user would not show up in the user list if it was not logged into a Neos account. This occurred because unauthenticated headless users have no user IDs, and this would cause parsing to fail. Headless users will now have their user ID set to `None` in these instances.

## 2021-06-18
* User IDs are now included when listing the users in a session, which is a feature that was added in Neos version [2021.6.18.4](https://github.com/Neos-Metaverse/NeosPublic/issues/2485#issuecomment-863639775).

## 2021-06-17
* Added checks for new error messages added in Neos version [2021.6.14.1031](https://github.com/Neos-Metaverse/NeosPublic/issues/2457#issuecomment-860859990), which occur when attempting to use `banByName` or `banByID` to ban a user who has already been banned.

## 2021-06-16
* Added exception for unexpected errors that occur in the headless client.

## 2021-06-12
* Added checks for additional error messages, particularly "Not logged in!" errors that occur when running a command that requires a logged in user while not being logged in.

## 2021-06-11
* Parsing of commands is now much more strict and less error prone. See [this GitHub issue](https://github.com/Neos-Metaverse/NeosPublic/issues/2436) for information on why this is required.
* The `status` command in particular has much improved parsing:
  * The check for an empty session ID has been removed. This used to be needed as the Userspace world had no session ID, but the [Userspace world has been removed from the world listing](https://github.com/Neos-Metaverse/NeosPublic/issues/1811#issuecomment-793282104) as of Neos version 2021.3.9.130.
  * Worlds with blank names are now parsed properly. The name will be set to `None` if there is no name.
  * Descriptions with multiple lines are now parsed properly.
  * Tags are now converted into the `list` type.
  * **Known bug:** World names containing lines ending with a `>` character may cause undesirable behavior as it trips up detection of the prompt, particularly when running the `status` command. Avoid using world names ending with a `>` immediately before a new line. Specifically, be careful when using [text formatting](https://wiki.neos.com/Text_Formatting) in world names.
* All other commands will now ignore unexpected output.

## 2021-06-09
* Calling any command or using `send_command()` directly will now raise an exception if the headless client is not ready to accept comamnds yet (for instance if it has just been started). Use the `wait()` method to block until the headless client is fully started up.

## 2021-06-06
* Added a custom class to substitute the supposedly improper use of Python's `Future` objects in regards to command queueing. This shouldn't have any effect on API usage.
* Most functions now accept a `world` keyword argument to execute a command "in" a particular world, by focusing/switching the world immediately before executing the command. If this argument is not defined, the command is executed in the currently focused world instead. Attempting to focus a world that doesn't exist will raise an exception and not execute the command.
  * Certain commands such as `login`, `message`, etc. don't have the `world` keyword argument because they don't require a world to be focused.
* The `async_` keyword argument has been removed from `send_command()`. Command results can now be waited on asynchronously by passing any function and its arguments to the `async_()` function in the `HeadlessClient` class.
  * The underscore is to avoid a naming conflict with Python's reserved `async` name.
  * `async_()` returns a `Future` object, from Python's `concurrent.futures` module. Please see [Python's documentation for Future objects](https://docs.python.org/3/library/concurrent.futures.html?highlight=futures#future-objects) for information on how to use these.

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
