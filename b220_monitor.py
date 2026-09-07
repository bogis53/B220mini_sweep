#!/usr/bin/env python3
"""Continuous spectrum monitor with peak hold and change detection."""
import os
os.environ.setdefault("UHD_AD9361_CAL_WINDOW", "6e9")
os.environ.setdefault("UHD_AD9361_FAST_TUNE", "1")
os.environ.setdefault("UHD_IMAGES_DIR", "/usr/share/uhd/images")
import sys, time, argparse, datetime, signal
import numpy as np, uhd

p = argparse.ArgumentParser()
p.add_argument("-f", default="70:6000", help="start:stop MHz")
p.add_argument("-g", type=float, default=40)
p.add_argument("-n", type=int, default=64)
p.add_argument("-a", type=int, default=64)
p.add_argument("-w", type=float, default=50, help="MHz captured per hop")
p.add_argument("-e", type=float, default=0, help="MHz kept per hop (edge-trimmed); 0=same as -w")
p.add_argument("-t", type=float, default=8.0, help="alert threshold dB above baseline")
p.add_argument("-b", type=float, default=0.002, help="baseline update rate 0-1")
p.add_argument("-c", type=str, default="", help="write CSV of every sweep here")
p.add_argument("-T", type=float, default=0, help="stop after N seconds")
p.add_argument("--csv", action="store_true", help="stream hackrf_sweep CSV to stdout")
a = p.parse_args()

f0, f1 = [float(x)*1e6 for x in a.f.split(":")]
RATE, USE = 61.44e6, a.w*1e6
KEEPBW = (a.e*1e6 if a.e else USE)
NS = a.n*a.a + 1024

import uhd.libpyuhd as _lp
try: _lp.set_log_level(_lp.log.level.error)
except Exception: pass
u = uhd.usrp.MultiUSRP("type=b200,master_clock_rate=61.44e6")
u.set_rx_rate(RATE); u.set_rx_bandwidth(56e6)
u.set_rx_gain(a.g); u.set_rx_antenna("RX2", 0)
st = u.get_rx_stream(uhd.usrp.StreamArgs("fc32","sc16"))
md = uhd.types.RXMetadata()
buf = np.zeros((1,NS), dtype=np.complex64)

win = np.hanning(a.n); wg = 10*np.log10((win**2).sum()*a.n)
half = int(a.n*KEEPBW/RATE/2); lo, hi = a.n//2-half, a.n//2+half
centers = np.arange(f0+KEEPBW/2, f1, KEEPBW)
NB = hi-lo
freqs = np.concatenate([fc - KEEPBW/2 + (np.arange(NB)+0.5)*(KEEPBW/NB) for fc in centers])

peak = np.full(len(centers)*NB, -200.0)
base = None
run = [True]
for _s in (signal.SIGINT, signal.SIGTERM):
    signal.signal(_s, lambda *_: run.__setitem__(0, False))

def sweep():
    rows = []
    for fc in centers:
        u.set_rx_freq(uhd.types.TuneRequest(float(fc)))
        c = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
        c.num_samps = NS; c.stream_now = True
        st.issue_stream_cmd(c)
        n = st.recv(buf, md, 0.5)
        x = buf[0,1024:n]; m = len(x)//a.n
        if m < 1:
            rows.append(np.full(NB, -200.0)); continue
        seg = x[:m*a.n].reshape(m,a.n)*win
        P = (np.abs(np.fft.fftshift(np.fft.fft(seg,axis=1),axes=1))**2).mean(0)
        db = 10*np.log10(P+1e-20) - wg
        db[a.n//2] = (db[a.n//2-1]+db[a.n//2+1])/2
        rows.append(db[lo:hi])
    return np.concatenate(rows)

csvf = open(a.c, "w") if a.c else None
sw = 0
_t_start = time.time()
print("# monitoring %.0f-%.0f MHz, %d bins, %.2f MHz resolution. ctrl-C to stop."
      % (f0/1e6, f1/1e6, len(freqs), USE/NB/1e6), file=sys.stderr)
while run[0] and (a.T <= 0 or time.time()-_t_start < a.T):
    t0 = time.time()
    cur = sweep()
    sw += 1
    peak = np.maximum(peak, cur)
    if base is None:
        base = cur.copy()
    else:
        d = cur - base
        hits = np.where(d > a.t)[0]
        if len(hits) and sw > 3:
            grp = np.split(hits, np.where(np.diff(hits) > 2)[0]+1)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            for g in grp:
                i = g[np.argmax(d[g])]
                print("%s  NEW  %8.2f MHz  %+6.1f dBFS  (+%.1f dB over baseline, %d bins)"
                      % (ts, freqs[i]/1e6, cur[i], d[i], len(g)), file=sys.stderr)
        base = base*(1-a.b) + cur*a.b
    if csvf or a.csv:
        t = datetime.datetime.now()
        for k, fc in enumerate(centers):
            line = "%s, %s, %d, %d, %.2f, %d, %s" % (
                t.strftime("%Y-%m-%d"), t.strftime("%H:%M:%S.%f"),
                int(fc-KEEPBW/2), int(fc+KEEPBW/2), RATE/a.n, a.n,
                ", ".join(np.char.mod("%.2f", cur[k*NB:(k+1)*NB])))
            if csvf: csvf.write(line+"\n")
            if a.csv: print(line)
        if csvf: csvf.flush()
    if sw % 100 == 0:
        print("# sweep %d  %.0f ms  floor %.1f  peak %.1f dBFS"
              % (sw, (time.time()-t0)*1000, np.median(cur), peak.max()), file=sys.stderr)

print("\n# stopped after %d sweeps" % sw, file=sys.stderr)
top = np.argsort(peak)[-15:][::-1]
print("# strongest signals seen:", file=sys.stderr)
for i in top:
    print("#   %8.2f MHz  %+6.1f dBFS" % (freqs[i]/1e6, peak[i]), file=sys.stderr)
if csvf: csvf.close()
