# Audacity

**What it is:** Audacity is a free, open-source audio editor. It runs natively on Linux (distro
packages, Flatpak, AppImage). Site: <https://www.audacityteam.org>. Manual:
<https://manual.audacityteam.org>.

![Audacity at 26:42](../frames/26_42.jpg)

## How he uses it

He uses Audacity only for the "can you protect yourself?" demo (26:00–27:00), and it's an
analysis lesson in its own right.

1. The stereo track is in **Spectrogram view** with a log-ish scale (70–990 Hz), with a Doppler curve
   at around 2:00–2:30.
2. He applies a **High-Pass Filter** and the curve disappears from view, then **exports as MP3**.
3. He re-imports the MP3, **boosts all frequencies**, and the curve is back.

The lesson is that a filter *attenuates* by its rolloff (6–48 dB per octave); it doesn't delete.
Whatever is left above the noise and quantization floor can be amplified back into view. Lossy
codecs and phone noise suppression didn't remove it either (27:30). If your job is *finding* weak
signals, "it looks gone" is not "it's gone."

## Functionality worth knowing (beyond his demo)

- **Per-track spectrogram settings.** Track dropdown → *Spectrogram Settings*. Window size and type,
  zero padding, scale (Linear / Logarithmic / Mel / Bark / ERB / Period), gain, range, frequency
  gain, and min/max frequency. These override the global *Preferences → Spectrograms*.
  Manual: [Spectrogram Settings](https://manual.audacityteam.org/man/spectrogram_settings.html).
- **Multi-view.** Waveform and spectrogram stacked for the same track (track dropdown → Multi-view).
- **Spectral selection.** In spectrogram view, drag a box in time *and* frequency. `Q` toggles
  between spectral and time-only selection. *Select → Spectral → Next Higher/Lower Peak Frequency*
  snaps to a spectral peak, which is handy for tracking a harmonic.
  Manual: [Spectral Selection](https://manual.audacityteam.org/man/spectral_selection.html).
- **Spectral edit effects** act on that box only: *Spectral Delete*, *Spectral edit parametric EQ*,
  and *Spectral edit shelves*.
- **Analyze → Plot Spectrum.** An averaged spectrum of the selection with a peak readout, exportable
  to text. This is the "Selection analysis" panel of [AudioLens](audiolens.md), done Audacity's way.
- **Label tracks** (`Ctrl+B` adds a label at the selection). *File → Export → Export Labels* writes
  start/end times. Labels made from a spectral selection also carry low and high frequency (an extra
  `\` line per label), so you can measure a curve point by point.
- **Nyquist Prompt** (Tools menu) for one-off DSP without leaving the app.
- **Macros** for batch processing a folder (normalize, filter, export).
- **Raw import.** *File → Import → Raw Data* opens headerless sample files. You can load an IQ
  capture as 2-channel 32-bit float to *look* at it. Each channel's spectrogram is real-valued
  (negative and positive frequencies fold together), so use [inspectrum](audiolens.md) for real IQ
  work.

## Existing tutorials

- [Spectrogram View](https://manual.audacityteam.org/man/spectrogram_view.html),
  [Spectrogram Settings](https://manual.audacityteam.org/man/spectrogram_settings.html), and
  [Spectral Selection](https://manual.audacityteam.org/man/spectral_selection.html) cover everything
  needed below.

## Tutorial: reproduce his high-pass claim, quantitatively

Generate data first: `uv run tutorials/make_dataset.py --out data`.

### 1. Setup

1. Open `data/recording.wav` and set the track to **Spectrogram**.
2. In Spectrogram Settings: window 4096, Hann, scale Linear, max 700 Hz, gain 20, range 80. Find
   event 2 at about 1100–1200 s and select 1050–1250 s.

### 2. Measure before you filter

With the selection set, use Analyze → Plot Spectrum (size 4096). Note the dB level of event 2's
strongest harmonic peak relative to the noise around it.

### 3. Filter

Effect → EQ and Filters → **High-Pass Filter**, 1000 Hz, rolloff **6 dB/octave**. Predict the
attenuation of a 400 Hz harmonic: log2(1000/400) ≈ 1.3 octaves × 6 dB ≈ 8 dB. Measure it with Plot
Spectrum. Does it match?

### 4. Export and re-import

Export as MP3 (128 kbps), then re-import. Is the curve visible? Raise the spectrogram **Gain** by
30–40 dB, or use Effect → Amplify. It comes back.

### 5. When does it really disappear?

1. Undo, and repeat with rolloff **48 dB/octave**: about 63 dB of attenuation at 400 Hz.
2. Export as 16-bit WAV, then as MP3.
3. Does the curve survive 16-bit quantization (~96 dB of dynamic range)? Does it survive MP3? Explain
   the difference in terms of quantization noise versus the codec's psychoacoustic masking.

### 6. Measure with labels

1. Switch on spectral selection. Draw small boxes on event 2's 2nd harmonic at about 10 times along
   the curve, pressing `Ctrl+B` after each.
2. Export the labels and convert them to `t_s,f_hz` (time = box center, frequency = box center).
3. Run `uv run tutorials/fit_trace.py labels.csv --harmonic 2`. Compare the fitted speed with what
   you'd get from the explorer page.
