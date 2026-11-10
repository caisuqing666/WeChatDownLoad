"""
把抓下来的真实文章页面裁剪成测试数据：

    python tests/fixtures/trim_page.py 原始页面.html tests/fixtures/real/xxx.html

真实页面约 3.5MB，其中九成以上是与解析无关的内联 JS/CSS。这里只删除不含
解析器所读变量的 <script>/<style> 块，其余字节（包括 #js_content 正文和
元数据脚本）原样保留。
"""
import re
import sys

KEEP_VARS = (
    "biz", "user_name", "nickname", "msg_title", "author", "create_time", "ct",
    "msg_desc", "msg_cdn_url", "msg_source_url", "msg_link", "item_show_type",
)
_BLOCK = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_NEEDED = re.compile(r"\bvar\s+(?:" + "|".join(KEEP_VARS) + r")\s*=")


def trim(page: str) -> str:
    return _BLOCK.sub(lambda m: m.group(0) if _NEEDED.search(m.group(0)) else "", page)


if __name__ == "__main__":
    src, dst = sys.argv[1:3]
    with open(src, encoding="utf-8") as f:
        page = f.read()
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(trim(page))
