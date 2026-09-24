# Third-party notices

This repository is an unofficial RGDSplus compatibility adapter. It is not the
Slay the Spire game and does not contain the purchased game JAR.

## PortMaster

The adapter incorporates compatibility files from
`PortsMaster/PortMaster-New`, source commit
`d4a4130059e2c8e8627bc55b78e3e0fae5b038f8`, under
`ports/slaythespire`. The upstream README, manifest and notices are retained
inside the generated adapter package where applicable. The PortMaster project
and its contributors retain their respective copyrights and licenses.

The exact source mapping and hashes are recorded in `upstream-manifest.json`.
The upstream snapshot is a local build input and is intentionally not uploaded
as a second copy of the upstream repository.

## Offline runtimes

Build `20260924-02` additionally distributes unmodified ARM64 Java 17 and
Weston runtime images from a fixed PortMaster revision. See
[offline runtime notices](packaging/OFFLINE_RUNTIMES.md) and the generated
package's `NOTICES/offline-runtime-manifest.json` for provenance and hashes.
The third-party images keep their original notices and licenses and are not
covered by the original adapter's license or commercial-use restrictions.

## User-supplied game

The user supplies a legally obtained `desktop-1.0.jar`. It is never included
in Git, in the adapter ZIP, or in a GitHub Release. The adapter does not grant
any right to copy, distribute, modify or bypass authorization for the game.

## Scope

Third-party components remain subject to their own license files and notices.
This document is not a replacement for reviewing the notices shipped with the
exact upstream files used by a particular build.
