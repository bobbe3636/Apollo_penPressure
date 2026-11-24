"""Drive Apollo's C++ virtual tablet (test_vt serve) through USB/IP the way Windows + the Wacom driver do,
and check its answers. Nothing is plugged into Windows.
    python vt_client.py intuos

With vwacom.py (the independent Python model it was ported from; not part of this repository) next to
it, or in VWACOM_DIR, the descriptors and feature reports are also compared with that model byte for
byte; without it, only their shape is checked."""
import os, socket, struct, sys, threading, time

for _dir in (os.environ.get("VWACOM_DIR"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "server")):
    if _dir:
        sys.path.insert(0, _dir)
try:
    import vwacom  # noqa: E402
except ImportError:
    vwacom = None

MODEL = sys.argv[1] if len(sys.argv) > 1 else "intuos"
HOST, PORT, UDP = "127.0.0.1", 47100, 47001
fails = []


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        fails.append(what)


def recv_exact(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


# ---------------------------------------------------------------- device list
s = socket.create_connection((HOST, PORT))
s.sendall(struct.pack(">HHI", 0x0111, 0x8005, 0))
data = b""
while True:
    c = s.recv(4096)
    if not c:
        break
    data += c
s.close()
ver, code, status, ndev = struct.unpack(">HHII", data[:12])
rec = data[12:12 + 312]
busnum, devnum, speed, vid, pid, bcd, dcls, dsub, dproto, cfgval, ncfg, nif = struct.unpack(">IIIHHHBBBBBB", rec[288:312])
ifaces = [tuple(data[12 + 312 + 4 * k:12 + 312 + 4 * k + 3]) for k in range(nif)]
print(f"devlist: {ndev} device, {vid:04x}:{pid:04x} bcdDevice {bcd:04x}, {nif} interfaces {ifaces}, {len(data)} bytes")
if MODEL == "intuos":
    d = vwacom.load_intuos_pro_m() if vwacom else None
    print("reference model: " + ("vwacom.py" if d else "none (shape checks only)"))
    check((vid, pid, bcd) == (0x056A, 0x03F7, 0x0014), "devlist: Intuos Pro M ids")
    check(nif == 3 and ifaces == [(3, 0, 0), (255, 0, 0), (3, 0, 0)], "devlist: 3 interfaces HID / vendor / HID")
    check(len(data) == 12 + 312 + 4 * 3, "devlist: record length")
else:
    check((vid, pid) == (0x056A, 0x0391), "devlist: Cintiq 22 ids")
    check(nif == 1 and ifaces == [(3, 0, 0)], "devlist: 1 HID interface")

# ---------------------------------------------------------------- import
s = socket.create_connection((HOST, PORT))
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
s.sendall(struct.pack(">HHI", 0x0111, 0x8003, 0) + b"1-1".ljust(32, b"\0"))
ver, code, status = struct.unpack(">HHI", recv_exact(s, 8))
rec2 = recv_exact(s, 312)
check(status == 0 and rec2 == rec, "import: accepted, same device record")

results, cond = {}, threading.Condition()


def reader():
    try:
        while True:
            hdr = recv_exact(s, 48)
            cmd, seq, devid, direction, ep, st, actual = struct.unpack(">IIIIIiI", hdr[:28])
            payload = recv_exact(s, actual) if cmd == 3 and direction == 1 and actual else b""
            with cond:
                results[seq] = (cmd, st, actual, payload, ep, time.perf_counter())
                cond.notify_all()
    except (ConnectionError, OSError):
        pass


threading.Thread(target=reader, daemon=True).start()
counter = [0]
DEVID = 0x00010001


def submit(ep, direction, buflen, setup=bytes(8), out=b""):
    counter[0] += 1
    s.sendall(struct.pack(">IIIIIIIIII", 1, counter[0], DEVID, direction, ep, 0, buflen, 0, 0, 0) + setup + out)
    return counter[0]


def unlink(target):
    counter[0] += 1
    s.sendall(struct.pack(">IIIIII", 2, counter[0], DEVID, 0, 0, target) + bytes(24))
    return counter[0]


def wait(seq, timeout=2.0):
    with cond:
        cond.wait_for(lambda: seq in results, timeout)
        return results.pop(seq, None)


def ctl_in(bmrt, breq, wvalue, windex, wlength):
    r = wait(submit(0, 1, wlength, struct.pack("<BBHHH", bmrt, breq, wvalue, windex, wlength)))
    return (r[1], r[3]) if r else (None, None)


def ctl_out(bmrt, breq, wvalue, windex, payload=b""):
    r = wait(submit(0, 0, len(payload), struct.pack("<BBHHH", bmrt, breq, wvalue, windex, len(payload)), payload))
    return r[1] if r else None


EPIPE = -32
# ---------------------------------------------------------------- enumeration
st, dev = ctl_in(0x80, 6, 0x0100, 0, 18)
st9, cfg9 = ctl_in(0x80, 6, 0x0200, 0, 9)
total = int.from_bytes(cfg9[2:4], "little") if cfg9 else 0
st, cfg = ctl_in(0x80, 6, 0x0200, 0, total)
strings = {k: ctl_in(0x80, 6, 0x0300 | k, 0x0409 if k else 0, 255)[1] for k in range(4)}
if MODEL == "intuos" and d:
    check(dev == d["device"], "device descriptor = vwacom")
    check(cfg == d["config"] and total == 75, f"configuration descriptor = vwacom ({total} bytes)")
    check(all(strings[k] == d["strings"][k] for k in range(4)), "strings 0-3 = vwacom (Wacom Co.,Ltd. / Wacom Intuos Pro M / 4HHS1K1000713)")
    for iface in (0, 1, 2):
        st_h, hid = ctl_in(0x81, 6, 0x2100, iface, 9)
        st_r, rep = ctl_in(0x81, 6, 0x2200, iface, 4096)
        if iface == 1:
            check(st_h == EPIPE and st_r == EPIPE, "interface 1 (vendor): HID descriptors stall")
        else:
            check(st_h == 0 and hid == d["hid_descs"][iface], f"interface {iface}: HID descriptor = vwacom")
            check(st_r == 0 and rep == d["hid_reports"][iface], f"interface {iface}: report descriptor = vwacom ({len(rep or b'')} bytes)")
elif MODEL == "intuos":
    check(dev is not None and len(dev) == 18 and dev[8:12] == bytes([0x6A, 0x05, 0xF7, 0x03]), "device descriptor: Intuos Pro M ids")
    check(cfg is not None and total == 75 and len(cfg) == 75, f"configuration descriptor ({total} bytes)")
    check(strings[2] is not None and "Intuos Pro M".encode("utf-16-le") in strings[2], "product string: Wacom Intuos Pro M")
    for iface in (0, 1, 2):
        st_h, hid = ctl_in(0x81, 6, 0x2100, iface, 9)
        st_r, rep = ctl_in(0x81, 6, 0x2200, iface, 4096)
        if iface == 1:
            check(st_h == EPIPE and st_r == EPIPE, "interface 1 (vendor): HID descriptors stall")
        else:
            check(st_h == 0 and hid and len(hid) == 9 and hid[1] == 0x21, f"interface {iface}: HID descriptor")
            check(st_r == 0 and rep and len(rep) == int.from_bytes(hid[7:9], "little"), f"interface {iface}: report descriptor ({len(rep or b'')} bytes)")
else:
    check(dev is not None and dev[8:12] == bytes([0x6A, 0x05, 0x91, 0x03]), "Cintiq device descriptor")
    st_h, hid = ctl_in(0x81, 6, 0x2100, 0, 9)
    st_r, rep = ctl_in(0x81, 6, 0x2200, 0, 4096)
    check(st_h == 0 and len(hid) == 9 and hid[1] == 0x21, "Cintiq HID descriptor (interface 0)")
    check(st_r == 0 and len(rep) == int.from_bytes(hid[7:9], "little"), f"Cintiq report descriptor ({len(rep or b'')} bytes)")
check(ctl_out(0x00, 9, 1, 0) == 0, "SET_CONFIGURATION")
check(ctl_out(0x21, 0x0A, 0, 0) == 0, "SET_IDLE interface 0")
if MODEL == "intuos":
    check(ctl_out(0x21, 0x0A, 0, 2) == 0, "SET_IDLE interface 2")
    st, f = ctl_in(0xA1, 0x01, 0x0314, 2, 14)
    check(st == EPIPE, "GET_REPORT on interface 2 stalls")

# ---------------------------------------------------------------- the Wacom driver's handshake
for rid in (0x14, 0x07, 0x0C, 0x03, 0x02, 0x04):
    st, f = ctl_in(0xA1, 0x01, 0x0300 | rid, 0, 64)
    if MODEL == "intuos" and d:
        check(st == 0 and f == d["features"][rid], f"GET_REPORT feature {rid:#04x} = vwacom ({f.hex() if f else f})")
    else:
        check(st == 0 and f and f[0] == rid, f"GET_REPORT feature {rid:#04x}")
check(ctl_out(0x21, 0x09, 0x0383, 0, bytes([0x83, 0])) == EPIPE, "SET_REPORT feature 0x83 stalls (as the real tablet)")

ep1 = []


def arm(n=1):
    for _ in range(n):
        ep1.append(submit(1, 1, 64))


def next_report(timeout=2.0):
    r = wait(ep1[0], timeout)
    if r is None:
        return None
    ep1.pop(0)
    arm()
    return r[3]


arm(8)
ep2 = submit(2, 1, 64) if MODEL == "intuos" else None
time.sleep(0.2)

check(ctl_out(0x21, 0x09, 0x0304, 0, bytes([0x04, 0x00])) == 0, "SET_REPORT feature 0x04")
if MODEL == "intuos":
    got = [next_report(), next_report()]
    check(got[0] == bytes([0x11]) + bytes(8), f"after 0x04: pad idle report 17 ({got[0].hex() if got[0] else None})")
    check(got[1] == bytes([0x13, 0xE4]) + bytes(7), f"after 0x04: battery report 19 ({got[1].hex() if got[1] else None})")
check(ctl_out(0x21, 0x09, 0x0302, 0, bytes([0x02, 0x02])) == 0, "SET_REPORT DataMode 2")
st, f = ctl_in(0xA1, 0x01, 0x0302, 0, 2)
check(f == bytes([0x02, 0x02]), "DataMode reads back 2")
if MODEL == "intuos":
    got = [next_report(), next_report()]
    check(got[0] is not None and got[0][0] == 0x11 and got[1] is not None and got[1][0] == 0x13, "after DataMode 2: pad + battery reports")
else:
    check(next_report(0.5) is None, "Cintiq: no pad/battery reports")

# ---------------------------------------------------------------- pen events (UDP, as the extra screens send them)
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


TOKEN = bytes.fromhex("00112233445566778899aabbccddeeff")  # as test_vt.cpp sets it


def send_pen(ev, x, y, pod=0.02, buttons=0, tool=1, rot=0xFFFF, tilt=0xFF, token=TOKEN):
    u.sendto(struct.pack("<4sBBBBfffHBB", b"VWP1", ev, tool, buttons, 0, x, y, pod, rot, tilt, 0) + token, (HOST, UDP))


def pen(ev, x, y, pod=0.02, buttons=0, tool=1, rot=0xFFFF, tilt=0xFF):
    send_pen(ev, x, y, pod, buttons, tool, rot, tilt)
    time.sleep(0.02)
    return next_report()


def r30(r):
    x = int.from_bytes(r[3:6], "little")
    y = int.from_bytes(r[6:9], "little")
    p, tx, ty, tw, z, dist, slo, shi, tool, scan, seq = struct.unpack("<HhhhHBIIHHH", r[9:34])
    return dict(id=r[0], contact=r[1], flags=r[2], x=x, y=y, p=p, tx=tx, ty=ty, dist=dist, slo=slo, shi=shi, tool=tool, scan=scan, seq=seq)


HOVER, DOWN, UP, MOVE, LEAVE = 0, 1, 2, 3, 6
if MODEL == "intuos":
    seqs, scans = [], []

    def expect(r, what, **want):
        if r is None or len(r) != 34:
            check(False, f"{what}: no 34-byte report ({r.hex() if r else None})")
            return
        v = r30(r)
        seqs.append(v["seq"])
        scans.append(v["scan"])
        bad = {k: (v[k], w) for k, w in want.items() if v[k] != w}
        check(v["id"] == 0x1E and not bad, f"{what}: " + (", ".join(f"{k}={v[k]:#x}" if k in ('flags', 'tool', 'slo') else f"{k}={v[k]}" for k in want) if not bad else f"got/want {bad}"))

    ident = dict(slo=0x5157A0D1, shi=0x00100842)
    expect(pen(HOVER, 0.5, 0.5), "hover centre", contact=1, flags=0xC0, x=26300, y=14800, p=0, dist=5, tool=0x842, **ident)
    expect(pen(DOWN, 0.25, 0.75, 0.5), "tip down", flags=0xC1, x=13348, y=22001, p=4095, dist=0)
    expect(pen(MOVE, 0.25, 0.75, 1.0, rot=90, tilt=40), "full pressure, tilt 40 towards the right", flags=0xC1, p=8191, tx=-40, ty=0)
    expect(pen(UP, 0.25, 0.75, 0.0), "tip up", flags=0xC0, p=0, dist=12)
    expect(pen(HOVER, 0.25, 0.75, buttons=1 | 2), "side switches 1+2", flags=0xC6)
    expect(pen(HOVER, 0.25, 0.75, buttons=4), "side switch 3", flags=0xC8)
    expect(pen(LEAVE, 0.25, 0.75), "leave: sense only, identity kept", contact=0, flags=0x80, dist=255, tool=0x842, **ident)
    expect(pen(HOVER, 0.0, 0.0, tool=2), "eraser hover at the corner", flags=0xE0, x=397, y=397, tool=0x84A)
    expect(pen(DOWN, 1.0, 1.0, 0.5, tool=2), "eraser down at the far corner", flags=0xF0, x=52203, y=29203, p=4095, tool=0x84A)
    expect(pen(UP, 1.0, 1.0, 0.0, tool=2), "eraser up", flags=0xE0, p=0)
    expect(pen(LEAVE, 1.0, 1.0, tool=2), "eraser leave", contact=0, flags=0x80, tool=0x84A, **ident)
    check(all(b - a == 1 for a, b in zip(seqs, seqs[1:])), f"sequence counter +1 per report ({seqs[0]}..{seqs[-1]})")
    steps = [(b - a) & 0xFFFF for a, b in zip(scans, scans[1:])]
    check(all(150 <= st_ <= 2000 for st_ in steps), f"scan time in 100 us units (steps {min(steps)}..{max(steps)}, ~20 ms apart)")

    # ---------------------------------------------------------------- only our extra screens feed the tablet
    send_pen(HOVER, 0.9, 0.9, token=b"")
    send_pen(HOVER, 0.9, 0.9, token=bytes(16))
    check(next_report(0.3) is None, "pen events without the token (or a wrong one) are ignored")

    # ---------------------------------------------------------------- a burst keeps every sample
    pen(HOVER, 0.5, 0.5)
    pen(DOWN, 0.5, 0.5, 0.5)
    t0 = time.perf_counter()
    for i in range(6):
        send_pen(MOVE, 0.50 + 0.01 * (i + 1), 0.5, 0.5)
    xs, times = [], []
    for i in range(6):
        r = next_report(0.5)
        if r is not None:
            xs.append(r30(r)["x"])
            times.append(time.perf_counter() - t0)
    check(len(xs) == 6 and xs == sorted(xs) and len(set(xs)) == 6, f"6 moves sent at once: 6 reports, in order ({len(xs)} got)")
    check(len(times) == 6 and 0.006 <= times[-1] <= 0.1, f"...played out a little apart ({times[-1] * 1000:.1f} ms for the 6)" if times else "no reports")
    pen(UP, 0.56, 0.5, 0.0)

    # ---------------------------------------------------------------- the other end of the pen while in range
    send_pen(HOVER, 0.5, 0.5, tool=2)
    time.sleep(0.02)
    expect(next_report(), "eraser while the pen is in range: the pen leaves first", contact=0, flags=0x80, tool=0x842)
    expect(next_report(), "...then the eraser arrives", contact=1, flags=0xE0, tool=0x84A)
    pen(LEAVE, 0.5, 0.5, tool=2)
    seqs.clear()
    scans.clear()

    st_in, rep = ctl_in(0xA1, 0x01, 0x011E, 0, 64)
    check(st_in == 0 and rep and len(rep) == 34 and rep[0] == 0x1E, "GET_REPORT input 30")
    st_in, rep = ctl_in(0xA1, 0x01, 0x0110, 0, 64)
    check(st_in == EPIPE, "GET_REPORT input 0x10 stalls on the Intuos")

    # ---------------------------------------------------------------- other endpoints
    r = wait(ep2, 0.3)
    check(r is None, "EP2 IN (interface 2) stays pending")
    r = wait(unlink(ep2))
    check(r is not None and r[0] == 4 and r[1] == -104, f"unlink EP2 URB -> RET_UNLINK ECONNRESET ({r[1] if r else None})")
    check(wait(ep2, 0.3) is None, "no RET_SUBMIT for the unlinked URB")
    r = wait(submit(4, 0, 16, out=bytes(range(16))))
    check(r is not None and r[1] == 0 and r[2] == 16, f"EP4 bulk OUT accepted, actual length {r[2] if r else None}")

    # ---------------------------------------------------------------- periodic battery while the pen is away
    t0 = time.perf_counter()
    rep = next_report(12.0)
    check(rep == bytes([0x13, 0xE4]) + bytes(7), f"battery report repeated while idle (after {time.perf_counter() - t0:.1f} s)")
else:
    r = pen(HOVER, 0.5, 0.5)
    check(r is not None and r[0] == 0x10 and r[1] == 0x60, f"Cintiq hover: report 0x10 flags 0x60 ({r.hex() if r else None})")
    x = int.from_bytes(r[2:5], "little") if r else 0
    check(x == 48006, f"Cintiq X = 0.5 * 96012 ({x})")
    r = wait(submit(4, 0, 16, out=bytes(16)))
    check(r is not None and r[1] == EPIPE, "Cintiq: other endpoints stall")

s.close()
print(f"\n{MODEL}: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
