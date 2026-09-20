# R3 Native UI Probe

Isolated, silent real-game routing on card 2. This is not the production port.
See `docs/R3_NATIVE_UI.zh-CN.md` for scope, screenshots and unverified items.
Touch is **capture-only**, not gameplay input. Controller gameplay is retained.

## Build

The local game JAR and upstream Javassist agent are compile-time inputs only.
`build.py` currently uses fixed Windows/WSL paths; review those paths before
using another machine. No game classes are bundled into the adapter agent.

```powershell
py -3 prototype/r3/build.py
py -3 tools/test_r3_contract.py
py -3 tools/test_r3_heartbeat.py
py -3 tools/test_touch_contract.py
py -3 -m unittest discover -s prototype/p1 -v
py -3 tools/test_package.py
```

## Private Device Session

Set `RGDSPLUS_SSH_PASSWORD` in the process environment. Do not save credentials.
Deployment is specific to the existing private device and requires the earlier
isolated single-screen source at `/tmp/rgds-sts-silent-01`.
It does not deploy a public package or reset the private copy's saves.

```powershell
py -3 prototype/r3/device.py deploy
py -3 prototype/r3/device.py run --seconds 600
py -3 prototype/r3/device.py status
py -3 prototype/r3/device.py shot --name unique-capture-name
py -3 prototype/r3/device.py key --keys b
py -3 prototype/r3/device.py touch-probe
py -3 prototype/r3/device.py key --keys select --hold-seconds 2
py -3 prototype/r3/device.py audit
py -3 prototype/r3/device.py logs
```

`touch-probe` injects one down/up only into a focused capture-only session with
no active contact. It is not physical calibration. `stop` requests normal
supervisor cleanup when the key path cannot be used. Verify cleanup with `audit`
after waiting for the launcher to exit.

The launcher, guardian and input bridge preserve the existing touch lifecycle.
Only the private R3 launch tree is eligible for cleanup. R1, R2 and stable
single-screen binaries are not updated.
