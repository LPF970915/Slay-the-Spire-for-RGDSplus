# Offline ARM64 runtimes

This adapter includes unmodified PortMaster runtime images, not game assets:

- `zulu17.54.21-ca-jre17.0.13-linux.squashfs`: Azul Zulu OpenJDK
  17.0.13+11, ARM64 Linux.
- `weston_pkg_0.2.squashfs`: PortMaster Westonpack ARM64 runtime and
  its bundled graphics compatibility libraries.
- `libs/libjpeg.so.8` and `libs/libXtst.so.6`: unmodified ARM64 shared
  libraries from Ubuntu Jammy `libjpeg-turbo8` and `libxtst6`. The Debian
  packages are SHA-256 pinned against Ubuntu's package download records.
  Full copyright/license notices are retained alongside this file as
  `libjpeg.so.8-copyright.txt` and `libXtst.so.6-copyright.txt`.

Exact download URLs, the pinned PortMaster commit, Git blob identifiers,
sizes and SHA-256 digests are in `offline-runtime-manifest.json`.
The runtime files are downloaded from upstream, never copied from a player's
modified PortMaster installation. They are mounted read-only in `/tmp`.
They do not install into or overwrite PortMaster, firmware or other ports.

## Copyright and source

These independent third-party works retain their own licenses. The adapter's
original-code license and commercial-use restrictions do not apply to them.
No existing file or notice inside either runtime image has been removed.

Zulu retains its complete `legal/` directory inside the image, including the
GNU GPL version 2, Classpath Exception, additional license information and
component-specific notices. See Azul's source-code distribution:

https://www.azul.com/downloads/?package=jdk#zulu
https://cdn.azul.com/zulu/src/

The Westonpack upstream project is:

https://github.com/binarycounter/Westonpack

The Westonpack wrapper/build scripts use the MIT license; this does not
relicense the individual bundled libraries. `Westonpack-LICENSE.txt` preserves
the upstream project's license. Component source projects include
https://gitlab.freedesktop.org/wayland/weston and
https://github.com/ptitSeb/gl4es. The original binary images are from:

https://github.com/PortsMaster/PortMaster-New/tree/00b09f76f36cd3ee310df4ae612cee925404b927/runtimes

The supplementary library source packages and original projects are available
from the Ubuntu package pools recorded in the manifest, and:

https://github.com/libjpeg-turbo/libjpeg-turbo
https://gitlab.freedesktop.org/xorg/lib/libxtst

## Firmware baseline

Offline packaging removes the need to install/download Java and Weston.
It does not replace the RGDSplus Linux firmware, graphics drivers, running
Wayland compositor, Python 3, system OpenAL, shell utilities or the firmware's
PortMaster `control.txt` and `gptokeyb`. Those remain the supported firmware
baseline and are checked before game resource extraction.
