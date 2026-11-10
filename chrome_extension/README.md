# 浏览器扩展：公众号文章存为 Markdown

只做一件事：把当前打开的公众号文章保存为 Markdown。安装和使用见仓库根目录的 [README](../README.md#浏览器扩展)。

## 文件

| 文件 | 作用 |
| --- | --- |
| `manifest.json` | 扩展配置（Manifest V3） |
| `popup.html` / `popup.css` / `popup.js` | 弹窗界面和按钮逻辑 |
| `extract.js` | 注入文章页，读取标题、公众号、发布时间和正文 |
| `markdown.js` | 正文 HTML 转 Markdown，生成 front matter 和文件名 |

## 权限

- `activeTab` + `scripting`：只在你点击扩展图标时读取当前标签页。
- `downloads`：保存 Markdown 文件。
- `http://127.0.0.1:4546/*`：「发送到本地命令行」按钮访问本机的 `python -m wechat_downloader.receiver`。

front matter 和文件名与命令行版（`wechat_downloader/render.py`、`downloader.py`）保持一致，由 `tests/extension/parity.test.js` 对样例页面逐字段比较；修改其中一边时请同步另一边。
