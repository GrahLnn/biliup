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
                "cover-main-entry",
                "cover-upload-trigger",
                "cover-editor-done",
            }:
                self.element.page.cover_actions.append((self.element.name, None))
            if self.element.name == "cover-main-entry":
                self.element.page.cover_editor_open = True
            if self.element.name == "cover-editor-done":
                self.element.page.cover_done_available = False
                if self.element.page.cover_editor_closes_after_done:
                    self.element.page.cover_editor_open = False
                    self.element.page.main_cover_identity = (
                        'url("https://archive.biliimg.com/uploaded-cover.jpg")'
                    )
            if self.element.name == "creation-statement-default":
                self.element.page.creation_statement_selected = True

    def to_upload(self, path):
        self.uploaded_path = path
        if self.element.name != "cover-upload-trigger":
            return
        self.__call__()
        page = self.element.page
        if page.cover_file_selection_applies:
            page.cover_upload_path = path
            page.cover_actions.append(("upload", path))
            if page.cover_upload_applies:
                page.cover_preview_identity = 'url("blob:uploaded-cover")'
                page.cover_editor_loading = False
        elif page.system_preview_changes:
            page.cover_preview_identity = 'url("blob:another-system-frame")'


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

    def style(self, name):
        if name == "background-image" and self.page is not None:
            if self.name == "main-cover-image":
                return self.page.main_cover_identity
            return self.page.cover_preview_identity
        return ""

    def run_js(self, script):
        if self.name != "cover-file-input" or self.page.cover_upload_path is None:
            return None
        cover_path = Path(self.page.cover_upload_path)
        return [cover_path.name, cover_path.stat().st_size]


class FakeWait:
    def __init__(self, page):
        self.page = page

    @property
    def submit_confirmed(self):
        return self.page.submit_confirmed

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
        if "添加主封面" in locator:
            return self.page.main_cover_available
        return True

    def __call__(self, seconds):
        self.waited_seconds = seconds


class FakeSetter:
    def __init__(self, page):
        self.page = page
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
    main_cover_available = True
    pk_cover_available = False
    cover_done_available = True
    cover_editor_closes_after_done = True
    cover_file_selection_applies = True
    unrelated_confirm_available = False
    cover_upload_applies = True
    system_preview_changes = False
    element_displayed = True
    element_disabled_or_deleted = True

    def __init__(self, options):
        self.options = options
        self.submit_confirmed = FakeChromiumPage.submit_confirmed
        self.main_cover_available = FakeChromiumPage.main_cover_available
        self.pk_cover_available = FakeChromiumPage.pk_cover_available
        self.cover_done_available = FakeChromiumPage.cover_done_available
        self.cover_editor_closes_after_done = (
            FakeChromiumPage.cover_editor_closes_after_done
        )
        self.cover_file_selection_applies = (
            FakeChromiumPage.cover_file_selection_applies
        )
        self.unrelated_confirm_available = (
            FakeChromiumPage.unrelated_confirm_available
        )
        self.cover_editor_open = False
        self.cover_upload_applies = FakeChromiumPage.cover_upload_applies
        self.system_preview_changes = FakeChromiumPage.system_preview_changes
        self.cover_preview_identity = 'url("blob:video-frame")'
        self.cover_editor_loading = False
        self.main_cover_identity = None
        self.element_displayed = FakeChromiumPage.element_displayed
        self.element_disabled_or_deleted = FakeChromiumPage.element_disabled_or_deleted
        self.wait = FakeWait(self)
        self.set = FakeSetter(self)
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
        if "添加主封面" in locator:
            if not self.main_cover_available:
                return []
            return [FakeElement("cover-main-entry", self, displayed=True)]
        if "添加PK封面" in locator:
            if not self.pk_cover_available:
                return []
            return [FakeElement("cover-pk-entry", self, displayed=True)]
        if "上传封面" in locator and "upload-area" in locator:
            return [FakeElement("cover-upload-trigger", self, displayed=True)]
        if "input[@type='file'" in locator and "image/png, image/jpeg" in locator:
            return [FakeElement("cover-file-input", self, displayed=False)]
        if "cover-editor-panel-canvas-loading" in locator or "upload-mask" in locator:
            if not self.cover_editor_loading:
                return []
            return [FakeElement("cover-editor-loading", self, displayed=True)]
        if "cover-editor-button" in locator and "完成" in locator:
            if not self.cover_done_available:
                return []
            return [FakeElement("cover-editor-done", self, displayed=True)]
        if "cover-editor-content" in locator:
            if not self.cover_editor_open:
                return []
            return [FakeElement("cover-editor-content", self, displayed=True)]
        if "cover-main" in locator and "cover-img" in locator:
            if self.main_cover_identity is None:
                return []
            return [FakeElement("main-cover-image", self, displayed=True)]
        if "bcc-dialog__footer" in locator and (
            "确定" in locator or "确认" in locator
        ):
            if self.unrelated_confirm_available:
                return [FakeElement("unrelated-confirm", self, displayed=True)]
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
    FakeChromiumPage.main_cover_available = True
    FakeChromiumPage.pk_cover_available = False
    FakeChromiumPage.cover_done_available = True
    FakeChromiumPage.cover_editor_closes_after_done = True
    FakeChromiumPage.cover_file_selection_applies = True
    FakeChromiumPage.unrelated_confirm_available = False
    FakeChromiumPage.cover_upload_applies = True
    FakeChromiumPage.system_preview_changes = False
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


