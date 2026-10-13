"""Локальная расшифровка видео и аудио на Windows: faster-whisper + CUDA.

Записи в облако не уходят. Окружение — отдельное `.tools/venv-whisper` на Python 3.13:
у основного venv Python 3.14, под него колёс ctranslate2 может не быть.

    .tools/venv-whisper/Scripts/python.exe .tools/universal/media/transcribe-video.py <папка|файл> [--out DIR] [--model large-v3]

Ищет *.mp4 *.mkv *.webm *.mp3 *.m4a *.wav рекурсивно, кладёт рядом в --out одноимённый .md
с таймкодами абзацами по ~45 секунд. Уже расшифрованные файлы пропускает — прогон можно прерывать.
Модели кэшируются в HF_HOME; по правилу «всё на D:» по умолчанию это D:\\.cache\\huggingface.
"""
import argparse
import os
import site
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HOME", r"D:\.cache\huggingface")

# DLL cuBLAS и cuDNN ставятся pip-пакетами nvidia-*; ctranslate2 сам их не находит.
for sp in site.getsitepackages():
    for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin"):
        p = Path(sp) / sub
        if p.is_dir():
            os.add_dll_directory(str(p))
            os.environ["PATH"] = str(p) + os.pathsep + os.environ["PATH"]

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

EXT = {".mp4", ".mkv", ".webm", ".mov", ".mp3", ".m4a", ".wav"}
PARA_SEC = 45


def ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def load_audio(src: Path):
    """16 кГц моно через системный ffmpeg: встроенный декодер faster-whisper (PyAV) ломается на несовпадении версий."""
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def transcribe(model, src: Path, dst: Path) -> None:
    t0 = time.time()
    segments, info = model.transcribe(
        load_audio(src), language="ru", beam_size=5, vad_filter=True,
        condition_on_previous_text=False,  # гасит зацикливание на длинных записях
    )
    paras, cur, start = [], [], None
    for seg in segments:
        if start is None:
            start = seg.start
        cur.append(seg.text.strip())
        if seg.end - start >= PARA_SEC:
            paras.append((start, " ".join(cur)))
            cur, start = [], None
    if cur:
        paras.append((start, " ".join(cur)))
    dst.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(f"**{ts(s)}** — {t}" for s, t in paras)
    dst.write_text(
        f"# {src.stem}\n\n*источник: `{src.name}` · длительность {ts(info.duration)} · "
        f"faster-whisper, локально*\n\n{body}\n",
        encoding="utf-8",
    )
    took = time.time() - t0
    print(f"  {ts(info.duration)} за {ts(took)} (x{info.duration / max(took, 1):.1f})", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", help="папка результатов; по умолчанию <src>/_transcripts")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--compute", default="int8", help="int8 для Pascal (GTX 10xx), float16 для RTX")
    ap.add_argument("--limit", type=int, default=0, help="расшифровать не больше N файлов")
    a = ap.parse_args()

    src = Path(a.src)
    root = src if src.is_dir() else src.parent
    out = Path(a.out) if a.out else root / "_transcripts"
    files = sorted(p for p in ([src] if src.is_file() else src.rglob("*")) if p.suffix.lower() in EXT and out not in p.parents)
    todo = [(f, out / f.relative_to(root).with_suffix(".md")) for f in files]
    todo = [(f, d) for f, d in todo if not d.exists()]
    if a.limit:
        todo = todo[: a.limit]
    print(f"к расшифровке: {len(todo)} из {len(files)}", flush=True)
    if not todo:
        return
    model = WhisperModel(a.model, device="cuda", compute_type=a.compute)
    for f, d in todo:
        print(f"> {f.relative_to(root)}", flush=True)
        transcribe(model, f, d)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
