#!/usr/bin/env python3
"""Give existing static EasyBassMaster routes one visual doorway to the room.

The root page is the room itself. Every other pre-existing URL remains its own
search/editorial destination with its own H1, text, canonical and contact; this
final post-render presentation pass provides a consistent way into the room.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

MARKER = 'data-foyer="r1"'


def _body_tag(match: re.Match[str]) -> str:
    tag = match.group(0)
    if "data-foyer=" in tag:
        return tag
    classes = re.search(r'class=["\']([^"\']*)["\']', tag)
    if classes:
        before = classes.group(0)
        tag = tag.replace(before, 'class="' + classes.group(1) + ' foyer-page"', 1)
    else:
        tag = tag.replace('<body', '<body class="foyer-page"', 1)
    return tag[:-1] + ' ' + MARKER + '>'


def _door(depth: int, kind: str) -> str:
    """A link to the EXISTING home page, not an extra indexed landing route."""
    root = '../' * depth if depth else './'
    if kind == 'search':
        kicker = 'Ваш запрос · вход в мастерскую'
        heading = 'За этим вопросом есть живая комната.'
        description = ('Можно увидеть инструменты рядом, услышать различия и '
                       'договориться о встрече. Начать знакомство можно здесь.')
    elif kind == 'knowledge':
        kicker = 'От знания к живому инструменту'
        heading = 'Продолжить знакомство в мастерской.'
        description = ('Текст помогает разобраться в вопросе. В мастерской '
                       'можно встретиться с инструментами, услышать их и сыграть.')
    else:
        kicker = 'Из прихожей · в коллекцию'
        heading = 'Пространство, в котором можно найти свой.'
        description = ('Комната с контрабасами, мастерская, коллекция '
                       'и возможность познакомиться лично.')
    return (
        '\n<section class="foyer-door foyer-door-' + kind + '" '
        'aria-label="Вход в пространство EasyBassMaster">'
        '<div class="foyer-door-image">'
        '<img src="' + root + 'assets/photography/room-golden.webp" '
        'width="1448" height="1086" loading="lazy" decoding="async" '
        'alt="Художественный вид комнаты с рядами контрабасов EasyBassMaster"></div>'
        '<div class="foyer-door-copy">'
        '<p class="foyer-door-kicker">' + kicker + '</p>'
        '<h2>' + heading + '</h2>'
        '<p>' + description + '</p>'
        '<a class="foyer-door-enter" href="' + root + '">Войти в мастерскую '
        '<span aria-hidden="true">↗</span></a>'
        '</div></section>\n'
    )


def transform(html: str, relative_path: Path) -> tuple[str, str]:
    """Transform a Jekyll/Python-rendered HTML page. Idempotent and non-destructive."""
    if relative_path.as_posix() == 'index.html':
        return html, 'home'
    if MARKER in html:
        return html, 'already'
    if '</head>' not in html or '</body>' not in html:
        raise ValueError(f'{relative_path}: missing HTML shell')
    route = relative_path.as_posix()
    if not route.endswith('/index.html'):
        raise ValueError(f'{relative_path}: only pretty-route index.html documents are supported')
    depth = len(relative_path.parts) - 1
    root = '../' * depth

    is_search = bool(re.search(r'<body[^>]*class=["\'][^"\']*entry-router', html))
    is_deep = bool(re.search(r'<body[^>]*class=["\'][^"\']*deep-editorial', html))
    kind = 'search' if is_search else 'knowledge' if is_deep else 'institution'

    link = f'<link rel="stylesheet" href="{root}assets/visual/foyer.css">'
    html = html.replace('</head>', link + '\n</head>', 1)
    html, count = re.subn(r'<body\b[^>]*>', _body_tag, html, count=1)
    if count != 1:
        raise ValueError(f'{relative_path}: unable to locate body')

    door = _door(depth, kind)
    if is_search:
        # Preserve the precise query -> single authored sentence -> phone order.
        # The visitor then sees the door before the original 4 + 4 routes.
        match = re.search(r'<section\b[^>]*class="[^"]*\bcontact-block\b[^"]*"[^>]*>[\s\S]*?</section>', html)
        if not match:
            raise ValueError(f'{relative_path}: N.0 has no verified contact block')
        html = html[:match.end()] + door + html[match.end():]
    else:
        # On deep knowledge and institutional pages, read the actual material
        # before the invitation. Nothing is inserted between source sections.
        match = re.search(r'<section\b[^>]*class="[^"]*\bcontact-block\b[^"]*"[^>]*>', html)
        if match:
            html = html[:match.start()] + door + html[match.start():]
        elif '</main>' in html:
            html = html.replace('</main>', door + '</main>', 1)
        else:
            raise ValueError(f'{relative_path}: unable to find an editorial exit')
    return html, kind


def build(site: Path) -> dict:
    site = site.resolve()
    if not (site / 'index.html').exists():
        raise ValueError('Jekyll output is missing index.html')
    if not (site / 'assets/visual/foyer.css').exists():
        raise ValueError('Compiled CSS is missing assets/visual/foyer.css')
    if not (site / 'assets/photography/room-golden.webp').exists():
        raise ValueError('Compiled photo is missing assets/photography/room-golden.webp')
    kinds = Counter()
    for path in sorted(site.rglob('*.html')):
        relative = path.relative_to(site)
        raw = path.read_text(encoding='utf-8')
        output, kind = transform(raw, relative)
        if output != raw:
            path.write_text(output, encoding='utf-8')
        kinds[kind] += 1
    return {'total_html': sum(kinds.values()), 'categories': dict(kinds),
            'single_room': kinds['home'] == 1,
            'foyer_pages': sum(v for k, v in kinds.items() if k in {'search', 'knowledge', 'institution'})}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path('_site'))
    parser.add_argument('--report', type=Path, default=Path('_audit/foyer.json'))
    args = parser.parse_args()
    report = build(args.site)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()