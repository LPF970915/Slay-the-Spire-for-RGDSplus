# RGDSplus Touch Integration Rules

Read `docs/RGDSPLUS_TOUCH_CONTRACT.zh-CN.md` before changing launch, touch,
display focus, packaging, or integrating the real dual-screen game.

- The user confirmed physical touch on 2026-09-20 with the `touch2` build.
  Its reference implementations are `prototype/p1/touch_mode.py` and
  `prototype/p1/device_input.py`. Do not replace them with SDL-only input.
- Preserve explicit `tpctrl=0` activation even when readback is already zero.
  Persist the previous known mode before activation and restore conditionally
  during normal exit, emergency exit, and independent supervisor recovery.
- Do not hardcode event numbers or change firmware/udev/calibration permanently.
  Evdev touch coordinates are lower-screen local, not compositor coordinates.
- Keep touch focus/grab ownership and stale-event cancellation; never grab
  controller keys used by the independent emergency exit monitor.
- Before distribution run `py -3 tools/test_touch_contract.py` and
  `py -3 -m unittest discover -s prototype/p1 -v`.
- Software replay, evdev injection, and framebuffer screenshots are not proof
  of physical touch accuracy or visual panel correctness. Preserve evidence
  labels and do not mark unmeasured acceptance criteria passed.
- Keep P1 probes separate on card 2. Do not overwrite the stable single-screen
  runtime or use production saves for dual-screen experiments.
