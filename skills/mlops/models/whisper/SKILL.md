---
name: whisper
description: "OpenAI Whisper for speech-to-text transcription, translation, and language identification. Use when: user wants to transcribe audio to text, translate speech to English, identify spoken languages, generate subtitles (SRT/VTT), extract word-level timestamps, or process multilingual podcasts/audio. Supports 99 languages with six model sizes (39M–1550M params). NOT for: text-to-speech, real-time streaming transcription, music lyrics extraction, or when native Whisper API/proprietary STT services are preferred."
category: general
---

## Core Capabilities

- **Transcription**: Audio → text in the same language (`task: transcribe`)
- **Translation**: Audio → English text (`task: translate`)
- **Language ID**: Detect dominant language without full transcription
- **Subtitle generation**: SRT, VTT, TXT, JSON output formats
- **Word-level timestamps**: Optional extraction for precise alignment

## When to Use Whisper

**Use when:**
- Speech-to-text transcription (99 languages)
- Podcast/video transcription
- Meeting notes automation
- Translation to English (from any language)
- Noisy audio transcription
- Multilingual audio processing
- Subtitle generation (SRT/VTT)
- Word-level timestamp extraction

**Use alternatives instead:**
- **AssemblyAI**: Managed API, speaker diarization
- **Deepgram**: Real-time streaming ASR
- **Google Speech-to-Text**: Cloud-based

## Installation

bash
# Requires Python 3.8-3.11
pip install -U openai-whisper

# Requires ffmpeg
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
# Windows: choco install ffmpeg


## Supported Formats

MP3, WAV, FLAC, OGG, M4A, WebM. Long audio files automatically chunked.

## Model Selection

| Model  | Parameters | VRAM   | Speed (GPU) | Best for                        |
|--------|------------|--------|-------------|---------------------------------|
| tiny   | 39M        | ~1 GB  | ~32x        | Testing, quick drafts           |
| base   | 74M        | ~1 GB  | ~16x        | General use, prototyping        |
| small  | 244M       | ~2 GB  | ~6x         | Higher accuracy                 |
| medium | 769M       | ~5 GB  | ~2x         | Difficult accents, noise        |
| large  | 1550M      | ~10 GB | 1x          | Best accuracy, non-English      |
| turbo  | 809M       | ~6 GB  | ~8x         | Fast + accurate (v3 model)      |

**Recommendation**: `turbo` for best speed/quality, `medium` for general use, `large` for non-English or difficult audio.

## Python API

python
import whisper

model = whisper.load_model("base")

# Transcription (auto-detect language)
result = model.transcribe("audio.mp3")
print(result["text"])

# Specify language (faster)
result = model.transcribe("audio.mp3", language="en")

# Translation to English
result = model.transcribe("spanish.mp3", task="translate")

# Improve accuracy with context
result = model.transcribe(
    "audio.mp3",
    initial_prompt="This is a technical podcast about machine learning."
)

# Word-level timestamps
result = model.transcribe("audio.mp3", word_timestamps=True)

# Temperature fallback
result = model.transcribe("audio.mp3", temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))

# Access segments
for segment in result["segments"]:
    print(f"[{segment['start']:.2f}s - {segment['end']:.2f}s] {segment['text']}")


### Language Detection

python
# Detect language only (faster, no full transcription)
result = model.transcribe("unknown_lang.mp3", language=None)
print(f"Detected: {result['language']}")  # e.g., "ja", "es", "fr"

# Then transcribe with detected language for best results
result = model.transcribe("unknown_lang.mp3", language=result["language"])


## Command Line Usage

bash
# Basic transcription
whisper audio.mp3 --model large

# Specify language and model
whisper audio.mp3 --model medium --language en

# Translation to English
whisper audio.mp3 --task translate

# Output formats
whisper audio.mp3 --output_format srt   # Subtitles
whisper audio.mp3 --output_format vtt   # WebVTT
whisper audio.mp3 --output_format txt    # Plain text
whisper audio.mp3 --output_format json   # JSON with timestamps

# Word-level timestamps
whisper audio.mp3 --word_timestamps True

# Beam search + temperature sampling
whisper audio.mp3 --model large --beam_size 5 --best_of 5


### CLI Options

| Flag               | Description                                      |
|--------------------|--------------------------------------------------|
| `--model`          | Model size: tiny/base/small/medium/large/turbo   |
| `--language`       | Language code (e.g., en, fr, de, zh) or auto    |
| `--task`           | `transcribe` (default) or `translate`            |
| `--output_format`  | Output format: srt/vtt/txt/json                  |
| `--word_timestamps`| Include word-level timestamps                    |
| `--fp16`           | Use FP16 acceleration (default on GPU)           |

## GPU Acceleration

python
# Automatically uses GPU if available
model = whisper.load_model("turbo")

