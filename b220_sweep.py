#!/usr/bin/env python3
import os
os.environ.setdefault("UHD_AD9361_CAL_WINDOW", "6e9")
os.environ.setdefault("UHD_AD9361_FAST_TUNE", "1")
os.environ.setdefault("UHD_IMAGES_DIR", "/usr/share/uhd/images")
import sys, time, argparse, datetime
import numpy as np, uhd

p = argparse.ArgumentParser()
p.add_argument("-f", default="70:6000")
p.add_argument("-g", type=float, default=40)
p.add_argument("-n", type=int, default=64)
p.add_argument("-a", type=int, default=4)
p.add_argument("-1", dest="one", action="store_true")
p.add_argument("-w", type=float, default=50, help="MHz used per hop (50 fast, 30 uniform)")
a = p.parse_args()

f0, f1 = [float(x) * 1e6 for x in a.f.split(":")]
RATE, USE = 61.44e6, a.w*1e6
NS = a.n * a.a + 1024

u = uhd.usrp.MultiUSRP("type=b200,master_clock_rate=61.44e6")
u.set_rx_rate(RATE); u.set_rx_bandwidth(56e6)
u.set_rx_gain(a.g); u.set_rx_antenna("RX2", 0)
st = u.get_rx_stream(uhd.usrp.StreamArgs("fc32", "sc16"))
buf = np.zeros((1, NS), dtype=np.complex64); md = uhd.types.RXMetadata()

win = np.hanning(a.n); wg = 10 * np.log10((win ** 2).sum() * a.n)
half = int(a.n * USE / RATE / 2)
lo, hi = a.n // 2 - half, a.n // 2 + half
centers = np.arange(f0 + USE / 2, f1, USE)

while True:
    t0 = time.time(); out = []
    for fc in centers:
        u.set_rx_freq(uhd.types.TuneRequest(float(fc)))
        c = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
        c.num_samps = NS; c.stream_now = True
        st.issue_stream_cmd(c)
        n = st.recv(buf, md, 0.5)
        x = buf[0, 1024:n]
        m = len(x) // a.n
        if m < 1: continue
        seg = x[:m * a.n].reshape(m, a.n) * win
        P = (np.abs(np.fft.fftshift(np.fft.fft(seg, axis=1), axes=1)) ** 2).mean(0)
        db = 10 * np.log10(P + 1e-20) - wg
        db[a.n // 2] = (db[a.n // 2 - 1] + db[a.n // 2 + 1]) / 2
        t = datetime.datetime.now()
        out.append("%s, %s, %d, %d, %.2f, %d, %s" % (
            t.strftime("%Y-%m-%d"), t.strftime("%H:%M:%S.%f"),
            int(fc - USE / 2), int(fc + USE / 2), RATE / a.n, a.n,
            ", ".join(np.char.mod("%.2f", db[lo:hi]))))
    sys.stdout.write("\n".join(out) + "\n")
    print("# sweep %.0f ms" % ((time.time() - t0) * 1000), file=sys.stderr)
    if a.one: break
