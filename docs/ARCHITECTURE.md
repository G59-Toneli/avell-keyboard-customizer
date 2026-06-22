# Architecture & design notes

## The problem in one sentence

Drive a slow, partly-undocumented embedded controller (EC) from a desktop app
that must feel instant — without the keyboard lagging or the code turning into a
tangle of sysfs writes.

## Layers

Dependencies point inward; each layer only knows about the ones below it.

| Layer | Module(s) | Responsibility | Depends on |
|-------|-----------|----------------|------------|
| Domain | `color`, `state` | Immutable value objects + pure color math | nothing |
| Ports & adapters | `backend` | `KeyboardBackend` interface + `SysfsKeyboardBackend` | domain |
| Application | `controller` | Async worker + pure `plan_transition` | domain, port |
| Presentation | `widgets`, `app`, `cli` | Tk widgets, GUI wiring, CLI | application, domain |

The **composition roots** (`app.main`, `cli.main`) are the only places that
instantiate the concrete `SysfsKeyboardBackend` and inject it. Everything else
talks to the abstraction.

## SOLID, concretely

- **S**ingle responsibility — color math, hardware I/O, scheduling, and drawing
  live in separate modules.
- **O**pen/closed — adding a backend (a mock, or a future per-key device) means
  a new `KeyboardBackend` subclass; the controller and UI don't change.
- **L**iskov — every backend honors the same contract, so the fake used in tests
  is a drop-in for the real one.
- **I**nterface segregation — `KeyboardBackend` is small and fine-grained
  (`apply_color`, `apply_brightness`, `set_rainbow`, `set_rainbow_speed`), which
  is exactly what lets the controller write *only what changed*.
- **D**ependency inversion — `BacklightController` and the GUI depend on the
  `KeyboardBackend` abstraction; the sysfs detail is injected at the edge.

## Two hardware findings that shaped the design

### 1. The EC is slow (~0.5 s/write)

Measured directly:

```
$ time echo "0 255 0" > /sys/class/leds/rgb:kbd_backlight/multi_intensity
# median ~489 ms per write
```

Implications:

- **Never block the UI on a write.** `BacklightController` owns one worker
  thread. Callers publish a desired `BacklightState` via `request()` and return
  immediately.
- **Coalesce — latest wins.** While a write is in flight, new requests just
  overwrite the pending target. When the worker is free it applies whatever the
  *current* target is and discards everything in between. Dragging produces a
  smooth UI and the keyboard converges to wherever the pointer landed, instead of
  replaying a backlog.
- **Write the minimum.** `plan_transition(previous, target)` is a pure function
  returning the ordered list of operations actually needed (e.g. a hue drag emits
  a single `SET_COLOR`, not color+brightness). It is trivially unit-tested.

```
UI thread ──request(state)──▶ [target]  ◀── coalesced, lock-protected
                                  │
                          worker thread: plan_transition(applied, target) ──▶ backend
```

### 2. The rainbow belongs in firmware

A software rainbow is impossible to make smooth at ~2 writes/second — you see
each step. But the EC exposes a hardware color-cycle:

```c
#define UW_EC_REG_KBD_BL_RGB_MODE          0x0767
#define UW_EC_REG_KBD_BL_RGB_MODE_BIT_RAINBOW 0x80   // firmware-driven cycle
#define UW_EC_REG_KBD_BL_RGB_SPEED         0x0768    // higher = slower (found empirically)
```

`tuxedo-drivers` defines the rainbow bit but never exposes it. The
[patch](../kernel/) adds two named, validated sysfs attributes
(`kbd_rainbow`, `kbd_rainbow_speed`) on the platform device. The app simply
toggles the firmware effect and sets its speed — perfectly smooth, no per-frame
writes. During the cycle the UI animates only its own preview swatch (cosmetic);
it does not touch the picker, so it never "fights" the user.

> The speed register was discovered by probing the keyboard RGB block of the EC.
> The patch deliberately exposes only the two specific, named registers — not an
> arbitrary EC poke interface — so the public driver change stays safe and
> reviewable.

## Why a desktop app and not a web UI

An earlier prototype served a local web page + a tiny HTTP server. It worked but
added moving parts (a server process, a port, browser-tab lifecycle) that each
failed in their own way — "sometimes it applies, sometimes it doesn't." The
native Tk app writes straight to sysfs in-process: fewer layers, deterministic,
no daemon to leak. The lesson — fewer moving parts beat a prettier stack when the
goal is reliability — is itself part of the design.

## Testing strategy

- `plan_transition` and `Color` are pure → exhaustively unit-tested without
  hardware (`tests/test_planner.py`, `tests/test_color.py`).
- The controller is tested through a `FakeBackend` injected via its constructor,
  proving the async path and ordering without a real keyboard
  (`tests/test_controller.py`).
- The sysfs adapter is the only untested-by-unit part by design (it *is* the I/O
  boundary); it is exercised manually / on the target device.
