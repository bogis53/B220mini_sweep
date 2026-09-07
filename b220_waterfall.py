#!/usr/bin/env python3
"""Live waterfall for b220 CSV on stdin."""
import sys, time, argparse, numpy as np
import matplotlib; matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("-r", type=int, default=400, help="history rows")
ap.add_argument("-d", type=float, default=0.15, help="redraw interval s")
ap.add_argument("-k", type=float, default=0.995, help="peak decay per sweep (1=hold forever)")
ap.add_argument("-c", default="turbo", help="colormap")
ap.add_argument("--floor", type=float, default=0, help="fix colour floor dBFS (0=auto)")
ap.add_argument("--ceil", type=float, default=0, help="fix colour ceiling dBFS (0=auto)")
ap.add_argument("--snr", type=float, default=3.0, help="colour floor = noise + this many dB")
ap.add_argument("--bands", action="store_true", help="mark known allocations")
ap.add_argument("--trim", type=float, default=0, help="drop this %% of bins at each hop edge")
a = ap.parse_args()

plt.rcParams.update({"figure.facecolor":"#111","axes.facecolor":"#111",
    "axes.edgecolor":"#555","text.color":"#ddd","axes.labelcolor":"#ddd",
    "xtick.color":"#aaa","ytick.color":"#aaa","font.size":9})
fig, (ax1, ax2) = plt.subplots(2,1,figsize=(14,9),
        gridspec_kw={"height_ratios":[1,3],"hspace":0.12})

bins={}; freqs=None; rows=[]; peak=None; img=None
lv=pk=None; last=0.0; clim=None; n=0

