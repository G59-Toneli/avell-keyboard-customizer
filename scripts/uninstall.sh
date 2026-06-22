#!/usr/bin/env bash
#
# Remove avell-rgb-control userspace bits and configs. Leaves the (generic)
# tuxedo-drivers module in place; remove it manually if you want.
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo $0" >&2
    exit 1
fi

DKMS_NAME="tuxedo-drivers-avell"
DKMS_VER="1.0.0"
if command -v dkms >/dev/null && dkms status -m "$DKMS_NAME" 2>/dev/null | grep -q "$DKMS_NAME"; then
    dkms remove -m "$DKMS_NAME" -v "$DKMS_VER" --all || true
    rm -rf "/usr/src/${DKMS_NAME}-${DKMS_VER}"
fi

rm -f /usr/local/bin/kbcolor /usr/local/bin/kbcolor-gui
rm -rf /usr/local/lib/avell-rgb-control
rm -f /usr/share/applications/avell-rgb.desktop
rm -f /etc/udev/rules.d/99-avell-rgb.rules
rm -f /etc/modprobe.d/avell-rgb-blacklist-clevo.conf
rm -f /etc/modules-load.d/uniwill-keyboard.conf
udevadm control --reload-rules 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

echo "Removed avell-rgb-control. The tuxedo-drivers kernel module was left installed."
