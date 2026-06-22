# Kernel patch — expose the Uniwill hardware rainbow

`0001-uniwill-expose-hardware-rainbow.patch` adds two sysfs attributes to the
`tuxedo-drivers` Uniwill keyboard driver, on the `tuxedo_keyboard` platform
device:

| Attribute | Access | Meaning |
|-----------|--------|---------|
| `kbd_rainbow` | read/write | `1` enable / `0` disable the firmware color-cycle (bit `0x80` of EC reg `0x0767`) |
| `kbd_rainbow_speed` | read/write | `0–255` effect speed, EC reg `0x0768` (higher = slower) |

Upstream already *defines* the rainbow bit but never exposes it. The patch only
touches `src/uniwill_interfaces.h` (one register define) and
`src/uniwill_keyboard.h` (the two attributes + their registration), and writes
exclusively to the keyboard RGB register block — no generic EC access.

## License

`tuxedo-drivers` is **GPL-2.0-or-later**, so this patch (and any module built
from it) is GPL-2.0+ as well — independent of the MIT license used by the
userspace app in this repository.

## Build & install

Requires kernel headers (`kernel-devel` on Fedora, `linux-headers-$(uname -r)`
on Debian/Ubuntu), `gcc`, `make`, `git`. With Secure Boot **off**, unsigned
modules load without MOK enrolment.

```bash
git clone https://gitlab.com/tuxedocomputers/development/packages/tuxedo-drivers.git
cd tuxedo-drivers
git apply /path/to/this/repo/kernel/0001-uniwill-expose-hardware-rainbow.patch

make
sudo make -C /lib/modules/$(uname -r)/build M="$PWD" modules_install
sudo depmod -a

# Uniwill barebones autoload via WMI; load now and on boot:
sudo modprobe uniwill_wmi
echo uniwill_wmi | sudo tee /etc/modules-load.d/uniwill-keyboard.conf
```

Verify:

```bash
cat /sys/devices/platform/tuxedo_keyboard/kbd_rainbow        # 0 or 1
cat /sys/devices/platform/tuxedo_keyboard/kbd_rainbow_speed  # 0..255
```

`../scripts/install.sh` automates all of the above and also installs the udev
rule that makes these attributes (and the LED) writable without `sudo`.

> **Not DKMS.** A plain `modules_install` does not survive a kernel upgrade —
> rebuild after upgrading, or package the patched tree with DKMS for persistence.
> Upstreaming these attributes to `tuxedo-drivers` would remove the need for the
> patch entirely; contributions welcome.
