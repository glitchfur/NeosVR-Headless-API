# Changelog

## 2021-03-17
* The following commands have been added:
  * `ban`
  * `unban`
  * `banByName`
  * `unbanByName`
  * `banByID`
  * `unbanByID`
* Fixed some boolean values that were strings.

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
