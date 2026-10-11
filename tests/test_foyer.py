"""Independent regression checks for the room/foyer visual protocol."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from foyer_wrap import transform


class RoomFoyerTests(unittest.TestCase):
    def test_room_home_is_immutable(self):
        html = '<html><head></head><body class="room-home"><h1>Пространство</h1></body></html>'
        out, kind = transform(html, Path('index.html'))
        self.assertEqual(out, html)
        self.assertEqual(kind, 'home')

    def test_n0_is_a_foyer_without_interfering_with_question_contact_and_routes(self):
        html = ('<html><head><title>Question</title></head>'
                '<body class="new-master entry-router entry-short"><main>'
                '<section class="issue master-lead"><h1>Купить контрабас</h1>'
                '<p class="entry-modulation">Индивидуальное различение</p></section>'
                '<section class="contact-block">Телефон</section>'
                '<nav class="entry-range-grid">4 routes</nav>'
                '<nav class="entry-utilities">4 routes</nav>'
                '<footer class="master-footer">Контакты</footer></main></body></html>')
        out, kind = transform(html, Path('vhod/family/question/index.html'))
        self.assertEqual(kind, 'search')
        self.assertEqual(out.count('foyer-door-enter'), 1)
        self.assertIn('href="../../../"', out)
        self.assertIn('src="../../../assets/photography/room-golden.webp"', out)
        self.assertEqual(out.count('<h1>'), 1)
        self.assertEqual(out.count('class="contact-block"'), 1)
        self.assertEqual(out.count('entry-range-grid'), 1)
        self.assertLess(out.index('<h1>'), out.index('entry-modulation'))
        self.assertLess(out.index('entry-modulation'), out.index('class="contact-block"'))
        self.assertLess(out.index('class="contact-block"'), out.index('class="foyer-door'))
        self.assertLess(out.index('class="foyer-door'), out.index('class="entry-range-grid"'))
        self.assertEqual(transform(out, Path('vhod/family/question/index.html'))[0], out)

    def test_article_remains_intact_before_the_door(self):
        text = '<article class="knowledge-text"><h2>Сведения</h2><p>Источник</p></article>'
        html = ('<html><head></head><body class="new-master deep-editorial"><main>'
                '<h1>Контрабас</h1>' + text + '<section class="contact-block">Телефон</section>'
                '</main></body></html>')
        out, kind = transform(html, Path('details/bass/index.html'))
        self.assertEqual(kind, 'knowledge')
        self.assertIn(text, out)
        self.assertLess(out.index(text), out.index('class="foyer-door'))
        self.assertLess(out.index('class="foyer-door'), out.index('class="contact-block"'))
        self.assertIn('href="../../"', out)
        self.assertEqual(out.count('<h1>'), 1)

    def test_archive_and_legacy_publications_can_enter_same_room(self):
        html = '<html><head></head><body><main class="issue-body"><h1>Архив</h1></main></body></html>'
        out, kind = transform(html, Path('archive/001/index.html'))
        self.assertEqual(kind, 'institution')
        self.assertIn('class="foyer-page"', out)
        self.assertIn('href="../../assets/visual/foyer.css"', out)
        self.assertEqual(out.count('foyer-door-enter'), 1)
        self.assertLess(out.index('class="foyer-door'), out.index('</main>'))


if __name__ == '__main__':
    unittest.main()