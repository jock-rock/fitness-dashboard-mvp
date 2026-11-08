"""Run with Python + Playwright and system Chromium: python3 tests/exercise_images_smoke.py."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        # Tuesday, Thursday and Saturday all expose their exercise references.
        for navigation in range(3):
            if navigation:
                page.locator('#next').click()
            assert page.locator('#sessions .exercise-link').count() == 21
        links = page.locator('#sessions .exercise-link')
        for index in range(links.count()):
            button = links.nth(index)
            button.click()
            expect(page.locator('#exerciseDialog')).to_be_visible()
            assert page.locator('#exerciseTitle').inner_text() in button.inner_text()
            page.wait_for_function("Array.from(document.querySelectorAll('#exercisePhotos img')).every(i => i.complete && i.naturalWidth > 0)")
            assert page.locator('#exercisePhotos img').count() == 2
            page.keyboard.press('Escape')
            expect(page.locator('#exerciseDialog')).not_to_be_visible()
            expect(button).to_be_focused()
        # Guide links, including both alternatives, use the same modal.
        page.locator('[data-tab=workouts]').click()
        for detail in page.locator('#workoutGuide details').all():
            detail.locator('summary').click()
        assert page.locator('#workoutGuide .exercise-link').count() == 21
        page.locator('#workoutGuide .exercise-link').filter(has_text='Adductor rock-backs').click()
        assert 'Related movement:' in page.locator('#exerciseNote').inner_text()
        page.locator('#closeExercise').click()
        # Small viewport: the modal fits the screen, scrolls, and its close button works.
        page.set_viewport_size({'width': 320, 'height': 568})
        page.locator('#workoutGuide .exercise-link').first.click()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        rect = page.locator('#exerciseDialog').bounding_box()
        assert rect['x'] >= 0 and rect['x'] + rect['width'] <= 320
        page.locator('#closeExercise').click()
        # Missing asset gives an explicit fallback instead of silent broken imagery.
        page.route('**/assets/exercises/*.jpg', lambda route: route.abort())
        page.locator('#workoutGuide .exercise-link').last.click()
        expect(page.locator('#exerciseImageError')).to_be_visible()
        page.locator('#closeExercise').click()
        page.unroute('**/assets/exercises/*.jpg')
        # Tracking and reload persistence remain intact.
        page.locator('[data-tab=week]').click()
        while page.locator('#prev').is_enabled():
            page.locator('#prev').click()
        page.locator('#sessions input').first.check()
        page.locator('#weight').fill('88.4')
        page.reload()
        expect(page.locator('#adherence')).to_have_text('1/6')
        expect(page.locator('#weight')).to_have_value('88.4')
        assert not errors, errors
        browser.close()
    print('PASS: 21 exercise references, 42 images, guide links, keyboard/focus, mobile modal, image fallback, tracking persistence.')
finally:
    server.shutdown()
    server.server_close()
