---
name: songsee
description: "Use when generating spectrograms and audio feature visualizations (mel, chroma, MFCC, tempogram, etc.) from audio files via CLI. Useful for audio analysis, music production debugging, and visual documentation. NOT for: audio transcription, music generation, speech recognition, or when DAW software is more appropriate."
category: general
---

## Overview

`songsee` generates spectrograms and audio feature visualizations from audio files via CLI. It supports multiple audio formats and visualization types useful for music analysis, audio debugging, and technical documentation.

## Core Features

- **Mel spectrograms** — Most common audio visualization, shows frequency content over time
- **Chroma features** — Pitch class profiles, great for harmonic analysis
- **MFCC (Mel-Frequency Cepstral Coefficients)** — Texture, timbre, genre classification
- **Tempogram** — Rhythm, tempo patterns
- **Waveforms** — Basic amplitude over time
- **Spectral contrast** — Peak/valley differences across frequency bands
- **Tonnetz** — Harmonic relationships

## Usage

bash
# Basic mel spectrogram
songsee input.wav --output mel.png

# Multiple visualization types
songsee track.mp3 --viz mel chroma mfcc tempogram

# Custom parameters
songsee audio.flac --n_fft 2048 --hop_length 512 --n_mels 128

## Purpose

Generate publication-ready audio visualizations (spectrograms, chroma features, MFCCs, tempograms) from any audio file via a single CLI command. SongSee turns sound into sight — making frequency content, harmonic structure, rhythmic patterns, and timbral texture visible for music analysis, audio debugging, technical documentation, and creative visual art.

## Why This Works

**Concept 1: Multi-domain feature extraction.** Unlike generic waveform viewers, SongSee covers six distinct visualization domains (mel, chroma, MFCC, tempogram, spectral contrast, tonnetz) — each revealing a different layer of the audio: pitch, harmony, timbre, rhythm, dynamics, and harmonic relationships. This gives a complete picture in one command.

**Concept 2: Publication-ready output.** The generated images are high-resolution PNGs with sensible default colormaps, axis labels, and sizing — suitable for slides, papers, documentation, or social media without post-processing. The `--custom` parameters allow fine-tuning (FFT size, hop length, mel bands) without requiring code changes.

**Concept 3: Library-grade audio backend.** Under the hood, SongSee uses librosa (industry standard for audio analysis) and matplotlib — the same tools used in music information retrieval research. This means scientifically accurate feature computation, not naive approximations.

## Examples

**Good: Full audio analysis dashboard**
```bash
songsee track.wav --viz mel chroma mfcc tempogram spectral_contrast --output dashboard.png
# → Generates a 2×3 grid showing all six feature types in one image
```

**Bad: Throwing all features at everything**
```bash
# WRONG: Every file gets every feature type regardless of content
songsee silence_15s.wav --viz mel chroma mfcc tempogram spectral_contrast tonnetz --output busy.png
```
**Bad:** Silent audio produces flat spectrograms across all domains — the output is all 6 subplots showing nothing useful. Pick 1-3 features matching the analytic question: rhythm → tempogram, harmony → chroma, timbre → MFCC.

---

**Good: High-resolution mel for a presentation slide**
```bash
songsee podcast_episode.mp3 --viz mel --n_mels 256 --n_fft 4096 --hop_length 1024 --output keynote_mel.png
# → Higher frequency resolution for detailed spectral analysis
```

**Bad: Overly large FFT on short audio**
```bash
# WRONG: n_fft bigger than the clip duration
songsee 0.5s_clip.wav --viz mel --n_fft 8192 --output tall_skinny.png
```
**Bad:** `n_fft=8192` on a 0.5s clip produces ~10 time frames with 4097 frequency bins. The result is a tall, skinny image with no temporal detail. Match FFT size to clip: short clips → smaller FFT (e.g., 1024 or 2048).

---

**Good: Harmonic analysis of a chord progression**
```bash
songsee jazz_chords.flac --viz chroma tonnetz --output harmony.png
# → Chroma reveals pitch-class content; Tonnetz shows harmonic movement in tonal space
```

