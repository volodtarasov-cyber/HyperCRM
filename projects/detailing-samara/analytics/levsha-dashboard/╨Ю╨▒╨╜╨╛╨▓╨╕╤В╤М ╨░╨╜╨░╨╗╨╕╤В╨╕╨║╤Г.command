#!/bin/zsh

set -u

PROJECT_DIR="${0:A:h}"
WORKSPACE_DIR="${PROJECT_DIR:h:h:h:h}"

python3 "$WORKSPACE_DIR/.tools/projects/detailing-samara/analytics/levsha-dashboard-update.py" --project "$PROJECT_DIR"
STATUS=$?

if [[ $STATUS -eq 0 ]]; then
  open "$PROJECT_DIR/dashboard/index.html"
  echo ""
  echo "Готово. Дашборд обновлён и открыт в браузере."
else
  echo ""
  echo "Обновление остановлено. Подробности выше и в папке logs."
fi

echo ""
read -k 1 "?Нажмите любую клавишу, чтобы закрыть окно."
exit $STATUS
