# GBO CBS Collector

Private-use collector code for Grant Baseball Operations (GBO).

This repository contains no CBS username, password, session cookie, access token, league password, or snapshot data. The collector runs only inside Grant's already-authenticated CBS Fantasy Baseball browser session and downloads a sanitized JSON snapshot locally.

## Files

- `collector.js` — current production collector used by the permanent GBO Refresh launcher.
- `versions/` — immutable tested collector versions.
- `bookmarklet.txt` — permanent bookmarklet launcher. The launcher URL should not need to change when `collector.js` is updated.

## Security

The collector is read-only. It uses CBS authentication only inside the browser session, never stores the CBS token, and aborts output if credential-like content is detected.
