#!/usr/bin/env python3
"""
Локальная транскрибация звонков (whisper.cpp via pywhispercpp), переиспользует
ggml-модель Handy. mp3 декодируется системным afconvert (без ffmpeg).

Запуск:
  .tools/venv/bin/python .tools/projects/detailing-samara/transcription/transcribe-calls.py \
    "<input_dir>" "<output_dir>" ["<ggml_model.bin>"]
"""
import sys, os, time, wave, audioop, subprocess, tempfile
from pathlib import Path
import numpy as np

DEFAULT_MODEL = os.path.expanduser(
    "~/Library/Application Support/com.pais.handy/models/ggml-large-v3-q5_0.bin")

def fmt(t):
    m, s = divmod(int(t), 60); h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"

def load_audio(mp3):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); tmp.close()
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", str(mp3), tmp.name],
                   check=True, capture_output=True)
    w = wave.open(tmp.name, "rb")
    ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(n); w.close(); os.unlink(tmp.name)
    if sw != 2: raw = audioop.lin2lin(raw, sw, 2)
    if ch == 2: raw = audioop.tomono(raw, 2, 0.5, 0.5)
    if sr != 16000: raw, _ = audioop.ratecv(raw, 2, 1, sr, 16000, None)
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return arr, len(arr) / 16000.0

def main():
    in_dir = Path(sys.argv[1]).expanduser()
    out_dir = Path(sys.argv[2]).expanduser()
    model_path = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MODEL

    from pywhispercpp.model import Model
    print(f"Модель: {os.path.basename(model_path)}", flush=True)
    nth = int(os.environ.get("N_THREADS", "6"))
    model = Model(model_path, n_threads=nth, print_realtime=False,
                  print_progress=False, print_timestamps=False)

    mp3s = sorted(in_dir.rglob("*.mp3"))
    # шардирование для параллельных воркеров через env SHARD_IDX/SHARD_CNT
    scnt = int(os.environ.get("SHARD_CNT", "1")); sidx = int(os.environ.get("SHARD_IDX", "0"))
    if scnt > 1:
        mp3s = [m for i, m in enumerate(mp3s) if i % scnt == sidx]
        print(f"Шард {sidx+1}/{scnt}", flush=True)
    if os.environ.get("REVERSE") == "1":
        mp3s = list(reversed(mp3s))
        print("порядок: с конца (помощник)", flush=True)
    print(f"Найдено mp3 (в шарде): {len(mp3s)}", flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for i, mp3 in enumerate(mp3s, 1):
        rel = mp3.relative_to(in_dir)
        out_path = out_dir / rel.with_suffix(".txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists() and out_path.stat().st_size > 0:
            print(f"[{i}/{len(mp3s)}] пропуск (готов): {rel}", flush=True)
            index.append((str(rel), "—", "готов ранее")); continue
        t0 = time.time()
        print(f"[{i}/{len(mp3s)}] {rel} …", flush=True)
        try:
            arr, dur = load_audio(mp3)
            segs = model.transcribe(arr, language="ru")
            lines = [f"[{fmt(s.t0/100)}–{fmt(s.t1/100)}] {s.text.strip()}" for s in segs]
            header = f"# {rel}\n# длительность: {fmt(dur)} · whisper.cpp large-v3 · ru\n\n"
            out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
            print(f"    ✓ {fmt(dur)} → {time.time()-t0:.0f}c, строк: {len(lines)}", flush=True)
            index.append((str(rel), fmt(dur), f"{len(lines)} строк"))
        except Exception as e:
            print(f"    ✗ ОШИБКА: {e}", flush=True)
            index.append((str(rel), "—", f"ОШИБКА: {e}"))

    if scnt <= 1:
        idx = ["# Транскрипты звонков — индекс\n", f"Источник: {in_dir.name}\n",
               "| Файл | Длит. | Статус |", "|---|---|---|"]
        idx += [f"| {r} | {d} | {s} |" for r, d, s in index]
        (out_dir / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"Готово (шард {sidx+1}/{scnt}).", flush=True)

if __name__ == "__main__":
    main()
