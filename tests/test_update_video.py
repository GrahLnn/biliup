import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biliup import main


class FakeElementWait:
    def __init__(self, displayed=True, disabled_or_deleted=True):
        self._displayed = displayed
        self._disabled_or_deleted = disabled_or_deleted

    def displayed(self):
        return self._displayed

    def disabled_or_deleted(self):
        return self._disabled_or_deleted

    def not_covered(self):
        return True


class FakeClick:
    def __init__(self):
        self.clicked = False
        self.uploaded_path = None

    def __call__(self):
        self.clicked = True

    def to_upload(self, path):
        self.uploaded_path = path


class FakeSet:
    def __init__(self):
        self.inner_html = None

    def innerHTML(self, value):
        self.inner_html = value


class FakeStates:
    is_enabled = True
    is_alive = True


class FakeElement:
    def __init__(self, name):
        self.name = name
        self.click = FakeClick()
        self.wait = FakeElementWait()
        self.set = FakeSet()
        self.states = FakeStates()
        self.inputs = []

    def ele(self, locator):
        return FakeElement(locator)

    def input(self, value, clear=False):
        self.inputs.append((value, clear))


class FakeWait:
    def __init__(self, submit_confirmed):
        self.submit_confirmed = submit_confirmed

    def load_start(self):
        return True

    def eles_loaded(self, locator, timeout=None):
        if locator == "稿件投递成功":
            return self.submit_confirmed
        return True

    def __call__(self, seconds):
        self.waited_seconds = seconds


class FakeSetter:
    def __init__(self):
        self.cookies_value = None

    def cookies(self, cookies):
        self.cookies_value = cookies


class FakeChromiumOptions:
    def auto_port(self):
        return self

    def headless(self):
        return self

    def set_browser_path(self, browser_path):
        self.browser_path = browser_path
        return self


class FakeChromiumPage:
    instances = []
    submit_confirmed = True

    def __init__(self, options):
        self.options = options
        self.wait = FakeWait(self.submit_confirmed)
        self.set = FakeSetter()
        self.quit_called = False
        self.refreshed = False
        self.urls = []
        self.scripts = []
        FakeChromiumPage.instances.append(self)

    def get(self, url):
        self.urls.append(url)

    def ele(self, locator):
        return FakeElement(locator)

    def refresh(self):
        self.refreshed = True

    def add_ele(self, html, parent):
        self.added_html = html

    def run_js(self, script):
        self.scripts.append(script)

    def quit(self):
        self.quit_called = True


@pytest.fixture
def fake_browser(monkeypatch):
    FakeChromiumPage.instances = []
    FakeChromiumPage.submit_confirmed = True
    monkeypatch.setattr(main, "ChromiumOptions", FakeChromiumOptions)
    monkeypatch.setattr(main, "ChromiumPage", FakeChromiumPage)
    return FakeChromiumPage


def write_cookie_file(tmp_path):
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(
        json.dumps([{"name": "SESSDATA", "value": "x", "domain": ".bilibili.com", "path": "/"}]),
        encoding="utf-8",
    )
    return cookie_file


def call_update_video(cookie_file):
    return main.update_video(
        video_path="video.mp4",
        title="title",
        cover_path="cover.jpg",
        tags=["tag"],
        description="line 1\nline 2",
        cookie_path=str(cookie_file),
        headless=False,
    )


def test_update_video_returns_success_and_closes_browser_on_confirmed_submit(
    tmp_path, fake_browser
):
    result = call_update_video(write_cookie_file(tmp_path))

    assert result is True
    assert fake_browser.instances[-1].quit_called is True


def test_update_video_keeps_browser_open_when_submit_is_not_confirmed(
    tmp_path, fake_browser
):
    fake_browser.submit_confirmed = False
    stopped = {}

    def stop_for_test(exc):
        stopped["exc"] = exc

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(main, "_hold_browser_open_after_unexpected_stop", stop_for_test)
    try:
        call_update_video(write_cookie_file(tmp_path))
    finally:
        monkeypatch.undo()

    assert isinstance(stopped["exc"], main.UploadConfirmationError)
    assert fake_browser.instances[-1].quit_called is False