# Force CPU
model = whisper.load_model("turbo", device="cpu")

# Force GPU
model = whisper.load_model("turbo", device="cuda")


10-20× faster on GPU. Real-time factors: tiny ~0.32 CPU / ~0.01 GPU; large ~1.0 CPU / ~0.05 GPU.

## Output Formats

| Format | Use case                          | Contains                |
|--------|-----------------------------------|-------------------------|
| `txt`  | Plain transcript, no timestamps   | Text only               |
| `vtt`  | Web captions, video players        | Timestamps + text       |
| `srt`  | Video subtitles, editors           | Sequential timestamps   |
| `json` | Processing, analysis               | Full metadata           |

## Batch Processing

python
import os

audio_files = ["file1.mp3", "file2.mp3", "file3.mp3"]

for audio_file in audio_files:
    print(f"Transcribing {audio_file}...")
    result = model.transcribe(audio_file)
    
    output_file = audio_file.replace(".mp3", ".txt")
    with open(output_file, "w") as f:
        f.write(result["text"])


## Real-Time Transcription

For streaming audio, use faster-whisper (4× faster):

bash
pip install faster-whisper


python
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cuda", compute_type="float16")
segments, info = model.transcribe("audio.mp3", beam_size=5)

for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")


## Integration

### Extract audio from video

bash
ffmpeg -i video.mp4 -vn -acodec pcm_s16le audio.wav
whisper audio.wav


### With LangChain

python
from langchain.document_loaders import WhisperTranscriptionLoader

loader = WhisperTranscriptionLoader(file_path="audio.mp3")
docs = loader.load()


## Troubleshooting

| Issue                        | Solution                                              |
|------------------------------|-------------------------------------------------------|
| Slow transcription           | Use smaller model or enable GPU/FP16                  |
| Poor accuracy                | Use `medium` or `large` model; ensure clear audio     |
| Wrong language               | Specify `--language` explicitly or use `auto`         |
| CUDA out of memory           | Use smaller model or batch with `chunk_length`        |
| CPU very slow                | Use `int8` quantization or `turbo` model              |
| MPS (Apple Silicon) fp16     | Use `dtype=torch.float32` on MPS devices              |
| No timestamps in output      | Use `word_timestamps=True` and `--word_timestamps true`|
| Audio has music              | Music transcribed as humming/singing, not filtered    |
| CUDA not available           | Falls back to CPU (significantly slower)              |

## Best Practices

1. **Use turbo/medium model** - Best speed/quality balance
2. **Specify language** - Faster than auto-detect
3. **Add initial prompt** - Improves technical terms, proper nouns
4. **Use GPU** - 10-20× faster
5. **Batch process** - More efficient for multiple files
6. **Split long audio** - <30 min chunks for best accuracy
7. **Check language support** - Quality varies by language
8. **Use faster-whisper** - 4× faster for real-time needs
9. **Monitor VRAM** - Scale model size to hardware
10. **Convert to WAV** - Better compatibility

## Limitations

1. **Hallucinations** - May repeat or invent text on low-quality audio
2. **Long-form accuracy** - Degrades on >30 min audio
3. **Speaker identification** - No diarization (use AssemblyAI)
4. **Accents** - Quality varies by accent
5. **Background noise** - Can affect accuracy
6. **Real-time latency** - Not suitable for live captioning (use Deepgram)
7. **Translation** - Only translates TO English, not from English

## Resources

- **GitHub**: https://github.com/openai/whisper ⭐ 72,900+
- **Paper**: https://arxiv.org/abs/2212.04356
- **Model cache**: `~/.cache/whisper/`
- **Available on**: Linux, macOS (MPS), Windows (CUDA)

## Purpose

Transcribe speech audio to text across 99 languages, translate non-English speech to English, and identify spoken languages — all with a single PyTorch model requiring no task-specific fine-tuning, supporting six model sizes from 39M (tiny) to 1.55B (large-v3) parameters.

## Why This Works

**Concept 1: Multi-Task Training on 680k Hours.** Whisper is trained on 680k hours of weakly supervised audio from the web, covering 99 languages, multiple acoustic conditions, and both transcription and translation objectives. This single training run produces a model that generalizes to accents, background noise, and domain-specific terminology without per-language or per-domain fine-tuning.

**Concept 2: Logit-Level Decode with Temperature Fallback.** The model outputs token logits over the multilingual GPT-2 tokenizer. When the primary decode (temperature=0, greedy) produces low-confidence tokens, Whisper automatically falls back through higher temperatures (0.2 → 0.4 → 0.6 → 0.8 → 1.0) with beam search, trading determinism for accuracy on difficult segments — a critical feature for noisy real-world audio.

