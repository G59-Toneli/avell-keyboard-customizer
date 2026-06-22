#!/usr/bin/env bash
#
# Install avell-rgb-control: builds the patched tuxedo-drivers module, installs
# the udev/modprobe configs, the kbcolor + kbcolor-gui commands and a desktop
# launcher. Re-runnable (idempotent).
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo $0" >&2
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SUDO_USER:-$(logname 2>/dev/null || echo "${USER:-root}")}"
GROUP="$(id -gn "$USER_NAME")"
KVER="$(uname -r)"
TD_URL="https://gitlab.com/tuxedocomputers/development/packages/tuxedo-drivers.git"
LIBDIR="/usr/local/lib/avell-rgb-control"
PATCH="$REPO/kernel/0001-uniwill-expose-hardware-rainbow.patch"
DKMS_NAME="tuxedo-drivers-avell"
DKMS_VER="1.0.0"

USE_DKMS=0
[ "${1:-}" = "--dkms" ] && USE_DKMS=1

echo "==> Installing for user '$USER_NAME' (group '$GROUP'), kernel $KVER"

echo "==> [1/6] Building & installing the patched tuxedo-drivers module"
if [ "$USE_DKMS" -eq 1 ]; then
    # DKMS: survives kernel upgrades (rebuilds automatically).
    command -v dkms >/dev/null || {
        echo "dkms not found. Install it (e.g. 'dnf install dkms' or 'apt install dkms') and re-run." >&2
        exit 1
    }
    SRC="/usr/src/${DKMS_NAME}-${DKMS_VER}"
    dkms remove -m "$DKMS_NAME" -v "$DKMS_VER" --all >/dev/null 2>&1 || true
    rm -rf "$SRC"
    git clone --depth 1 "$TD_URL" "$SRC"
    git -C "$SRC" apply --3way "$PATCH"
    cp "$REPO/kernel/dkms.conf" "$SRC/dkms.conf"
    dkms add -m "$DKMS_NAME" -v "$DKMS_VER"
    dkms build -m "$DKMS_NAME" -v "$DKMS_VER"
    dkms install -m "$DKMS_NAME" -v "$DKMS_VER" --force
    # Drop any earlier direct-installed copies so DKMS's /updates wins cleanly.
    find "/lib/modules/$KVER/extra" -type f \
        \( -name 'tuxedo_*.ko' -o -name 'clevo_*.ko' -o -name 'uniwill_*.ko' \) -delete 2>/dev/null || true
    depmod -a
else
    # Direct build: simpler, but must be re-run after a kernel upgrade.
    BUILD="$(mktemp -d)"
    trap 'rm -rf "$BUILD"' EXIT
    git clone --depth 1 "$TD_URL" "$BUILD/tuxedo-drivers"
    git -C "$BUILD/tuxedo-drivers" apply --3way "$PATCH"
    # Build inside the tree: upstream's Makefile relies on $(PWD).
    ( cd "$BUILD/tuxedo-drivers" && make >/dev/null )
    make -C "/lib/modules/$KVER/build" M="$BUILD/tuxedo-drivers" modules_install >/dev/null
    depmod -a
fi

echo "==> [2/6] Module load/blacklist configs"
install -m0644 "$REPO/packaging/blacklist-clevo.conf"  /etc/modprobe.d/avell-rgb-blacklist-clevo.conf
install -m0644 "$REPO/packaging/uniwill-keyboard.conf" /etc/modules-load.d/uniwill-keyboard.conf

echo "==> [3/6] udev rule (sudo-less access for group '$GROUP')"
sed "s/__GROUP__/$GROUP/g" "$REPO/packaging/99-avell-rgb.rules" > /etc/udev/rules.d/99-avell-rgb.rules
udevadm control --reload-rules

echo "==> [4/6] Python package + commands"
rm -rf "$LIBDIR"
mkdir -p "$LIBDIR"
cp -r "$REPO/src/avell_rgb" "$LIBDIR/"
for entry in "kbcolor:cli" "kbcolor-gui:app"; do
    name="${entry%%:*}"; module="${entry##*:}"
    cat > "/usr/local/bin/$name" <<EOF
#!/usr/bin/env python3
import sys
sys.path.insert(0, "$LIBDIR")
from avell_rgb.$module import main
raise SystemExit(main())
EOF
    chmod 0755 "/usr/local/bin/$name"
done

echo "==> [5/6] Desktop launcher"
install -m0644 "$REPO/packaging/avell-rgb.desktop" /usr/share/applications/avell-rgb.desktop
update-desktop-database /usr/share/applications 2>/dev/null || true

echo "==> [6/6] Loading driver and applying permissions"
modprobe -r uniwill_wmi 2>/dev/null || true
modprobe -r tuxedo_keyboard 2>/dev/null || true
modprobe uniwill_wmi || true
sleep 1
P="/sys/devices/platform/tuxedo_keyboard"
LED="/sys/class/leds/rgb:kbd_backlight"
chgrp "$GROUP" "$LED"/multi_intensity "$LED"/brightness "$P"/kbd_rainbow "$P"/kbd_rainbow_speed 2>/dev/null || true
chmod 0664   "$LED"/multi_intensity "$LED"/brightness "$P"/kbd_rainbow "$P"/kbd_rainbow_speed 2>/dev/null || true

echo
echo "Done. Try:  kbcolor blue   |   kbcolor-gui   |   kbcolor rainbow --speed slow"
if [ "$USE_DKMS" -eq 1 ]; then
    echo "(DKMS: the module will rebuild automatically on kernel upgrades.)"
else
    echo "(Direct build: re-run after a kernel upgrade, or use '--dkms' for auto-rebuild.)"
fi