for ln in sys.stdin:
    if not ln.strip() or ln.startswith("#"): continue
    f = ln.split(", ")
    try:
        lo, hi = int(f[2]), int(f[3]); v = np.asarray(f[6:], dtype=float)
    except Exception: continue
    if a.trim > 0 and len(v) > 8:
        k = int(len(v)*a.trim/100.0)
        if k > 0:
            step=(hi-lo)/len(v); lo=int(lo+k*step); hi=int(hi-k*step); v=v[k:len(v)-k]
    bins[lo] = (hi, v)
    ks = sorted(bins)
    cur = np.concatenate([bins[k][1] for k in ks])
    fr  = np.concatenate([np.linspace(k, bins[k][0], len(bins[k][1])) for k in ks])/1e6

    if freqs is None or len(fr) != len(freqs):
        freqs, rows, peak, n = fr, [cur], cur.copy(), 0
        ax1.clear(); ax2.clear()
        pk, = ax1.plot(freqs, peak, lw=0.8, color="#ff5c39", alpha=.85, label="peak")
        lv, = ax1.plot(freqs, cur,  lw=0.9, color="#4fc3f7", label="live")
        ax1.set_ylabel("dBFS"); ax1.grid(alpha=.15, color="#444")
        ax1.set_xlim(freqs[0], freqs[-1])
        ax1.legend(loc="upper right", fontsize=8, facecolor="#222", labelcolor="#ddd")
        ax1.set_xticklabels([])
        img = ax2.imshow(np.array(rows), aspect="auto", origin="lower", cmap=a.c,
                         extent=[freqs[0],freqs[-1],0,1], interpolation="nearest")
        ax2.set_xlabel("MHz"); ax2.set_ylabel("sweeps ago")
        if a.bands:
            BANDS=[(2401,2423,"wifi1"),(2426,2448,"wifi6"),(2451,2473,"wifi11"),
                   (2402,2403,"BLE37"),(2426,2427,"BLE38"),(2480,2481,"BLE39"),
                   (88,108,"FM"),(470,694,"DTT"),(791,821,"LTE800"),
                   (925,960,"GSM900"),(1805,1880,"LTE1800"),(2110,2170,"UMTS"),
                   (2620,2690,"LTE2600"),(5150,5350,"UNII-1/2"),(5470,5725,"UNII-2e"),
                   (5725,5875,"UNII-3")]
            for b0,b1,nm in BANDS:
                if b1 < freqs[0] or b0 > freqs[-1]: continue
                for ax in (ax1,ax2):
                    ax.axvspan(max(b0,freqs[0]), min(b1,freqs[-1]),
                               color="#ffffff", alpha=.02, zorder=0)
                ax1.text((max(b0,freqs[0])+min(b1,freqs[-1]))/2, .97, nm,
                         transform=ax1.get_xaxis_transform(), ha="center", va="top",
                         fontsize=7, color="#88aacc")
        def _click(ev):
            if ev.inaxes and ev.xdata is not None:
                i=int(np.argmin(np.abs(freqs-ev.xdata)))
                print("  %.3f MHz   live %+6.1f   peak %+6.1f dBFS"
                      % (freqs[i], rows[-1][i], peak[i]), file=sys.stderr)
        fig.canvas.mpl_connect("button_press_event", _click)
        if a.bands:
            BANDS=[(2401,2423,"wifi1"),(2426,2448,"wifi6"),(2451,2473,"wifi11"),
                   (2402,2403,"BLE37"),(2426,2427,"BLE38"),(2480,2481,"BLE39"),
                   (88,108,"FM"),(470,694,"DTT"),(791,821,"LTE800"),
                   (925,960,"GSM900"),(1805,1880,"LTE1800"),(2110,2170,"UMTS"),
                   (2620,2690,"LTE2600"),(5150,5350,"UNII-1/2"),(5470,5725,"UNII-2e"),
                   (5725,5875,"UNII-3")]
            for b0,b1,nm in BANDS:
                if b1 < freqs[0] or b0 > freqs[-1]: continue
                for ax in (ax1,ax2):
                    ax.axvspan(max(b0,freqs[0]), min(b1,freqs[-1]),
                               color="#ffffff", alpha=.02, zorder=0)
                ax1.text((max(b0,freqs[0])+min(b1,freqs[-1]))/2, .97, nm,
                         transform=ax1.get_xaxis_transform(), ha="center", va="top",
                         fontsize=7, color="#88aacc")
        def _click(ev):
            if ev.inaxes and ev.xdata is not None:
                i=int(np.argmin(np.abs(freqs-ev.xdata)))
                print("  %.3f MHz   live %+6.1f   peak %+6.1f dBFS"
                      % (freqs[i], rows[-1][i], peak[i]), file=sys.stderr)
        fig.canvas.mpl_connect("button_press_event", _click)
        if a.bands:
            BANDS=[(2401,2423,"wifi1"),(2426,2448,"wifi6"),(2451,2473,"wifi11"),
                   (2402,2403,"BLE37"),(2426,2427,"BLE38"),(2480,2481,"BLE39"),
                   (88,108,"FM"),(470,694,"DTT"),(791,821,"LTE800"),
                   (925,960,"GSM900"),(1805,1880,"LTE1800"),(2110,2170,"UMTS"),
                   (2620,2690,"LTE2600"),(5150,5350,"UNII-1/2"),(5470,5725,"UNII-2e"),
                   (5725,5875,"UNII-3")]
            for b0,b1,nm in BANDS:
                if b1 < freqs[0] or b0 > freqs[-1]: continue
                for ax in (ax1,ax2):
                    ax.axvspan(max(b0,freqs[0]), min(b1,freqs[-1]),
                               color="#ffffff", alpha=.02, zorder=0)
                ax1.text((max(b0,freqs[0])+min(b1,freqs[-1]))/2, .97, nm,
                         transform=ax1.get_xaxis_transform(), ha="center", va="top",
                         fontsize=7, color="#88aacc")
        def _click(ev):
            if ev.inaxes and ev.xdata is not None:
                i=int(np.argmin(np.abs(freqs-ev.xdata)))
                print("  %.3f MHz   live %+6.1f   peak %+6.1f dBFS"
                      % (freqs[i], rows[-1][i], peak[i]), file=sys.stderr)
        fig.canvas.mpl_connect("button_press_event", _click)
        if a.bands:
            BANDS=[(2401,2423,"wifi1"),(2426,2448,"wifi6"),(2451,2473,"wifi11"),
                   (2402,2403,"BLE37"),(2426,2427,"BLE38"),(2480,2481,"BLE39"),
                   (88,108,"FM"),(470,694,"DTT"),(791,821,"LTE800"),
                   (925,960,"GSM900"),(1805,1880,"LTE1800"),(2110,2170,"UMTS"),
                   (2620,2690,"LTE2600"),(5150,5350,"UNII-1/2"),(5470,5725,"UNII-2e"),
                   (5725,5875,"UNII-3")]
            for b0,b1,nm in BANDS:
                if b1 < freqs[0] or b0 > freqs[-1]: continue
                for ax in (ax1,ax2):
                    ax.axvspan(max(b0,freqs[0]), min(b1,freqs[-1]),
                               color="#ffffff", alpha=.02, zorder=0)
                ax1.text((max(b0,freqs[0])+min(b1,freqs[-1]))/2, .97, nm,
                         transform=ax1.get_xaxis_transform(), ha="center", va="top",
                         fontsize=7, color="#88aacc")
        def _click(ev):
            if ev.inaxes and ev.xdata is not None:
                i=int(np.argmin(np.abs(freqs-ev.xdata)))
                print("  %.3f MHz   live %+6.1f   peak %+6.1f dBFS"
                      % (freqs[i], rows[-1][i], peak[i]), file=sys.stderr)
        fig.canvas.mpl_connect("button_press_event", _click)
        fig.tight_layout(); plt.ion(); plt.show(); continue

    n += 1
    rows.append(cur)
    if len(rows) > a.r: rows.pop(0)
    peak = np.maximum(peak*a.k + cur*(1-a.k), cur)

    if time.time()-last < a.d: continue
    last = time.time()
    arr = np.array(rows)
    if clim is None or n % 40 == 0:
        nf = np.median(np.percentile(arr, 25, axis=0))
        f_ = a.floor if a.floor else nf + a.snr
        c_ = a.ceil  if a.ceil  else np.percentile(arr, 99.9)
        clim = (f_, max(c_, f_+12))
    lv.set_ydata(cur); pk.set_ydata(peak)
    ax1.set_ylim(clim[0]-6, peak.max()+4)
    img.set_data(arr[::-1]); img.set_clim(*clim)
    img.set_extent([freqs[0], freqs[-1], 0, len(rows)])
    ax2.set_ylim(0, len(rows))
    ax1.set_title("%.0f-%.0f MHz   %d bins @ %.0f kHz   sweep %d"
        % (freqs[0], freqs[-1], len(freqs), (freqs[1]-freqs[0])*1000, n),
        color="#ddd", fontsize=10)
    fig.canvas.draw_idle(); fig.canvas.flush_events()
plt.ioff(); plt.show()
