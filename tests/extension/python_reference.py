"""
给扩展的一致性测试输出命令行版的结果：python python_reference.py <页面文件> <请求链接>
输出 JSON：front matter 字段（不含 downloaded_at）和文件名主干
"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wechat_downloader.downloader import ArticleDownloader  # noqa: E402
from wechat_downloader.parse import parse_article  # noqa: E402
from wechat_downloader.render import front_matter  # noqa: E402


def main() -> None:
    page_path, url = sys.argv[1], sys.argv[2]
    article = parse_article(Path(page_path).read_text(encoding="utf-8"), url)
    fields = yaml.load(front_matter(article).strip().strip("-"), Loader=yaml.BaseLoader)
    fields.pop("downloaded_at", None)
    json.dump({
        "fields": fields,
        "stem": ArticleDownloader(output_dir="unused").article_stem(article),
        "account": article.account_name,
    }, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
