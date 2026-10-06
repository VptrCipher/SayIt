#!/usr/bin/env python3
"""Build a manylinux-compatible PortAudio shared library for the Linux AppImage.

The python-sounddevice package does not bundle PortAudio on Linux. SayIt loads
sounddevice during application startup, so a missing libportaudio.so.2 can make
an otherwise valid AppImage exit before the UI appears.

This script builds PortAudio inside the same manylinux_2_28 family used by the
Briefcase AppImage backend, with ALSA enabled and dynamically loaded. The
resulting shared object is placed in the Python package as build-time data;
it is not committed to Git.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

PORTAUDIO_TAG = "v19.7.0"
BUILD_IMAGE = os.environ.get(
    "SAYIT_LINUX_BUILD_IMAGE",
    "quay.io/pypa/manylinux_2_28_x86_64:latest",
)


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is required to build the Linux PortAudio runtime.")

    root = Path(__file__).resolve().parents[1]
    destination = root / "src" / "sayit" / "_vendor" / "linux"
    destination.mkdir(parents=True, exist_ok=True)

    for path in destination.glob("libportaudio.so*"):
        path.unlink()

    uid = os.getuid()
    gid = os.getgid()

    docker_script = f"""
set -eux
PKG=dnf
if ! command -v dnf >/dev/null 2>&1; then
  PKG=yum
fi

$PKG install -y alsa-lib-devel cmake gcc gcc-c++ make tar gzip curl

rm -rf /tmp/portaudio-src /tmp/portaudio-build /tmp/portaudio-install
mkdir -p /tmp/portaudio-src /tmp/portaudio-install

curl -fsSL https://github.com/PortAudio/portaudio/archive/refs/tags/{PORTAUDIO_TAG}.tar.gz |
  tar -xz --strip-components=1 -C /tmp/portaudio-src

cmake -S /tmp/portaudio-src -B /tmp/portaudio-build   -DCMAKE_BUILD_TYPE=Release   -DPA_BUILD_SHARED_LIBS=ON   -DPA_BUILD_STATIC=OFF   -DPA_BUILD_TESTS=OFF   -DPA_BUILD_EXAMPLES=OFF   -DPA_USE_ALSA=ON   -DPA_ALSA_DYNAMIC=ON \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5

cmake --build /tmp/portaudio-build --parallel
cmake --install /tmp/portaudio-build --prefix /tmp/portaudio-install

mkdir -p /workspace/src/sayit/_vendor/linux
rm -f /workspace/src/sayit/_vendor/linux/libportaudio.so*
cp -a /tmp/portaudio-install/lib/libportaudio.so* /workspace/src/sayit/_vendor/linux/

chown -R {uid}:{gid} /workspace/src/sayit/_vendor/linux
ls -la /workspace/src/sayit/_vendor/linux
"""

    run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            "0:0",
            "-v",
            f"{root}:/workspace",
            "-w",
            "/workspace",
            BUILD_IMAGE,
            "bash",
            "-lc",
            docker_script,
        ]
    )

    libraries = sorted(destination.glob("libportaudio.so*"))
    if not libraries:
        raise RuntimeError("PortAudio build completed but no libportaudio.so* was produced.")

    print("Bundled PortAudio runtime:")
    for library in libraries:
        print(f"  {library.relative_to(root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