**Bad: MFCC on a solo instrument recording**
```bash
# WRONG: Using MFCC on a solo flute or sine wave
songsee flute_scale.wav --viz mfcc --output timbre.png
```
**Bad:** MFCCs model spectral envelope — they're designed for speech and polyphonic music with rich timbral texture. A solo flute or sine wave produces flat, meaningless MFCC patterns. Use mel spectrogram instead to see the harmonic content.

---

**Good: Tempo and rhythm visualization**
```bash
songsee drum_loop.wav --viz tempogram --output rhythm.png
# → Tempogram displays local tempo over time, revealing tempo changes and rhythmic patterns
```

---

**Good: Batch analysis for a music library**
```bash
for f in *.wav; do
  songsee "$f" --viz mel chroma --output "${f%.wav}_analysis.png"
done
```

## Anti-Patterns

**Anti-Pattern 1: Overly large FFT on short audio.** Using `--n_fft 8192` on a 0.5-second clip produces a frequency axis with more bins than time frames. The spectrogram becomes tall and skinny with no temporal detail. Match FFT size to clip duration: short clips → smaller FFT.

**Anti-Pattern 2: Ignoring sample rate mismatch.** Feeding a 44.1kHz file into analysis expecting 22kHz defaults produces aliased-looking spectrograms. Either resample first or pass `--sr 22050` to override the target sample rate.

**Anti-Pattern 3: MFCC on single-instrument recordings.** MFCCs model spectral envelope — they're designed for speech and polyphonic music. A solo flute or sine wave produces meaningless MFCC patterns because there's no timbral texture to capture.

**Anti-Pattern 4: All features every time.** Generating all visualization types for every file creates information overload. Pick the 1-3 features that match the *analytic question*: rhythm → tempogram, harmony → chroma, timbre → MFCC, frequency content → mel.

## When NOT to Use

- **Audio transcription (speech-to-text)** — spectrograms show frequency content, not words. Use a speech recognition tool (Whisper, DeepSpeech) instead.
- **Music generation or synthesis** — SongSee analyzes existing audio; it doesn't create or modify it. For music generation, use a dedicated audio generation tool.
- **Real-time visualization** — SongSee is a CLI batch processor. For real-time spectrum analyzers, use TouchDesigner, Max/MSP, or a DAW plugin.
- **Lossless audio editing** — SongSee doesn't modify audio files. For cutting, filtering, or effects, use SoX, Audacity, or ffmpeg.
- **Speech recognition/pronunciation analysis** — while formants appear in spectrograms, dedicated tools (Praat, Wavesurfer) provide proper phonetic analysis with formant tracking and annotation.
- **File format conversion** — SongSee reads audio but doesn't convert formats. For transcoding, use ffmpeg or SoX.
- **Large batch processing with all features** — generating all 6 feature types across hundreds of files is computationally expensive. Target specific features per batch.
- **Low-quality or heavily compressed audio** — lossy formats (low-bitrate MP3, streaming rips) produce noisy spectrograms that obscure the features you want to analyze.

## Cross-References

- **touchdesigner-mcp** (optional-skills/touchdesigner-mcp/SKILL.md) — Real-time audio-reactive visual pipelines; pair SongSee spectrograms with TD for live generative visuals
- **baoyu-infographic** (creative/baoyu-infographic/SKILL.md) — Data-to-visual pipeline; embed SongSee spectrograms into infographic layouts
- **meme-generation** (meme-generation/SKILL.md) — Creative image output; overlay text captions on SongSee spectrograms for educational memes
- [librosa Documentation](https://librosa.org/doc/latest/) — the Python library powering all feature extraction
- [Understanding the Mel Scale](https://en.wikipedia.org/wiki/Mel_scale) — perceptual frequency scaling explained
- [MFCC Tutorial](https://practicalcryptography.com/miscellaneous/machine-learning/guide-mel-frequency-cepstral-coefficients-mfccs/) — how MFCCs capture timbral texture
- `sox` / `ffmpeg` — pre-processing tools for resampling, trimming, or converting audio before analysis