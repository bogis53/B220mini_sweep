#!/usr/bin/env python3
"""Emitter classification from b220 CSV on stdin."""
import sys, time, argparse, numpy as np
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument("-t", type=float, default=8.0, help="detect dB above noise")
ap.add_argument("-m", type=int, default=2, help="min contiguous bins")
ap.add_argument("-i", type=float, default=10.0, help="report interval s")
ap.add_argument("-q", action="store_true", help="only report at intervals")
a = ap.parse_args()

# (lo MHz, hi MHz, name, expected BW MHz or None)
ALLOC = [(87.5,108,"FM broadcast",0.2),(108,137,"aeronautical",0.025),
    (144,148,"amateur 2m",0.012),(174,230,"DAB/VHF-III",1.5),
    (380,400,"TETRA",0.025),(430,440,"ISM 433/amateur",0.05),
    (470,694,"DTT broadcast",8.0),(694,790,"LTE700",10),
    (791,821,"LTE800 DL",10),(869,894,"GSM850 DL",0.2),
    (925,960,"GSM900 DL",0.2),(1452,1492,"L-band DL",5),
    (1575.3,1575.5,"GPS L1",2),(1805,1880,"LTE1800 DL",10),
    (1930,1990,"PCS DL",5),(2110,2170,"UMTS/LTE2100 DL",5),
    (2400,2483.5,"ISM 2.4",None),(2620,2690,"LTE2600 DL",10),
    (3400,3800,"5G n78",20),(5150,5350,"WiFi UNII-1/2",20),
    (5470,5725,"WiFi UNII-2e",20),(5725,5875,"ISM 5.8",20)]
BLE_ADV = [2402,2426,2480]
WIFI24 = {1:2412,2:2417,3:2422,4:2427,5:2432,6:2437,7:2442,
          8:2447,9:2452,10:2457,11:2462,12:2467,13:2472}

def classify(fc, bw, duty, n_seen):
    for lo,hi,name,ebw in ALLOC:
        if lo <= fc <= hi:
            if 2400 <= fc <= 2483.5:
                if bw < 0.8:
                    return "narrow / fragment", name
                if 0.8 <= bw <= 3.0 and any(abs(fc-b) < 1.5 for b in BLE_ADV):
                    return "BLE advertising", name
                if 1.2 <= bw <= 3.0 and abs(fc-2402-round((fc-2402)/2.0)*2.0) < 0.5:
                    return "BLE data", name
                if bw < 4.0:
                    return "narrowband unknown", name
                if 8 < bw < 32:
                    ch = min(WIFI24, key=lambda c: abs(WIFI24[c]-fc))
                    if abs(WIFI24[ch]-fc) < 6:
                        return "WiFi ch%d" % ch, name
                    return "WiFi-like", name
                if bw > 30: return "wideband / multiple", name
                return "unknown ISM", name
            if ebw and bw > ebw*3:  return "wideband in %s" % name, name
            if duty > 0.9:          return "continuous carrier", name
            if duty < 0.2:          return "bursty", name
            return "in-band", name
    if duty > 0.9: return "UNALLOCATED continuous", "-"
    return "UNALLOCATED bursty", "-"

tracks = defaultdict(lambda: dict(n=0, seen=0, pk=-200.0, first=time.time(), bw=[]))
bins={}; freqs=None; nf=None; hist=[]; sw=0; last=time.time()

for ln in sys.stdin:
    if not ln.strip() or ln.startswith("#"): continue
    f = ln.split(", ")
    try:
        lo,hi = int(f[2]), int(f[3]); v = np.asarray(f[6:], dtype=float)
    except Exception: continue
    bins[lo]=(hi,v)
    ks=sorted(bins)
    cur=np.concatenate([bins[k][1] for k in ks])
    fr=np.concatenate([np.linspace(k,bins[k][0],len(bins[k][1])) for k in ks])/1e6
    if freqs is None or len(fr)!=len(freqs):
        freqs=fr; hist=[cur]; continue
    hist.append(cur)
    if len(hist)>200: hist.pop(0)
    sw += 1
    if sw < 12: continue
    arr=np.array(hist)
    nf=np.percentile(arr,25,axis=0)
    k=max(9, int(len(nf)/80)|1)
    pad=np.pad(nf,(k//2,k//2),mode='edge')
    nf=np.array([np.median(pad[j:j+k]) for j in range(len(nf))])
    hot=np.where(cur > nf + a.t)[0]
    if len(hot):
        for g in np.split(hot, np.where(np.diff(hot)>2)[0]+1):
            if len(g) < a.m: continue
            i=g[np.argmax(cur[g])]
            fc=float(freqs[g].mean()); bw=float(freqs[g[-1]]-freqs[g[0]])+ (freqs[1]-freqs[0])
            step = 1.0 if bw < 3 else 10.0
            key = round(fc/step)*step
            t=tracks[key]
            t['n']+=1; t['seen']=sw; t['pk']=max(t['pk'],cur[i])
            t['bw'].append(bw)
            t.setdefault('fcs',[]).append(fc)
            if len(t['fcs'])>50: t['fcs'].pop(0)
            if len(t['fcs'])>50: t['fcs'].pop(0)
            if len(t['bw'])>50: t['bw'].pop(0)
            _n=min(len(t['bw']),len(t['fcs']))
            _b=np.array(t['bw'][-_n:]); _f=np.array(t['fcs'][-_n:])
            _m=_b >= np.percentile(_b,75)
            t['fc']=float(np.median(_f[_m])) if _m.any() else float(np.median(_f))
            if len(t['bw'])>50: t['bw'].pop(0)
    if time.time()-last >= a.i:
        last=time.time()
        act={k:v for k,v in tracks.items() if v['n']>=3 and sw-v['seen']<400}
        act={k:v for k,v in act.items() if np.percentile(v['bw'],90) >= 0.5}
        wide=[(v['fc'], np.percentile(v['bw'],90)) for v in act.values()
              if np.percentile(v['bw'],90) > 8]
        act={k:v for k,v in act.items()
             if np.percentile(v['bw'],90) > 8 or
                not any(abs(v['fc']-wf) < wb/2 for wf,wb in wide)}
        print("\n=== %d emitters, sweep %d ===" % (len(act), sw), file=sys.stderr)
        print("%10s %8s %6s %-24s %s" % ("MHz","peak","BW","classification","allocation"), file=sys.stderr)
        for k,v in sorted(act.items(), key=lambda kv:-kv[1]['pk'])[:20]:
            bw=float(np.percentile(v['bw'],90)); duty=v['n']/max(sw-11,1)
            cls,alloc=classify(v['fc'],bw,duty,v['n'])
            print("%10.2f %+7.1f %6.2f %-24s %s" %
                  (v['fc'], v['pk'], bw, cls, alloc), file=sys.stderr)