**Concept 3: Hierarchical Model Scaling for Budget Matching.** The six model sizes (tiny → turbo) follow a consistent architecture (encoder-decoder transformer with 2× encoder layers vs decoder), allowing the user to match VRAM budget to accuracy requirement. Turbo (809M) uses the encoder of large-v3 and a smaller decoder, achieving near-large accuracy at ~8× real-time on GPU.

## Examples

**Good: Transcribe a multi-speaker podcast with language auto-detection.**  
Context: 45-minute podcast with English, Spanish code-switching and technical ML jargon.  
```python
import whisper
model = whisper.load_model("turbo")                    # best accuracy/speed
result = model.transcribe(
    "podcast_episode_42.mp3",
    initial_prompt="Podcast about machine learning, transformer architectures, LoRA fine-tuning.",
    word_timestamps=True,
    temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)        # fallback for tough sections
)
for seg in result["segments"]:
    print(f"[{seg['start']:.1f}s-{seg['end']:.1f}s] {seg['text']}")
```

**Good: Generate SRT subtitles for a multilingual training video.**  
Context: Technical tutorial with presenter speaking Hindi, slides in English.  
```bash
whisper tutorial.mp4 --model large --language hi --output_format srt --word_timestamps True
# Output: tutorial.srt with Hindi transcription, timestamps, and line breaks
```

**Good: Translate non-English customer support calls to English for analytics.**  
Context: Global SaaS company needs English transcripts of Japanese support calls for analysis.  
```python
model = whisper.load_model("large")
result = model.transcribe("japanese_call.wav", task="translate")  # outputs English
with open("transcript_en.txt", "w") as f:
    f.write(result["text"])
```

**Good: Real-time-like batch processing with faster-whisper.**  
Context: Processing a 5-hour meeting recording on CPU with <4 GB RAM.  
```python
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")   # quantized CPU
segments, info = model.transcribe("all_hands_meeting.wav", beam_size=5)
print(f"Detected language: {info.language} (p={info.language_probability:.2f})")
for seg in segments:
    print(f"[{seg.start:.2f}s -> {seg.end:.2f}s] {seg.text}")
```

## Anti-Patterns

**Anti-Pattern 1: Omitting `initial_prompt` for domain-specific audio.**  
Transcribing medical or technical audio without context leads to incorrect domain terms ("myocardial infarction" → "my car dial in faction"). Always provide a brief initial prompt describing the topic.

**Anti-Pattern 2: Using `large` model for every task on limited hardware.**  
Running large-v3 on a 6GB GPU causes OOM or swap thrashing. Match model size to hardware: `base` for clean English, `turbo` for general, `medium` for noisy audio, `large` only for 99-language or very challenging audio.

**Anti-Pattern 3: Not specifying `language` when it's known.**  
When the spoken language is known, passing `language="ja"` skips the language-detection forward pass (saving 3–5s) and avoids language confusion on short clips. Only omit for truly mixed-language content.

**Anti-Pattern 4: Using Whisper for real-time / live captioning.**  
Whisper processes fixed-length windows (30s chunks) with no streaming output until the chunk finishes. For real-time, use faster-whisper with VAD (voice activity detection) streaming, Deepgram, or AssemblyAI.

## When NOT to Use

1. **Real-time streaming transcription (<2s latency)** — Whisper processes full 30s audio chunks. For live captioning, use faster-whisper with `vad_filter=True` + stream mode, or managed APIs (Deepgram, AssemblyAI).
2. **Text-to-speech / speech synthesis** — Whisper is strictly encoder-decoder for ASR. Use Bark, Coqui TTS, or ElevenLabs for generation.
3. **Speaker diarization (who said what)** — Whisper outputs only text and timestamps, no speaker labels. Use PyAnnote Audio or AssemblyAI for speaker segmentation.
4. **Music lyrics transcription** — Whisper treats music as speech and typically outputs garbled or hallucinated text. Use dedicated lyrics transcription (e.g., Demucs + Chorus) for music.
5. **Very short audio clips (<1 second)** — The model processes 30-second windows internally; short clips get padded with silence, which degrades accuracy. For short commands, use a specialized KWS model (e.g., Porcupine, SpeechBrain).
6. **Deploying in privacy-sensitive environments requiring on-device ASR** — While Whisper runs locally, the large model requires 10GB VRAM, which may exceed edge device budgets. Use tiny/base models or Distil-Whisper for edge deployment.

## Cross-References

- [audiocraft](/skills/audiocraft) — Music and audio generation (complementary: transcribe audio, then generate matching soundscape)
- [faster-whisper](/skills/faster-whisper) — CTranslate2-optimized Whisper (4× faster, lower memory)
- [huggingface-transformers](/skills/huggingface-transformers) — 🤗 Transformers Whisper API with pipeline support
- [torchaudio](/skills/torchaudio) — Audio loading, resampling, and VAD preprocessing
- [pyannote-audio](/skills/pyannote-audio) — Speaker diarization to pair with Whisper transcripts