def write_cover_file(tmp_path):
    cover_file = tmp_path / "cover.jpg"
    cover_file.write_bytes(b"downloaded cover image")
    return cover_file


def call_update_video(cookie_file):
    return call_update_video_with_cover(
        cookie_file, write_cover_file(cookie_file.parent)
    )


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


def test_try_upload_cover_accepts_main_cover_entry_before_file_upload(
    tmp_path, fake_browser, monkeypatch
):
    page = fake_browser(None)
    page.main_cover_available = True
    page.pk_cover_available = True
    monkeypatch.setattr(main, "_save_debug_html", lambda *args, **kwargs: None)
    cover_file = write_cover_file(tmp_path)

    result = main._try_upload_cover(page, cover_file)

    expected_cover_path = str(cover_file.resolve())
    assert result is True
    assert page.cover_actions[0] == ("cover-main-entry", None)
    assert ("cover-upload-trigger", None) in page.cover_actions
    assert page.cover_actions.index(("cover-upload-trigger", None)) < page.cover_actions.index(
        ("upload", expected_cover_path)
    )
    assert page.cover_actions.index(("cover-main-entry", None)) < page.cover_actions.index(
        ("upload", expected_cover_path)
    )
    assert ("cover-pk-entry", None) not in page.cover_actions


def test_try_upload_cover_does_not_accept_pk_cover_entry(
    tmp_path, fake_browser, monkeypatch
):
    page = fake_browser(None)
    page.main_cover_available = False
    page.pk_cover_available = True
    monkeypatch.setattr(main, "_save_debug_html", lambda *args, **kwargs: None)

    result = main._try_upload_cover(page, write_cover_file(tmp_path))

    assert result is False
    assert page.cover_upload_path is None
    assert ("cover-pk-entry", None) not in page.cover_actions


def test_try_upload_cover_does_not_confirm_preexisting_video_frame(
    tmp_path, fake_browser, monkeypatch
):
    page = fake_browser(None)
    page.cover_upload_applies = False
    monkeypatch.setattr(main, "_save_debug_html", lambda *args, **kwargs: None)
    wait_for_upload = main._wait_for_cover_upload_ready
    monkeypatch.setattr(
        main,
        "_wait_for_cover_upload_ready",
        lambda driver, previous_preview: wait_for_upload(
            driver, previous_preview, timeout=0.01
        ),
    )

    result = main._try_upload_cover(page, write_cover_file(tmp_path))

    assert result is False
    assert ("cover-editor-done", None) not in page.cover_actions


