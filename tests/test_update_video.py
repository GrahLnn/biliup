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
    def __init__(self, element=None):
        self.element = element
        self.clicked = False
        self.uploaded_path = None

    def __call__(self, *args, **kwargs):
        self.clicked = True
        if self.element is not None and self.element.page is not None:
            self.element.page.clicks.append((self.element.name, kwargs))
            if self.element.name in {
                "cover-settings",
                "cover-editor-done",
                "cover-post-confirm-done",
                "cover-dialog-confirm",
                "cover-sync-confirm",
            }:
                self.element.page.cover_actions.append((self.element.name, None))
            if self.element.name == "cover-editor-done":
                self.element.page.cover_done_available = False
            if self.element.name == "cover-dialog-confirm":
                if self.element.page.cover_post_confirm_done_required:
                    self.element.page.cover_post_confirm_done_available = True
                else:
                    self.element.page.cover_dialog_confirm_available = False
                if (
                    self.element.page.cover_sync_confirm_required
                    and not self.element.page.cover_post_confirm_done_required
                ):
                    self.element.page.cover_sync_confirm_available = True
            if self.element.name == "cover-post-confirm-done":
                self.element.page.cover_dialog_confirm_available = False
                self.element.page.cover_post_confirm_done_available = False
                if (
                    self.element.page.cover_sync_confirm_required
                    and not self.element.page.cover_done_after_sync_required
                ):
                    self.element.page.cover_sync_confirm_available = True
            if self.element.name == "cover-sync-confirm":
                self.element.page.cover_sync_confirm_available = False
                if self.element.page.cover_done_after_sync_required:
                    self.element.page.cover_post_confirm_done_available = True
            if self.element.name == "creation-statement-default":
                self.element.page.creation_statement_selected = True

    def to_upload(self, path):
        self.uploaded_path = path


class FakeSet:
    def __init__(self):
        self.inner_html = None

    def innerHTML(self, value):
        self.inner_html = value


class FakeStates:
    def __init__(self, displayed=True):
        self.is_enabled = True
        self.is_alive = True
        self.is_displayed = displayed


class FakeElement:
    def __init__(self, name, page=None, displayed=True, disabled_or_deleted=True):
        self.name = name
        self.page = page
        self.click = FakeClick(self)
        self.wait = FakeElementWait(disabled_or_deleted=disabled_or_deleted)
        self.set = FakeSet()
        self.states = FakeStates(displayed)
        self.inputs = []

    def ele(self, locator):
        child = FakeElement(locator, self.page)
        if self.page is not None:
            self.page.elements.append(child)
        return child

    def input(self, value, clear=False):
        self.inputs.append((value, clear))
        if self.page is not None:
            self.page.inputs.append((self.name, value, clear))
            if self.name == "cover-file-input":
                self.page.cover_upload_path = value
                if self.page.cover_upload_becomes_ready:
                    self.page.cover_upload_ready = True
                    self.page.cover_editor_loading = False
                self.page.cover_actions.append(("upload", value))


