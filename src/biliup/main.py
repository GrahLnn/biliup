import json
import os
import time

from DrissionPage import ChromiumOptions, ChromiumPage


class UploadConfirmationError(RuntimeError):
    """Raised when Bilibili upload did not reach the success confirmation state."""


def _wait_for_required_result(wait_call, message):
    result = wait_call()
    if result is False:
        raise UploadConfirmationError(message)
    return result


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

        _wait_for_required_result(
            lambda: driver.wait.eles_loaded("封面设置"),
            "Upload page did not expose cover settings after video upload.",
        )
        driver.ele("封面设置").click()
        driver.ele("上传封面").click.to_upload(cover_path)
        # driver.ele(".bcc-dialog__body").ele(".bcc-upload").click.to_upload(cover_path)
        done_ele = driver.ele(" 完成 ")
        _wait_for_required_result(
            done_ele.wait.displayed,
            "Cover upload dialog did not show the completion button.",
        )
        done_ele.click()
        _wait_for_required_result(
            done_ele.wait.disabled_or_deleted,
            "Cover upload dialog did not close after completion.",
        )

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
        _hold_browser_open_after_unexpected_stop(exc)
    finally:
        if upload_confirmed and driver is not None:
            driver.quit()
