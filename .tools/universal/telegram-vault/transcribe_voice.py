#!/usr/bin/env python3
"""Decode Telegram OGG/Opus with PyAV and transcribe it with local Whisper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import av
import numpy as np
from pywhispercpp.model import Model


WHISPER_SAMPLE_RATE = 16000


def decode_audio(path: Path) -> np.ndarray:
    chunks: list[np.ndarray] = []
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise RuntimeError("В файле нет аудиодорожки")
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="flt", layout="mono", rate=WHISPER_SAMPLE_RATE)
        for frame in container.decode(stream):
            converted = resampler.resample(frame)
            for output in converted if isinstance(converted, list) else [converted]:
                if output is not None:
                    chunks.append(output.to_ndarray().reshape(-1).astype(np.float32, copy=False))
        flushed = resampler.resample(None)
        for output in flushed if isinstance(flushed, list) else [flushed]:
            if output is not None:
                chunks.append(output.to_ndarray().reshape(-1).astype(np.float32, copy=False))
    if not chunks:
        raise RuntimeError("Аудио пустое или не декодировалось")
    return np.concatenate(chunks)


def transcribe(audio_path: Path, model_path: Path, language: str) -> str:
    audio = decode_audio(audio_path)
    model = Model(str(model_path), print_progress=False)
    segments = model.transcribe(
        audio,
        language=language,
        print_progress=False,
        print_timestamps=False,
    )
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--language", default="ru")
    args = parser.parse_args()
    try:
        text = transcribe(args.audio, args.model, args.language)
        if not text:
            raise RuntimeError("Whisper не распознал речь")
        print(text)
        return 0
    except Exception as error:
        print(f"Ошибка расшифровки: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