class FakeWait:
    def __init__(self, page):
        self.page = page

    @property
    def submit_confirmed(self):
        return self.page.submit_confirmed

    @property
    def cover_available(self):
        return self.page.cover_available

    @property
    def cover_done_available(self):
        return self.page.cover_done_available

    @property
    def cover_close_confirmed(self):
        return self.page.cover_close_confirmed

    @property
    def element_displayed(self):
        return self.page.element_displayed

    @property
    def element_disabled_or_deleted(self):
        return self.page.element_disabled_or_deleted

    def __init_old__(self, submit_confirmed):
        self.submit_confirmed = submit_confirmed

    def load_start(self):
        return True

    def eles_loaded(self, locator, timeout=None):
        if locator == "稿件投递成功":
            return self.submit_confirmed
        if "封面设置" in locator:
            return self.cover_available
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
    cover_available = True
    cover_done_available = True
    cover_close_confirmed = True
    cover_confirm_closes_after_click = True
    cover_sync_confirm_required = True
    cover_done_after_sync_required = False
    cover_post_confirm_done_required = False
    cover_upload_becomes_ready = True
    element_displayed = True
    element_disabled_or_deleted = True

    def __init__(self, options):
        self.options = options
        self.submit_confirmed = FakeChromiumPage.submit_confirmed
        self.cover_available = FakeChromiumPage.cover_available
        self.cover_done_available = FakeChromiumPage.cover_done_available
        self.cover_close_confirmed = FakeChromiumPage.cover_close_confirmed
        self.cover_confirm_closes_after_click = (
            FakeChromiumPage.cover_confirm_closes_after_click
        )
        self.cover_sync_confirm_required = FakeChromiumPage.cover_sync_confirm_required
        self.cover_done_after_sync_required = (
            FakeChromiumPage.cover_done_after_sync_required
        )
        self.cover_post_confirm_done_required = (
            FakeChromiumPage.cover_post_confirm_done_required
        )
        self.cover_upload_becomes_ready = FakeChromiumPage.cover_upload_becomes_ready
        self.cover_upload_ready = False
        self.cover_editor_loading = True
        self.cover_dialog_confirm_available = True
        self.cover_post_confirm_done_available = False
        self.cover_sync_confirm_available = False
        self.element_displayed = FakeChromiumPage.element_displayed
        self.element_disabled_or_deleted = FakeChromiumPage.element_disabled_or_deleted
        self.wait = FakeWait(self)
        self.set = FakeSetter()
        self.quit_called = False
        self.refreshed = False
        self.urls = []
        self.scripts = []
        self.clicks = []
        self.inputs = []
        self.elements = []
        self.cover_upload_path = None
        self.cover_actions = []
        self.creation_statement_selected = False
        self.html = "<html><body>debug page</body></html>"
        FakeChromiumPage.instances.append(self)

    def get(self, url):
        self.urls.append(url)

    def ele(self, locator):
        element = FakeElement(locator, self)
        if locator == ".video-title" or locator == ".tag-container":
            element.wait = FakeElementWait(displayed=self.element_displayed)
        self.elements.append(element)
        return element

    def eles(self, locator, timeout=None):
        if "内容无需标注" in locator:
            return [
                FakeElement(
                    "creation-statement-default",
                    self,
                    displayed=True,
                )
            ]
        if "创作声明" in locator or "请选择符合您视频内容的创作声明" in locator:
            return [
                FakeElement(
                    "creation-statement-select",
                    self,
                    displayed=True,
                )
            ]
        if "edit-text" in locator or "封面设置" in locator:
            return [FakeElement("cover-settings", self, displayed=self.cover_available)]
        if (
            "上传封面" in locator
            or "cover-editor-panel-select" in locator
            or ".cover-editor-panel-select .cover-upload" in locator
            or ".cover-editor .cover-upload" in locator
        ):
            if "has-image" in locator:
                if not self.cover_upload_ready:
                    return []
                return [FakeElement("cover-upload-preview", self, displayed=True)]
            return [FakeElement("cover-file-input", self, displayed=False)]
        if "cover-editor-panel-canvas-loading" in locator or "upload-mask" in locator:
            if not self.cover_editor_loading:
                return []
            return [FakeElement("cover-editor-loading", self, displayed=True)]
        if "cover-editor-button" in locator and "完成" in locator:
            if self.cover_done_available:
                name = "cover-editor-done"
            elif self.cover_post_confirm_done_available:
                name = "cover-post-confirm-done"
            else:
                return []
            return [
                FakeElement(
                    name,
                    self,
                    displayed=True,
                )
            ]
        if "bcc-dialog__footer" in locator and "确认同步" in locator:
            if not self.cover_sync_confirm_available:
                return []
            return [
                FakeElement(
                    "cover-sync-confirm",
                    self,
                    displayed=True,
                    disabled_or_deleted=True,
                )
            ]
        if "bcc-dialog__footer" in locator and (
            "确定" in locator or "确认" in locator
        ):
            if not self.cover_dialog_confirm_available:
                return []
            return [
                FakeElement(
                    "cover-dialog-confirm",
                    self,
                    displayed=self.cover_close_confirmed,
                    disabled_or_deleted=self.cover_confirm_closes_after_click,
                )
            ]
        return []

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
    FakeChromiumPage.cover_available = True
    FakeChromiumPage.cover_done_available = True
    FakeChromiumPage.cover_close_confirmed = True
    FakeChromiumPage.cover_confirm_closes_after_click = True
    FakeChromiumPage.cover_sync_confirm_required = True
    FakeChromiumPage.cover_done_after_sync_required = False
    FakeChromiumPage.cover_post_confirm_done_required = False
    FakeChromiumPage.cover_upload_becomes_ready = True
    FakeChromiumPage.element_displayed = True
    FakeChromiumPage.element_disabled_or_deleted = True
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
    return call_update_video_with_cover(cookie_file, "cover.jpg")


def call_update_video_with_cover(cookie_file, cover_path):
    return main.update_video(
        video_path="video.mp4",
        title="title",
        cover_path=cover_path,
        tags=["tag"],
        description="line 1\nline 2",
        cookie_path=str(cookie_file),
        headless=False,
    )


