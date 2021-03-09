# Changelog

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
