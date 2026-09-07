# B220mini_sweep

A `hackrf_sweep`-equivalent wideband spectrum sweeper for the LibreSDR B220mini
(XC7A200T + AD9361), plus the UHD patches that make it fast.

**70 MHz - 6 GHz in 164 ms**, versus ~750 ms for hackrf_sweep over the same span.
12-bit samples instead of 8-bit, 50 MHz per hop instead of 20.

| | full sweep | rate |
|---|---|---|
| stock UHD 4.6 | ~2.8 s | 0.9 GHz/s |
| hackrf_sweep (reference) | ~750 ms | ~8 GHz/s |
| **B220mini_sweep** | **164 ms** | **36 GHz/s** |

## Where the time went

Three things in UHD, none of them the radio:

1. `AD9361_CAL_VALID_WINDOW = 100e6` (ad9361_device.cpp:85) forces a DC-offset
   and quadrature recalibration whenever you tune more than 100 MHz from the
   last cal point - ~55 ms per hop at 61.44 MHz master clock. Recal cost scales
   with ClkRF: ~105 ms at 16/32 MHz MCR, ~55 ms at 61.44.
2. A hardcoded `sleep_for(milliseconds(2))` waiting for RFPLL lock, when the
   lock bit at 0x247 / 0x287 can be polled. 70% of the remaining time.
3. `_setup_synth()` rewrites 11 registers per tune - VCO bias, varactor, charge
   pump, loop filter - mostly with values already in the register.

58 ms -> 3.0 ms -> 0.86 ms -> 0.67 ms -> 0.594 ms per hop (monotonic sweep, measured).

## Measured behaviour

Interleaved A/B/A/B sweeps, across-mode difference vs within-mode spread:

    within stock UHD (A vs A) : 2.127 dB
    within patched   (B vs B) : 2.115 dB
    across modes     (A vs B) : 2.128 dB

No measurable difference; the ~2 dB is ambient RF changing between sweeps.

RF gain is flat across the full 50 MHz hop: 0.47 dB variation centre to
+/-25 MHz, measured against a steady off-air reference carrier.

The noise floor is not flat. It rises ~15 dB from centre to +/-28 MHz. This is
internal - identical at 1.0/2.0/3.5/5.0 GHz, unchanged with 40 MHz analog
bandwidth, unchanged by custom RX FIR taps at four cutoffs. Signal power reads
correctly everywhere; SNR falls from 19 dB at centre to 11 dB at +/-25 MHz.

| -w | hops | sweep (-a 64) | noise | seam step (median) |
|---|---|---|---|---|
| 50 | 119 | 164 ms | 0.57 dB | 1.20 dB |
| 30 | 198 | 242 ms | 0.52 dB | 0.45 dB |

Use `-w 30` when you need uniform sensitivity.

Not verified: absolute frequency accuracy, absolute amplitude calibration.

## Use

    export PYTHONPATH=/usr/local/lib/python3.12/site-packages
    export UHD_IMAGES_DIR=/usr/share/uhd/images
    python3 b220_sweep.py -f 70:6000 -g 40 -a 64 > sweep.csv

Output is hackrf_sweep CSV format, so QSpectrumAnalyzer reads it unchanged.

| flag | meaning | default |
|---|---|---|
| -f | start:stop MHz | 70:6000 |
| -g | RX gain dB (0-76) | 40 |
| -n | FFT size | 64 |
| -a | averages per hop | 4 |
| -w | MHz per hop | 50 |
| -1 | one sweep then exit | continuous |

Fixed gain only, never AGC: the AD9361 gain table is non-monotonic above
3.5 GHz (~1.5-1.8 dB dips at index boundaries), so AGC crossing those mid-sweep
puts false steps in the spectrum. Run the host performance preflight first
(governor + EPP performance, hwp_dynamic_boost=1, USB autosuspend off,
rtprio 99) or 61.44 MS/s will overflow.

Patch env vars: `UHD_AD9361_CAL_WINDOW` (Hz, use 6e9) and
`UHD_AD9361_FAST_TUNE=1`. Both default to stock behaviour.

Hardware: LibreSDR B220mini, UHD-detected as B210, USB 3.0, vendor bitstream
(sources: github.com/bkerler/LibreSDR_UHD_B220_Mini_FPGA). Host i5-1135G7,
Ubuntu 24.04. Should work on a real Ettus B210; untested.

Floor is USB round trips, ~0.082 ms each, ~11 per hop. Below that needs AD9361
fastlock, but a profile is 16 bytes with only 8 on-chip slots, so host-driven
fastlock is not obviously a win for 119 hops. An FPGA hop engine would be, but
this board does not route AD9361 CTRL_IN to fabric (the XDC exposes only
CAT_TXnRX and tx_enable1/2).

Licence: GPLv3, matching UHD.