def test_update_video_returns_success_and_closes_browser_on_confirmed_submit(
    tmp_path, fake_browser
):
    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]
    expected_cover_path = str(Path("cover.jpg").resolve())

    assert result is True
    assert page.quit_called is True
    assert page.cover_actions == [
        ("cover-settings", None),
        ("upload", expected_cover_path),
        ("cover-editor-done", None),
        ("cover-dialog-confirm", None),
        ("cover-sync-confirm", None),
    ]


def test_update_video_selects_creation_statement_before_cover_upload(
    tmp_path, fake_browser
):
    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]
    click_names = [name for name, _ in page.clicks]

    assert result is True
    assert page.creation_statement_selected is True
    assert click_names.index("creation-statement-select") < click_names.index(
        "cover-settings"
    )
    assert click_names.index("creation-statement-default") < click_names.index(
        "cover-settings"
    )
    assert "creation-statement-select" not in [
        name for name, _ in page.cover_actions
    ]
    assert "creation-statement-default" not in [
        name for name, _ in page.cover_actions
    ]


def test_update_video_keeps_browser_open_when_submit_is_not_confirmed(
    tmp_path, fake_browser, monkeypatch
):
    fake_browser.submit_confirmed = False
    stopped = {}

    def stop_for_test(exc):
        stopped["exc"] = exc

    monkeypatch.setattr(main, "_hold_browser_open_after_unexpected_stop", stop_for_test)
    call_update_video(write_cookie_file(tmp_path))

    assert isinstance(stopped["exc"], main.UploadConfirmationError)
    assert fake_browser.instances[-1].quit_called is False


def test_update_video_continues_metadata_fields_when_cover_dialog_fails(
    tmp_path, fake_browser, monkeypatch
):
    debug_path = tmp_path / "biliup_upload_debug_latest.html"
    fake_browser.cover_available = False
    monkeypatch.setattr(main, "SNAPSHOT_PATH", debug_path)

    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]

    assert result is True
    assert page.quit_called is True
    assert any(value == "title" for _, value, _ in page.inputs)
    assert any(value == "tag\n" for _, value, _ in page.inputs)
    assert debug_path.read_text(encoding="utf-8").startswith("<!-- cover dialog failed:")


def test_cover_upload_ready_wait_requires_uploaded_preview(fake_browser):
    page = fake_browser(None)
    fake_browser.cover_upload_becomes_ready = False

    with pytest.raises(main.CoverUploadError):
        main._wait_for_cover_upload_ready(page, timeout=0.01)

    assert page.cover_upload_ready is False


def test_update_video_clicks_both_cover_confirmation_layers(tmp_path, fake_browser):
    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]
    expected_cover_path = str(Path("cover.jpg").resolve())

    assert result is True
    assert page.cover_upload_path == expected_cover_path
    assert page.cover_actions == [
        ("cover-settings", None),
        ("upload", expected_cover_path),
        ("cover-editor-done", None),
        ("cover-dialog-confirm", None),
        ("cover-sync-confirm", None),
    ]


def test_update_video_normalizes_cover_path_for_file_input(tmp_path, fake_browser):
    cover_file = tmp_path / "cover.jpg"
    cover_file.write_bytes(b"image")

    result = call_update_video_with_cover(write_cookie_file(tmp_path), cover_file)
    page = fake_browser.instances[-1]

    assert result is True
    assert isinstance(page.cover_upload_path, str)
    assert page.cover_upload_path == str(cover_file.resolve())


def test_update_video_accepts_cover_confirmation_without_sync_layer(
    tmp_path, fake_browser
):
    fake_browser.cover_sync_confirm_required = False

    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]

    assert result is True
    assert ("cover-dialog-confirm", None) in page.cover_actions
    assert ("cover-sync-confirm", None) not in page.cover_actions


def test_update_video_clicks_cover_done_after_confirm_layer(tmp_path, fake_browser):
    fake_browser.cover_confirm_closes_after_click = False
    fake_browser.cover_post_confirm_done_required = True

    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]
    expected_cover_path = str(Path("cover.jpg").resolve())

    assert result is True
    assert page.cover_actions == [
        ("cover-settings", None),
        ("upload", expected_cover_path),
        ("cover-editor-done", None),
        ("cover-dialog-confirm", None),
        ("cover-post-confirm-done", None),
        ("cover-sync-confirm", None),
    ]


def test_update_video_clicks_cover_done_after_sync_confirm(tmp_path, fake_browser):
    fake_browser.cover_done_after_sync_required = True

    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]
    expected_cover_path = str(Path("cover.jpg").resolve())

    assert result is True
    assert page.cover_actions == [
        ("cover-settings", None),
        ("upload", expected_cover_path),
        ("cover-editor-done", None),
        ("cover-dialog-confirm", None),
        ("cover-sync-confirm", None),
        ("cover-post-confirm-done", None),
    ]
