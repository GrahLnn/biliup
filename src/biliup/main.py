import json
import os
import time
from pathlib import Path

from DrissionPage import ChromiumOptions, ChromiumPage


class UploadConfirmationError(RuntimeError):
    """Raised when Bilibili upload did not reach the success confirmation state."""


SNAPSHOT_PATH = Path("biliup_upload_debug_latest.html")


class CoverUploadError(RuntimeError):
    """Raised when Bilibili cover upload controls are not in the expected state."""


class CreationStatementError(RuntimeError):
    """Raised when Bilibili creation statement controls are not in the expected state."""


def _wait_for_required_result(wait_call, message):
    result = wait_call()
    if result is False:
        raise UploadConfirmationError(message)
    return result


def _save_debug_html(driver, reason, path=None):
    if path is None:
        path = SNAPSHOT_PATH
    html = getattr(driver, "html", "")
    payload = f"<!-- {reason} -->\n{html}"
    snapshot_path = Path(path).resolve()
    snapshot_path.write_text(payload, encoding="utf-8")
    print(f"Biliup debug HTML saved: {snapshot_path}")
    return snapshot_path


def _first_available(driver, locators, message, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for locator in locators:
            for element in driver.eles(locator, timeout=0.5):
                return element
        time.sleep(0.2)
    raise CoverUploadError(message)


def _first_displayed(driver, locators, message, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for locator in locators:
            for element in driver.eles(locator, timeout=0.5):
                if element.states.is_displayed:
                    return element
        time.sleep(0.2)
    raise CoverUploadError(message)


def _click_first_displayed(driver, locators, message):
    element = _first_displayed(driver, locators, message)
    element.click(by_js=True)
    return element


def _click_optional_displayed(driver, locators, timeout=3):
    try:
        element = _first_displayed(driver, locators, "", timeout=timeout)
    except CoverUploadError:
        return None
    element.click(by_js=True)
    return element


def _select_default_creation_statement(driver):
    try:
        _click_first_displayed(
            driver,
            (
                "xpath://h3[normalize-space()='创作声明']/ancestor::div[contains(@class, 'creation-statement-container')]//input[contains(@class, 'bcc-select-input-inner')]",
                "xpath://input[@placeholder='请选择符合您视频内容的创作声明']",
            ),
            "Creation statement selector is not visible.",
        )
        _click_first_displayed(
            driver,
            (
                "xpath://h3[normalize-space()='创作声明']/ancestor::div[contains(@class, 'creation-statement-container')]//li[contains(@class, 'bcc-option')][.//span[normalize-space()='内容无需标注']]",
                "xpath://li[contains(@class, 'bcc-option')][.//span[normalize-space()='内容无需标注']]",
            ),
            "Default creation statement option is not visible.",
        )
    except CoverUploadError as exc:
        raise CreationStatementError(str(exc)) from exc


def _confirm_cover_dialogs(driver, max_clicks=8):
    sync_locators = (
        "xpath://div[contains(@class, 'bcc-dialog__footer')]//button[contains(@class, 'bcc-button--primary')][.//span[normalize-space()='确认同步']]",
    )
    confirm_locators = (
        "xpath://div[contains(@class, 'bcc-dialog__footer')]//button[contains(@class, 'bcc-button--primary')][.//span[normalize-space()='确定']]",
        "xpath://div[contains(@class, 'bcc-dialog__footer')]//button[contains(@class, 'bcc-button--primary')][.//span[normalize-space()='确认']]",
    )
    completion_locators = (
        "xpath://div[contains(@class, 'cover-editor-button')]//div[contains(@class, 'submit') and contains(normalize-space(), '完成')]",
        "xpath://div[contains(@class, 'cover-editor-button')]//*[contains(normalize-space(), '完成')]",
    )
    clicked = False
    for _ in range(max_clicks):
        sync = _click_optional_displayed(driver, sync_locators, timeout=1)
        if sync is not None:
            clicked = True
            sync.wait.disabled_or_deleted()
            completion = _click_optional_displayed(driver, completion_locators, timeout=5)
            if completion is not None:
                clicked = True
                completion.wait.disabled_or_deleted()
            continue

        completion = _click_optional_displayed(driver, completion_locators, timeout=1)
        if completion is None:
            confirm = _click_optional_displayed(driver, confirm_locators, timeout=1)
            if confirm is None:
                break
            clicked = True
            confirm.wait.disabled_or_deleted()
            continue

        clicked = True
        completion.wait.disabled_or_deleted()
    else:
        raise CoverUploadError("Cover confirmation dialog did not close.")

    if not clicked:
        raise CoverUploadError("Cover confirmation button is not visible.")


def _wait_for_cover_upload_ready(driver, previous_preview, timeout=30):
    preview_locator = (
        "xpath://div[contains(@class, 'cover-editor-panel-select')]//div[contains(@class, 'cover-upload')]//div[contains(@class, 'upload-area')][.//span[normalize-space()='上传封面']]"
    )
    deadline = time.monotonic() + timeout
    loading_locators = (
        "css:.cover-editor-panel-canvas-loading",
        "css:.cover-editor-panel-canvas .upload-mask",
    )
    stable_preview = None
    stable_since = None
    while time.monotonic() < deadline:
        preview = None
        for element in driver.eles(preview_locator, timeout=0.5):
            if element.states.is_displayed:
                preview = element.style("background-image")
                break

        is_loading = False
        for locator in loading_locators:
            for element in driver.eles(locator, timeout=0.5):
                if element.states.is_displayed:
                    is_loading = True
                    break
            if is_loading:
                break

        if preview and preview != "none" and preview != previous_preview and not is_loading:
            now = time.monotonic()
            if preview != stable_preview:
                stable_preview = preview
                stable_since = now
            elif stable_since is not None and now - stable_since >= 0.5:
                return
        else:
            stable_preview = None
            stable_since = None
        time.sleep(0.1)
    raise CoverUploadError("Cover preview did not change after selecting the upload file.")


def _try_upload_cover(driver, cover_path):
    try:
        cover_file = str(Path(cover_path).expanduser().resolve())
        cover_entry_locator = (
            "xpath://div[contains(concat(' ',normalize-space(@class),' '), ' cover-empty-pill ')][.//span[normalize-space()='添加主封面']]"
        )
        _wait_for_required_result(
            lambda: driver.wait.eles_loaded(cover_entry_locator),
            "Upload page did not expose cover settings after video upload.",
        )
        _click_first_displayed(
            driver,
            (cover_entry_locator,),
            "Cover settings entry is not visible.",
        )

        upload_trigger = _first_displayed(
            driver,
            (
                "xpath://div[contains(@class, 'cover-editor-panel-select')]//div[contains(@class, 'cover-upload')]//div[contains(@class, 'upload-area')][.//span[normalize-space()='上传封面']]",
            ),
            "Cover upload control is not visible.",
        )
        previous_preview = upload_trigger.style("background-image")
        driver.set.upload_files(cover_file)
        upload_trigger.click()
        _wait_for_cover_upload_ready(driver, previous_preview)

        _click_first_displayed(
            driver,
            (
                "xpath://div[contains(@class, 'cover-editor-button')]//div[contains(@class, 'submit') and contains(normalize-space(), '完成')]",
                "xpath://div[contains(@class, 'cover-editor-button')]//*[contains(normalize-space(), '完成')]",
            ),
            "Cover editor completion button is not visible.",
        )

        _confirm_cover_dialogs(driver)
        return True
    except Exception as exc:
        _save_debug_html(driver, f"cover dialog failed: {exc}")
        print(f"Cover dialog failed, continuing with metadata fields: {exc}")
        return False


def _hold_browser_open_after_unexpected_stop(exc):
    print(
        "Upload stopped before Bilibili confirmed success. "
        "The browser will stay open for manual inspection."
    )
    print(f"Reason: {exc}")
    while True:
        time.sleep(3600)


def update_video(
    video_path,
    title,
    cover_path,
    tags,
    description,
    cookie_path,
    browser_path=None,
    headless=True,
):
    """
    Update a video on Bilibili platform.
    Args:
        video_path (str): The path to the video file.
        title (str): The title of the video.
        cover_path (str): The path to the cover image file.
        tags (list): A list of tags for the video.
        description (str): The description of the video.
        cookie_path (str): The path to the cookie file.
    Returns:
        None
    Raises:
        FileNotFoundError: If the video file or cookie file is not found.
    """
    driver = None
    upload_confirmed = False

    with open(cookie_path) as f:
        file_ext = os.path.splitext(cookie_path)[1].lower()
        if file_ext == '.json':
            cookies = json.load(f)
        else:
            content = f.read()
            f.seek(0)

            try:
                cookies = json.loads(content)
            except json.JSONDecodeError:
                cookies = []
                for line in content.splitlines():
                    if line.startswith('#') or not line.strip():
                        continue

                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        domain, flag, path, secure, expiration, name, value = parts[:7]
                        cookie = {
                            'domain': domain,
                            'path': path,
                            'secure': secure.lower() == 'true',
                            'expires': float(expiration) if expiration.isdigit() else None,
                            'name': name,
                            'value': value,
                            'sameSite': 'Lax'
                        }
                        cookies.append(cookie)

    for cookie in cookies:
        if "sameSite" in cookie and cookie["sameSite"] in [
            "unspecified",
            "no_restriction",
        ]:
            cookie["sameSite"] = "Lax"
        elif "sameSite" not in cookie:
            cookie["sameSite"] = "Lax"
        else:
            cookie["sameSite"] = cookie["sameSite"].capitalize()
    co = ChromiumOptions().auto_port()
    if headless:
        co = co.headless()
    if browser_path:
        if "msedge.exe" in browser_path:
            raise ValueError("Microsoft Edge is not supported")
        co = co.set_browser_path(browser_path)
    try:
        driver = ChromiumPage(co)
        driver.get("https://www.bilibili.com")
        driver.set.cookies(cookies)
        driver.get("https://member.bilibili.com/platform/upload/video/frame")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                upload_ele = driver.ele(".bcc-upload-wrapper")
                upload_ele.wait.displayed()
                upload_ele.click.to_upload(video_path)
                driver.wait.load_start()
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"上传失败，正在尝试刷新页面并重试（第{attempt+1}次）")
                    driver.refresh()
                else:
                    raise Exception(f"上传失败，已尝试{max_retries}次：{str(e)}")

        _select_default_creation_statement(driver)
        _try_upload_cover(driver, cover_path)

        title_ele = driver.ele(".video-title").ele(".input-val")
        title_ele.wait.not_covered()
        title_ele.input(title, clear=True)

        tags_ele = driver.ele(".tag-container").ele(".input-val")
        for tag in tags[:10]:
            tags_ele.input(tag + "\n")
            driver.wait(2)

        desc_elem = driver.ele(".archive-info-editor").ele(".ql-editor ql-blank")
        sub_p = desc_elem.ele("tag:p")
        desc_paragraphs = description.split("\n")
        sub_p.set.innerHTML(desc_paragraphs[0])
        if len(desc_paragraphs) > 1:
            for paragraph in desc_paragraphs[1:]:
                p_html = f"<p>{paragraph}</p>"
                driver.add_ele(p_html, desc_elem)

        driver.run_js('document.querySelector(".setting").removeAttribute("style")')
        # driver.ele("未经作者授权 禁止转载").click()

        driver.ele("立即投稿").click()

        upload_confirmed = _wait_for_required_result(
            lambda: driver.wait.eles_loaded("稿件投递成功", timeout=7200),
            "Bilibili did not confirm successful submission before timeout.",
        )
        return upload_confirmed
    except Exception as exc:
        if driver is not None:
            _save_debug_html(driver, f"upload stopped unexpectedly: {exc}")
        _hold_browser_open_after_unexpected_stop(exc)
    finally:
        if upload_confirmed and driver is not None:
            driver.quit()
