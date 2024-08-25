import json

from DrissionPage import ChromiumOptions, ChromiumPage


def update_video(video_path, title, cover_path, tags, description, cookie_path):
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

    with open(cookie_path) as f:
        cookies = json.load(f)
    co = ChromiumOptions().headless()
    driver = ChromiumPage()
    driver.get("https://www.bilibili.com")
    driver.set.cookies(cookies)
    driver.get("https://member.bilibili.com/platform/upload/video/frame")

    upload_ele = driver.ele(".bcc-upload-wrapper")
    upload_ele.wait.displayed()
    upload_ele.click.to_upload(video_path)
    driver.wait.load_start()

    driver.wait.eles_loaded("更改封面")
    driver.ele("更改封面").click()
    driver.ele("上传封面").click()
    driver.ele(".bcc-dialog__body").ele(".bcc-upload").click.to_upload(cover_path)
    driver.ele(" 完成 ").click()

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

    try:
        driver.ele("未经作者授权 禁止转载").click()
    except Exception:
        driver.ele("（含声明与权益、视频元素、互动管理等）").click()
        driver.ele("未经作者授权 禁止转载").click()

    driver.ele("立即投稿").click()

    driver.wait.eles_loaded("稿件投递成功", timeout=3600)
    driver.quit()
