# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Video Analyzer is a Python tool that analyzes video content using vision LLMs (Llama3.2 Vision, etc.) and Whisper audio transcription. It works in three stages:
1. **Frame Extraction & Audio Processing**: OpenCV extracts keyframes, FFmpeg + Whisper transcribes audio
2. **Frame Analysis**: Vision LLM analyzes each frame with context from previous frames
3. **Video Reconstruction**: Combines frame analyses and transcript into a coherent description

## Development Commands

```bash
# Install (development mode recommended)
pip install -e .

# Install UI (optional)
cd video-analyzer-ui && pip install .

# Run analysis (local Ollama)
video-analyzer video.mp4

# Run analysis (cloud API)
video-analyzer video.mp4 --client openai_api --api-key KEY --api-url https://openrouter.ai/api/v1 --model MODEL

# Start Web UI
video-analyzer-ui --dev

# Run tests
python test_prompt_loading.py

# Debug mode
video-analyzer video.mp4 --log-level DEBUG --keep-frames
```

**System Requirement**: FFmpeg must be installed (`apt install ffmpeg` / `brew install ffmpeg`)

## Architecture

### Core Processing Pipeline

```
Video Input → VideoProcessor (frame.py) → Keyframes
           → AudioProcessor (audio_processor.py) → Transcript
                    ↓
           VideoAnalyzer (analyzer.py) → LLMClient → Frame-by-frame analysis
                    ↓
           Video Reconstruction → JSON Output
```

### LLM Client Abstraction

`clients/llm_client.py` defines the base `LLMClient` class. Implementations:
- `OllamaClient` (clients/ollama.py) - Local Ollama server
- `GenericOpenAIAPIClient` (clients/generic_openai_api.py) - OpenAI-compatible APIs (OpenRouter, OpenAI)

To add a new LLM provider: inherit `LLMClient`, implement `generate()`, update `create_client()` in cli.py.

### Configuration Cascade

Priority (highest to lowest):
1. CLI arguments
2. User config (`config/config.json`)
3. Default config (`video_analyzer/config/default_config.json`)

### Prompt System

Prompts are in `video_analyzer/prompts/`. Key placeholders:
- `{PREVIOUS_FRAMES}` - Previous frame analyses for context
- `{TRANSCRIPT}` - Audio transcription
- `{prompt}` - User's custom question

## Coding Standards (from docs/AI.md)

- **File size limit**: Keep files under 400 lines of code
- **Modularity**: Split large components into smaller, focused modules
- **Dependencies**: Minimize external dependencies
- **Documentation**: Keep readme.md, docs/DESIGN.md, and docs/USAGES.md updated

## Key Algorithms

**Frame Extraction** (frame.py):
- Calculates target frames: `(duration/60) * frames_per_minute`
- Uses frame difference analysis (grayscale `cv2.absdiff`, threshold 10.0)
- Selects frames with highest visual differences

**Audio Processing** (audio_processor.py):
- FFmpeg extracts audio (16kHz, mono)
- faster-whisper with VAD filtering
- Word-level timestamps and confidence scoring

## Error Handling

- Audio extraction failures are graceful (analysis continues without transcript)
- LLM calls have retry mechanism (max 3 attempts)
- Rate limiting handled via Retry-After header

## MV Reviewer Module

A content review module for music videos with 7 configurable rules:

### Rules

| ID | Rule | Technology |
|----|------|------------|
| 1 | Blocked lyricist/composer (e.g., 林夕) | ShazamAPI + MusicBrainz |
| 2 | Vertical video / black borders | OpenCV |
| 3 | Volume spikes | pydub |
| 4-7 | Content review (exposure, inappropriate, landscape-only, ads, drugs) | Vision LLM |

### Commands

```bash
# Review single video
mv-reviewer video.mp4 --violation-dir ./violations

# Batch review directory
mv-reviewer ./mv_folder/ --violation-dir ./violations --report report.json

# Review specific rules only
mv-reviewer video.mp4 --rules 1 2 3

# Dry run (detect only, don't move files)
mv-reviewer video.mp4 --dry-run
```

### Architecture

```
mv_reviewer/
├── reviewer.py          # Main orchestrator
├── models/
│   └── review_result.py # Data models
├── rules/
│   ├── base_rule.py     # Abstract base class
│   ├── metadata_rule.py # Rule 1: Creator detection
│   ├── aspect_rule.py   # Rule 2: Aspect ratio
│   ├── volume_rule.py   # Rule 3: Volume analysis
│   └── content_rule.py  # Rules 4-7: LLM content review
└── services/
    ├── shazam_client.py      # Song identification
    └── musicbrainz_client.py # Metadata lookup
```

### Dependencies

- `shazamio` - Audio fingerprint identification
- `musicbrainzngs` - MusicBrainz API client
