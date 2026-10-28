"""Ежедневный прогон дашборда SEO-заводов: свежий техаудит каждого выложенного сайта → сборка дашборда.

Запускает планировщик Windows: задача «SEO-дашборд», 08:00, через pythonw (без окна);
пропущенный запуск догоняет после включения компьютера. Создать или пересоздать задачу —
«Включить ежедневный прогон.ps1», убрать — `Unregister-ScheduledTask "SEO-дашборд"`.
Вручную — «Ежедневный прогон.bat» или

    .tools/venv/Scripts/python.exe .tools/universal/seo-dashboard/daily.py

Аудит — m2 завода без PageSpeed и без Telegram: бесплатно, около минуты на сайт. Сайты с
live: false пропускаются. Ошибка одного завода не останавливает остальные и сборку.
Раз в 7 дней (по дате последнего снимка — пропущенный догоняется) ещё и съём позиций:
m3 завода, живая выдача Яндекса через XMLRiver, ≈0,075 ₽ за ключ (87 ключей ≈ 6,5 ₽).
Только где в site.config.yml завода features.rankings: true.
Лог — out/daily.log (последние 200 строк), out/ вне git.
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RANKINGS_EVERY = 7   # дней между платными съёмами позиций
LOG = HERE / "out" / "daily.log"
VENV_PY = HERE.parents[1] / "venv" / "Scripts" / "python.exe"


def log(line: str) -> None:
    LOG.parent.mkdir(exist_ok=True)
    old = LOG.read_text(encoding="utf-8").splitlines() if LOG.exists() else []
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    LOG.write_text("\n".join((old + [f"{stamp}  {line}"])[-200:]) + "\n", encoding="utf-8")
    print(line)


def run(cmd: list[str], cwd: Path, timeout: int) -> tuple[bool, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))   # планировщик: без окон
    except subprocess.TimeoutExpired:
        return False, f"не уложился в {timeout // 60} мин"
    tail = (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]
    return p.returncode == 0, tail[0][:200]


def rankings_on(factory: Path) -> bool:
    cfg = yaml.safe_load((factory / "site.config.yml").read_text(encoding="utf-8")) or {}
    return bool((cfg.get("features") or {}).get("rankings"))


def main() -> int:
    sites = (yaml.safe_load((HERE / "sites.yml").read_text(encoding="utf-8")) or {}).get("sites", [])
    failed = 0
    for s in sites:
        if not s.get("live"):
            continue
        factory = Path(s["factory"])
        py = factory / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            log(f"✗ {s['id']}: нет окружения завода {py}")
            failed += 1
            continue
        ok, tail = run([str(py), "orchestrator.py", "m2", "--skip-psi", "--dry-run"],
                       factory / "engine" / "seo-agent", timeout=900)
        log(f"{'✓' if ok else '✗'} {s['id']}: техаудит{'' if ok else ' — ' + tail}")
        failed += not ok
        snaps = sorted((factory / "engine" / "seo-agent" / "data" / "rankings").glob("????-??-??.csv"))
        last = dt.date.fromisoformat(snaps[-1].stem) if snaps else None
        if rankings_on(factory) and (not last or (dt.date.today() - last).days >= RANKINGS_EVERY):
            ok, tail = run([str(py), "orchestrator.py", "m3", "--refresh-seeds", "--dry-run"],
                           factory / "engine" / "seo-agent", timeout=1800)
            log(f"{'✓' if ok else '✗'} {s['id']}: позиции{'' if ok else ' — ' + tail}")
            failed += not ok
    ok, tail = run([str(VENV_PY), "build.py"], HERE, timeout=300)
    log(f"{'✓' if ok else '✗'} дашборд собран{'' if ok else ' — ' + tail}")
    return 1 if failed or not ok else 0


if __name__ == "__main__":
    sys.exit(main())
