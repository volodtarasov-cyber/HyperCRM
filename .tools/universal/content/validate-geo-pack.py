"""Локальная проверка комплекта карт. Не публикует и не подтверждает факты вместо человека."""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from PIL import Image


def validate(manifest_path, as_of):
    base = manifest_path.resolve().parent
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    errors, warnings, blockers = [], [], []
    client = manifest.get('client_id')
    if client in [None, '', '?', 'TODO'] or manifest.get('schema_version') != 1:
        errors.append('Нет client_id или поддерживаемой версии schema_version=1')

    def local_file(name):
        if not isinstance(name, str) or not name:
            errors.append('Пустой путь артефакта')
            return None
        path = (base / name).resolve()
        if not path.is_relative_to(base):
            errors.append('Артефакт выходит за пределы папки пакета: ' + name)
            return None
        if not path.is_file():
            errors.append('Не найден файл: ' + name)
            return None
        return path

    texts_path = local_file(manifest.get('texts_file'))
    posts = json.loads(texts_path.read_text(encoding='utf-8')) if texts_path else []
    if len(posts) != manifest.get('expected_posts'):
        errors.append('Количество публикаций не соответствует контракту')
    facts = manifest.get('facts', {})
    seen = set()
    hashes = {}
    for post in posts:
        pid = post.get('id')
        if not pid or pid in seen:
            errors.append('Пустой или повторный ID публикации')
        seen.add(pid)
        if post.get('client') != client:
            errors.append(str(pid) + ': чужой клиент в тексте')
        try:
            release = date.fromisoformat(post['date'])
            if not date.fromisoformat(manifest['period_start']) <= release <= date.fromisoformat(manifest['period_end']):
                errors.append(str(pid) + ': дата вне периода')
        except (KeyError, ValueError):
            errors.append(str(pid) + ': неверная дата'); release = as_of
        for field in ['title', 'yandex', 'story_title', 'story_text', 'keyword', 'reader_need', 'button', 'button_url']:
            if not isinstance(post.get(field), str) or not post[field].strip():
                errors.append(str(pid) + ': пустое поле ' + field)
        if len(post.get('title', '') + '\n\n' + post.get('yandex', '')) > 3000:
            errors.append(str(pid) + ': превышен лимит Яндекса')
        if not post.get('button_url', '').startswith(('https://', 'tel:')):
            errors.append(str(pid) + ': неподдерживаемая ссылка кнопки')
        if len(post.get('story_text', '')) > 180:
            warnings.append(str(pid) + ': проверить читаемость длинного слайда; 180 — редакционная рекомендация, не лимит 2ГИС')
        keys = post.get('fact_keys', [])
        if not keys:
            errors.append(str(pid) + ': нет привязки утверждений к источникам')
        for key in keys:
            fact = facts.get(key)
            if not fact or fact.get('source') in [None, '', '?', 'TODO'] or fact.get('level') not in ['client_confirmed', 'public_source']:
                errors.append(str(pid) + ': отсутствует проверяемый источник факта ' + key)
                continue
            try:
                verified = date.fromisoformat(fact['verified_on'])
                until = date.fromisoformat(fact['valid_until'])
                if verified > as_of or until < max(as_of, release):
                    errors.append(str(pid) + ': факт вне срока редакционного допуска ' + key)
            except (ValueError, KeyError):
                errors.append(str(pid) + ': не задан срок источника ' + key)
        for platform, expected in [('yandex', (1200, 900)), ('2gis', (1080, 1920))]:
            name = post.get('photo_' + platform)
            path = local_file(name)
            if path:
                try:
                    with Image.open(path) as im:
                        if im.size != expected or im.format != 'JPEG':
                            errors.append(str(pid) + ': неправильный JPG/размер для ' + platform)
                        im.verify()
                    hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
                except Exception as exc:
                    errors.append(str(pid) + ': фото не читается: ' + type(exc).__name__)
            asset = manifest.get('assets', {}).get(name, {})
            if asset.get('kind') not in ['real_photo', 'ai_illustration'] or not asset.get('rights_basis') or not asset.get('source'):
                errors.append(str(pid) + ': нет происхождения/основания использования фото')
            if asset.get('kind') == 'ai_illustration' and not asset.get('not_documentary'):
                errors.append(str(pid) + ': AI-фото не отделено от документального кейса')

    bundle_sha256 = hashlib.sha256(json.dumps({'texts': posts, 'assets': manifest.get('assets', {}),
        'facts': facts, 'asset_sha256': hashes}, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

    def filled(value):
        return isinstance(value, str) and value.strip() not in ['', '?', '—', 'TODO', 'unknown']

    def review_passed(obj, through=as_of):
        if not isinstance(obj, dict) or obj.get('result') != 'pass' or not filled(obj.get('evidence')) or not filled(obj.get('reviewed_by')):
            return False
        try:
            return date.fromisoformat(obj['reviewed_on']) <= as_of and date.fromisoformat(obj['valid_until']) >= through
        except (KeyError, ValueError):
            return False

    reviews = manifest.get('reviews', {})
    latest_release = max([date.fromisoformat(p['date']) for p in posts if p.get('date') and p['date'][:4].isdigit()] + [as_of]) if not errors else as_of
    for gate in ['editorial', 'visual', 'facts']:
        if not review_passed(reviews.get(gate), latest_release) or reviews[gate].get('bundle_sha256') != bundle_sha256:
            blockers.append('Нет документированной проверки ' + gate)
    publication = manifest.get('publication_scope', {})
    if publication.get('authorized') is not True or not filled(publication.get('evidence')):
        blockers.append('Нет поручения на размещение: подготовка материалов не является поручением на публикацию')
    elif publication.get('client_id') != client or not publication.get('branch_ids') or not publication.get('platforms') or not publication.get('post_ids'):
        blockers.append('Не определён объём поручения: клиент, точки, площадки и ID публикаций')
    branches = manifest.get('branches', [])
    if not branches:
        blockers.append('Не задана целевая точка')
    branch_results = []
    for branch in branches:
        for platform in ['yandex', '2gis']:
            reasons = []
            target = branch.get(platform, {})
            reviewed_posts = target.get('post_ids', [])
            target_through = max([date.fromisoformat(p['date']) for p in posts if p.get('id') in reviewed_posts] + [as_of]) if not errors else as_of
            if not filled(target.get('card_id')) or not filled(target.get('card_url')):
                reasons.append('Нет ID/URL целевой карточки')
            for gate in ['identity', 'service_scope', 'access', 'format', 'contact']:
                if not review_passed(target.get(gate), target_through):
                    reasons.append('Не пройден допуск ' + gate)
            if not reviewed_posts or not set(reviewed_posts).issubset(seen):
                reasons.append('Не указан корректный набор публикаций для точки')
            if publication.get('authorized') is True:
                if branch.get('id') not in publication.get('branch_ids', []) or platform not in publication.get('platforms', []):
                    reasons.append('Точка/площадка вне поручения на размещение')
                if not set(reviewed_posts).issubset(publication.get('post_ids', [])):
                    reasons.append('Есть публикации вне поручения на размещение')
            if target.get('bundle_sha256') != bundle_sha256:
                reasons.append('Допуск точки не привязан к текущей версии материалов')
            branch_results.append({'branch_id': branch.get('id'), 'platform': platform,
                                   'publish_ready': not errors and not blockers and not reasons,
                                   'blockers': reasons})
    if any(not b['publish_ready'] for b in branch_results):
        blockers.append('Есть точки/площадки без полного допуска; см. branch_results')
    return {'client_id': client, 'as_of': as_of.isoformat(), 'posts_checked': len(posts),
            'material_checks_pass': not errors, 'publish_ready': not errors and not blockers,
            'errors': errors, 'warnings': warnings, 'publication_blockers': blockers,
            'branch_results': branch_results, 'asset_sha256': hashes, 'bundle_sha256': bundle_sha256,
            'limits': ['Проверены структура, даты, привязки к источникам и файлы; правдивость утверждений и видимость публикации код не устанавливает',
                       'Доступ и работа контакта проверяются в целевом кабинете; валидатор ничего не отправляет']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--require-publish-ready', action='store_true')
    args = parser.parse_args()
    result = validate(args.manifest, date.fromisoformat(args.as_of))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'asset_sha256'}, ensure_ascii=True, indent=2))
    return 0 if result['material_checks_pass'] and (result['publish_ready'] or not args.require_publish_ready) else 1


if __name__ == '__main__':
    raise SystemExit(main())