def test_try_upload_cover_rejects_system_preview_when_file_was_not_selected(
    tmp_path, fake_browser, monkeypatch
):
    page = fake_browser(None)
    page.cover_file_selection_applies = False
    page.system_preview_changes = True
    monkeypatch.setattr(main, "_save_debug_html", lambda *args, **kwargs: None)
    wait_for_selection = main._wait_for_cover_file_selected
    monkeypatch.setattr(
        main,
        "_wait_for_cover_file_selected",
        lambda upload_input, cover_path: wait_for_selection(
            upload_input, cover_path, timeout=0.01
        ),
    )

    result = main._try_upload_cover(page, write_cover_file(tmp_path))

    assert result is False
    assert page.cover_upload_path is None
    assert ("cover-editor-done", None) not in page.cover_actions


def test_try_upload_cover_ignores_unrelated_confirm_after_editor_closes(
    tmp_path, fake_browser, monkeypatch
):
    page = fake_browser(None)
    page.unrelated_confirm_available = True
    monkeypatch.setattr(main, "_save_debug_html", lambda *args, **kwargs: None)

    result = main._try_upload_cover(page, write_cover_file(tmp_path))

    assert page.cover_editor_open is False
    assert result is True
    assert "unrelated-confirm" not in [name for name, _ in page.clicks]


def test_try_upload_cover_rejects_editor_that_does_not_close(
    tmp_path, fake_browser, monkeypatch
):
    page = fake_browser(None)
    page.cover_editor_closes_after_done = False
    monkeypatch.setattr(main, "_save_debug_html", lambda *args, **kwargs: None)
    wait_for_close = main._wait_for_cover_editor_closed
    monkeypatch.setattr(
        main,
        "_wait_for_cover_editor_closed",
        lambda driver: wait_for_close(driver, timeout=0.01),
    )

    result = main._try_upload_cover(page, write_cover_file(tmp_path))

    assert result is False
    assert page.cover_editor_open is True
    assert page.main_cover_identity is None


def test_update_video_returns_success_and_closes_browser_on_confirmed_submit(
    tmp_path, fake_browser
):
    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]
    expected_cover_path = str((tmp_path / "cover.jpg").resolve())

    assert result is True
    assert page.quit_called is True
    assert page.cover_actions == [
        ("cover-main-entry", None),
        ("cover-upload-trigger", None),
        ("upload", expected_cover_path),
        ("cover-editor-done", None),
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
        "cover-main-entry"
    )
    assert click_names.index("creation-statement-default") < click_names.index(
        "cover-main-entry"
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
    fake_browser.main_cover_available = False
    monkeypatch.setattr(main, "SNAPSHOT_PATH", debug_path)

    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]

    assert result is True
    assert page.quit_called is True
    assert any(value == "title" for _, value, _ in page.inputs)
    assert any(value == "tag\n" for _, value, _ in page.inputs)
    assert debug_path.read_text(encoding="utf-8").startswith("<!-- cover dialog failed:")


def test_cover_upload_ready_wait_requires_changed_preview(fake_browser):
    page = fake_browser(None)
    previous_preview = page.cover_preview_identity

    with pytest.raises(main.CoverUploadError):
        main._wait_for_cover_upload_ready(page, previous_preview, timeout=0.01)


def test_update_video_applies_uploaded_cover_without_global_confirmation(
    tmp_path, fake_browser
):
    result = call_update_video(write_cookie_file(tmp_path))
    page = fake_browser.instances[-1]
    expected_cover_path = str((tmp_path / "cover.jpg").resolve())

    assert result is True
    assert page.cover_upload_path == expected_cover_path
    assert page.cover_actions == [
        ("cover-main-entry", None),
        ("cover-upload-trigger", None),
        ("upload", expected_cover_path),
        ("cover-editor-done", None),
    ]


def test_update_video_normalizes_cover_path_for_file_input(tmp_path, fake_browser):
    cover_file = tmp_path / "cover.jpg"
    cover_file.write_bytes(b"image")

    result = call_update_video_with_cover(write_cookie_file(tmp_path), cover_file)
    page = fake_browser.instances[-1]

    assert result is True
    assert isinstance(page.cover_upload_path, str)
    assert page.cover_upload_path == str(cover_file.resolve())
