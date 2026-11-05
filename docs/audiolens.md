# AudioLens (VS Code extension), plus IDE-free spectrogram viewers

**What it is:** AudioLens is a VS Code extension that opens audio files as a waveform and
spectrogram viewer inside the editor. It's what he uses at 1:24, 1:37, and 1:44. I identified it from
the exact set of "Selection analysis" metrics in the frame (RMS, Peak, Dominant, Crest, Clipping,
Noise floor, Centroid, ZCR, band percentages) and the settings panel (Rose palette, zero padding
factor, "Max follows Nyquist").

- Repo / README: <https://github.com/SimZhou/vscode-audiolens>
- Marketplace: `simzhou.audiolens` (<https://marketplace.visualstudio.com/items?itemName=simzhou.audiolens>)
- Open VSX (for VSCodium): <https://open-vsx.org/extension/simzhou/audiolens>
- Install: `code --install-extension simzhou.audiolens`

**On Linux:** VS Code and VSCodium both run on Linux. The README doesn't state OS support outright,
but it documents Windows/Linux key bindings (Ctrl+wheel to zoom time, Alt+wheel for amplitude), so
Linux is an intended target. It can also be used over Remote-SSH. Formats: WAV (multichannel),
MP3, FLAC, OGG, Opus, M4A/AAC, and raw PCM with explicit sample rate and encoding.

Since you'd rather avoid an IDE, most of this doc covers **Sonic Visualiser**, which does everything
he does here and more as a standalone Linux app. It also covers **inspectrum**, the RF/IQ equivalent.

![AudioLens settings at 1:44](../frames/1_44.jpg)

## How he uses it

- **He scrubs an hour-long file** (`21:21 / 60:00`) by dragging the yellow timeline label. He
  plays sections to hear what's there.
- **He zooms into the right band before anything is visible** (1:30): "It's only when I zoom into
  the right frequency, and then increase the resolution, that you start to see it." His settings at
  1:44 are window size 2048, Hamming, zero padding 1, linear frequency scale, display range
  5–800 Hz (down from 8 kHz), Rose palette, gain 20 dB, auto brightness off.
- **He uses Selection analysis** (1:24). Dragging a 4.5 s selection reports RMS −59.6 dBFS, noise
  floor −63 dBFS, dominant frequency 22 Hz, and 82% of the energy in 0–250 Hz. That's a fast sanity
  check of "is there anything here, and where in frequency?"
- **The viewer lives next to the code**: he opens a WAV in the editor where his scripts are. That's
  the only real advantage over a standalone app.

## Concepts that matter more than the tool

**Resolution trade-off.** Bin width is Δf = fs/N and the window is N/fs seconds long. At fs = 8 kHz,
N = 4096 gives 1.95 Hz bins and a 0.51 s window.

**A rule of thumb for chirps** (Doppler curves are chirps): the sharpest line comes from a window
T ≈ 1/√|df/dt|. A propeller plane's harmonic sweeping at ~1 Hz/s wants T ≈ 1 s, so N ≈ fs. A
satellite carrier sweeping at ~100 Hz/s wants T ≈ 0.1 s. Use bigger windows for slow sweeps and
smaller ones for fast sweeps. Zero padding only interpolates the display; it doesn't add resolution.

**Display range vs. analysis.** Narrowing the displayed band (AudioLens' "display only" range) gives
more pixels per Hz, which is half of "zoom in and it appears." The other half is gain and range
(color contrast).

**Harmonics.** A propeller produces a comb at multiples of the blade-pass frequency. All harmonics
share the same *fractional* Doppler shift. That lets you prove that lines belong to one source, and
lets you fit whichever harmonic is clearest. In the synthetic recording the 96 Hz fundamental is
buried in wind rumble, so fit harmonic 3 or 4.

## IDE-free alternative 1: Sonic Visualiser (recommended)

Free, cross-platform (Linux packages/AppImage), built for *looking at* audio:
<https://www.sonicvisualiser.org>. Reference manual (4.1):
<https://sonicvisualiser.org/doc/reference/4.1/en>.

### Mapping his AudioLens settings to Sonic Visualiser

Layer → Add Spectrogram, then use the layer's property box on the right.

| AudioLens (1:44) | Sonic Visualiser |
|---|---|
| Window size 2048 | **Window Size** (spectrogram property) |
| — (hop) | **Window Overlap** (fraction of window). Raise it to sharpen time resolution. |
| Window type Hamming | Global: Preferences → **Spectral analysis window shape** (Hann default) |
| Zero padding factor | **Oversampling** (1x/2x/4x/8x) |
| Frequency scale Linear | **Frequency Scale** (linear / log) |
| Min/max frequency 5–800 | Zoom the vertical scale, or use the **Melodic Range Spectrogram** preset (≈40 Hz–1.5 kHz, log, large overlapped windows), which suits 50–500 Hz engine tones well |
| Gain 20 dB / Range | **Gain**, **Colour Scale** (dBV, etc.), **Threshold**, **Normalization** (Col / View / Hybrid) |
| Palette Rose | **Colour** |

### Things AudioLens can't do

- **Peak Frequency Spectrogram** (Layer → Add Peak Frequency Spectrogram). It draws each spectral
  peak at a phase-refined instantaneous frequency, so Doppler lines get much thinner than the bin
  width. It's also exportable to CSV.
- **Harmonic cursor.** With the measure tool (key `6`), hovering over a spectrogram draws ticks at
  2×, 3×, … of the frequency under the pointer. Use it to check that lines belong to one source.
- **Manual tracing to CSV.** Add a **Time Values** layer, use the draw tool (key `4`), and click
  along a curve. Edit points with key `3` or Layer → *Edit Layer Data*. Then File → **Export
  Annotation Layer** as `.csv`. This is his "I just traced it with a line" (23:30) as a reusable
  workflow.
- **Vamp plugins** (Transform menu). Analysis plugins add derived layers automatically. Install
  plugin packs from <https://vamp-plugins.org>; a pitch tracker such as pYIN can follow a curve for
  you. Expect a fundamental tracker to need help on noisy, multi-harmonic plane sounds.
- **Panes and layers**: stack several spectrograms with different window sizes over the same time
  axis.

## IDE-free alternative 2: inspectrum (for your RF / IQ recordings)

<https://github.com/miek/inspectrum>. It's the closest RF equivalent of what he does with audio. It
opens raw IQ captures (`.cf32`, `.cs8`, `.cu8`, `.cs16`, …, from RTL-SDR, HackRF, BladeRF, or your
own recorder), handles files of 100 GB and more, and has cursors for measuring period and symbol
rate. Select a signal to add derived plots (amplitude, frequency, phase). The frequency plot of a
satellite or aircraft carrier *is* its Doppler curve. Packaged on most distros (`inspectrum`).

## IDE-free alternative 3: a Python one-liner page

`uv run tutorials/doppler_explorer.py file.wav --t0 … --t1 … --fmax …` writes a self-contained
HTML spectrogram with a live Doppler model. See [plotly-html.md](plotly-html.md).

## Existing tutorials

- **AudioLens README**: controls table (Space, Esc, Ctrl+wheel, Shift+wheel, Alt+wheel,
  Ctrl+F reset).
- **Sonic Visualiser reference manual 4.1**: read §6.3 (spectrogram and presets), §6.6 (time
  values), §8 (measurement), §12.5 (export).
- **[Audacity Spectrogram View](https://manual.audacityteam.org/man/spectrogram_view.html)**: if
  you'd rather do this in Audacity (see [audacity.md](audacity.md)).

The existing material teaches buttons, not how to *find* a faint line. That's what the tutorial
below is for.

## Tutorial: find, prove, and measure two faint flyovers

Generate the data once: `uv run tutorials/make_dataset.py --out data`. Don't open `data/TRUTH.json`.

### 1. Blind search

1. Open `data/recording.wav` (23 minutes, 8 kHz) in Sonic Visualiser or AudioLens.
2. The default full-band spectrogram shows wind gusts, birds at 2–4 kHz, and not much else.
3. Find **two** aircraft flyovers and write down approximate times. Things to try: limit the display
   to under 800 Hz, try N = 2048, 4096, and 8192, raise the gain, and switch to log frequency.
4. Which window size makes the lines sharpest, and does that match the 1/√(df/dt) rule above?

### 2. Prove they're harmonics

With the harmonic cursor, show that event 1's visible lines are k × f0 for one f0. Estimate f0, and
explain why you can't see the fundamental itself.

### 3. Trace

1. Add a Time Values layer and click 30–50 points along the clearest harmonic of event 1.
2. Export the layer to CSV and rename the columns to `t_s,f_hz`. The doppler_explorer page's "Copy
   trace CSV" button produces the same file.
3. Run `uv run tutorials/fit_trace.py trace.csv --harmonic <k>`. This gives you f0, speed, slant
   distance, and delayed-CPA time **with uncertainties**, which are the ranges the funnel filters
   need.

### 4. Measure the offset

Do the same for event 2. The difference of the two `t0` values is the "920 s" of this dataset.

### 5. Asymmetry

Event 1 doesn't fit a straight-line model on both sides. Fit only the left half, then only the
right half. Which parameter disagrees? (The truth is in `make_dataset.py`. Read it after you've
answered.)

### 6. RF version

1. Record a few minutes of IQ around a strong carrier you know. A NOAA/Meteor pass, or an aircraft's
   1090 MHz squitters with an RTL-SDR, will do.
2. Open it in inspectrum, select the carrier, and *Add derived plot → Frequency*. That's the same
   Doppler curve.
3. Export it and fit with `fit_trace.py`, changing `C` to the speed of light and treating
   `f0` as the carrier offset.
