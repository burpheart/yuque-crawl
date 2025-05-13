# BY @burpheart
# https://www.yuque.com/burpheart/phpaudit
# https://github.com/burpheart
#
# ⚠️  已按如下需求做了增强：
#   1. 抓取到的 Markdown 中的所有远程图片将被下载到本地 images 子目录，
#      文件名为随机 UUID（保留原扩展名，默认 .png）。
#   2. Markdown 内对应图片链接自动改写为本地相对路径。
#   3. 下载失败最多重试 3 次；仍失败则回退为远程 URL。
#   4. 不修改原有业务逻辑，其余功能保持不变。

import sys
import os
import re
import json
import uuid
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Tuple, List

import requests
from requests import Response, exceptions as req_exc

# ---------- 通用配置 ----------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 10                 # 单次请求超时
RETRY = 3                    # 图片下载最大重试次数
SLEEP_BETWEEN_RETRY = 1      # 重试间隔（秒）

# ---------- 辅助函数 ----------


def _retry_get(url: str, max_retry: int = RETRY, **kwargs) -> Tuple[bool, Response]:
    """
    带重试的 GET 请求。
    返回 (success, response)
    """
    for attempt in range(1, max_retry + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
            if resp.status_code == 200:
                return True, resp
            else:
                print(f"[WARN] 下载失败（HTTP {resp.status_code}），第 {attempt}/{max_retry} 次重试：{url}")
        except req_exc.RequestException as e:
            print(f"[WARN] 下载异常 {e}，第 {attempt}/{max_retry} 次重试：{url}")
        time.sleep(SLEEP_BETWEEN_RETRY)
    return False, None


def _ensure_dir(path: Path) -> None:
    """确保目录存在。"""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def _save_binary(resp: Response, dest: Path) -> None:
    """保存二进制文件。"""
    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def _extract_images(md: str) -> List[Tuple[str, str]]:
    """
    提取 markdown 中的图片 (alt, url) 列表。
    支持普通 markdown 语法 ![alt](url) 以及行内 <img src="url">。
    """
    pattern_md = re.compile(r'!\[([^\]]*)\]\((https?[^)]+)\)', re.IGNORECASE)
    pattern_html = re.compile(r'<img[^>]*?src=["\'](https?[^"\']+)["\']', re.IGNORECASE)

    images = pattern_md.findall(md)
    images += [('', m) for m in pattern_html.findall(md)]
    return images


def _local_filename(url: str) -> str:
    """生成本地文件名（uuid+原扩展名，默认为 .png）。"""
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if not suffix or len(suffix) > 6:  # 粗暴过滤异常后缀
        suffix = ".png"
    return f"{uuid.uuid4().hex}{suffix}"


# ---------- 业务函数 ----------


def save_page(book_id: str, slug: str, md_path: str) -> None:
    """
    下载单篇文档并保存为 markdown。
    同时将其中的远程图片下载到本地，并替换为本地链接。
    """
    url = f"https://www.yuque.com/api/docs/{slug}?book_id={book_id}&merge_dynamic_data=false&mode=markdown"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"[ERROR] 文档下载失败（状态码 {resp.status_code}），可能已删除：{book_id} {slug}")
            return
        doc_json = resp.json()
        md_content = doc_json["data"]["sourcecode"]
    except (req_exc.RequestException, KeyError, json.JSONDecodeError) as e:
        print(f"[ERROR] 文档解析失败：{e} | {book_id} {slug}")
        return

    # 处理图片
    images_dir = Path(md_path).parent / "images"
    images_map: Dict[str, str] = {}  # 远程 url -> 本地相对路径

    for alt, img_url in _extract_images(md_content):
        if img_url in images_map:
            continue  # 已处理过

        local_name = _local_filename(img_url)
        local_rel_path = f"images/{local_name}"
        local_abs_path = images_dir / local_name
        _ensure_dir(images_dir)

        success, img_resp = _retry_get(img_url, RETRY)
        if success:
            try:
                _save_binary(img_resp, local_abs_path)
                images_map[img_url] = local_rel_path
                print(f"[INFO] 图片已保存：{local_rel_path}")
            except Exception as e:
                # 保存失败回退
                print(f"[WARN] 图片保存失败 {e}，回退远程链接：{img_url}")
                images_map[img_url] = img_url
        else:
            images_map[img_url] = img_url  # 下载失败回退

    # 替换 markdown 中的链接
    for remote, local in images_map.items():
        md_content = md_content.replace(remote, local)

    # 写入文件
    Path(md_path).parent.mkdir(parents=True, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f_md:
        f_md.write(md_content)
    print(f"[INFO] 文档已保存：{md_path}")


def get_book(book_url: str = "https://www.yuque.com/burpheart/phpaudit") -> None:
    """
    抓取整本语雀知识库。
    """
    try:
        resp = requests.get(book_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except req_exc.RequestException as e:
        print(f"[ERROR] 获取知识库失败：{e}")
        return

    # 提取嵌入页面的 JSON 数据
    matches = re.findall(r'decodeURIComponent\(\"(.+)\"\)\);', resp.text)
    if not matches:
        print("[ERROR] 未找到知识库数据")
        return
    try:
        docs_json = json.loads(urllib.parse.unquote(matches[0]))
    except json.JSONDecodeError as e:
        print(f"[ERROR] 解析知识库 JSON 失败：{e}")
        return

    book_id = str(docs_json["book"]["id"])
    book_root = Path("download") / book_id
    _ensure_dir(book_root)

    toc = docs_json["book"]["toc"]
    uuid_title_parent: Dict[str, Tuple[str, str]] = {
        d["uuid"]: (d["title"], d["parent_uuid"]) for d in toc
    }
    resolved_paths: Dict[str, str] = {}  # uuid -> 相对路径

    # 构造层级路径
    trans_table = str.maketrans('\/:*?"<>|' + "\n\r", "___________")

    def resolve_path(u: str) -> str:
        if u in resolved_paths:
            return resolved_paths[u]
        title, parent = uuid_title_parent[u]
        safe_title = title.translate(trans_table)
        if not parent:
            path_ = safe_title
        else:
            path_ = f"{resolve_path(parent)}/{safe_title}"
        resolved_paths[u] = path_
        return path_

    # 生成 SUMMARY.md 并抓取各 md
    summary_lines: List[str] = []

    for item in toc:
        path_rel = resolve_path(item["uuid"])
        abs_dir = book_root / path_rel
        is_dir = item["type"] == "TITLE" or item.get("child_uuid") != ""

        if is_dir:
            _ensure_dir(abs_dir)
            header_level = path_rel.count("/") + 2  # 从 ## 开始
            summary_lines.append("#" * header_level + f" {path_rel.split('/')[-1]}")
        if item.get("url"):
            md_filename = f"{path_rel}.md"
            summary_indent = "  " * path_rel.count("/")
            summary_lines.append(f"{summary_indent}* [{item['title']}]({urllib.parse.quote(md_filename)})")
            save_page(book_id, item["url"], str(book_root / f"{md_filename}"))

    # 写入 SUMMARY.md
    with open(book_root / "SUMMARY.md", "w", encoding="utf-8") as f_sum:
        f_sum.write("\n".join(summary_lines))
    print(f"[INFO] SUMMARY.md 已生成：{book_root / 'SUMMARY.md'}")


# ---------- 入口 ----------
if __name__ == "__main__":
    if len(sys.argv) > 1:
        get_book(sys.argv[1])
    else:
        get_book()
