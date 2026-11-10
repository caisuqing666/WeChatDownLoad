# WeChatDownLoad

把微信公众号文章保存成 Markdown 的个人小工具，作者 CAI SUQING。

包含两部分：

- **命令行**（`wechat_downloader/`）：单篇、多篇、按链接清单（`--urls`）或整个合集（`--album`）下载为 Markdown，支持断点续传。
- **浏览器扩展**（`chrome_extension/`）：在当前打开的文章页上一键保存，或把链接交给本地命令行下载。

> 这是个人自用项目，按需维护。微信页面随时可能调整，兼容性不做保证。

## 命令行

需要 Python 3.7+。

把公众号文章保存为 Markdown，文件开头是 YAML front matter（title、author、url、date 等）。图片下载到本地，Markdown 里用相对路径引用；加 `--no-images` 则保留微信原始图片链接。

```bash
pip install -r requirements.txt

# 单篇（支持 /s/xxx 短链接，也支持带 &amp; 的长链接）
python -m wechat_downloader.main "https://mp.weixin.qq.com/s/xxx"

# 多篇，默认每篇间隔 2 秒，可用 --interval 调整
python -m wechat_downloader.main URL1 URL2 URL3 -o ~/Documents/公众号
```

输出位置：`<输出目录>/<公众号名称>/<发布日期>_<标题>_<文章ID>.md`，图片在同目录的同名 `.assets/` 文件夹里。文章ID 是由链接（biz+mid+idx，或短链接路径）算出的 8 位标识：同一篇重复下载会覆盖原文件，不同文章即使同名也不会冲突。单张图片下载失败时保留原始链接并提示。

### 按链接清单批量下载（`--urls`）

不登录拿不到某个号的历史文章列表，批量下载需要自己整理链接：

```bash
# links.txt：每行一个链接，空行和 # 开头的行会被忽略，重复的链接只下载一次
python -m wechat_downloader.main --urls links.txt -o ~/Documents/公众号

# 每两篇之间等待 --delay 秒再随机加 0~--jitter 秒（默认 3 + 0~2 秒）
python -m wechat_downloader.main --urls links.txt --delay 5 --jitter 3
```

- 断点续传：进度记在输出目录的 `.wechat_progress.json`（每篇结束后原子写入）。中途 Ctrl+C、断网或遇到验证页后，重新运行同一命令即可，已成功的自动跳过、不再请求。带 `__biz`/`mid` 的长链接即使没有进度文件，也会按文件名里的文章ID 认出已下载的文件。
- 遇到“环境异常”验证页立即停止并提示剩余篇数，稍后再跑同一命令继续。
- 单篇失败（文章已删除、网络错误等）记入进度文件后继续下一篇，结束时汇总列出；下次运行会重试失败的文章。
- 有图片没下载成功的文章记为 `partial`（正文已保存，缺的图保留微信原始链接），汇总里单独列出。下次运行默认重新下载这些文章补齐缺图：这次又失败的图沿用上次的本地文件，已成功的图不会丢；全部补齐后变为 `done`。加 `--no-retry-images` 则把缺图文章当作已下载跳过。按文件名里的文章ID 识别已有文件时，Markdown 里还有远程图片链接的也按缺图处理。
- 用 `--no-images` 下载的文章在进度里标记 `"images_skipped": true`：之后再用 `--no-images` 运行会跳过，不加 `--no-images` 运行时会重新下载并保存图片，完成后标记变为 `false`。旧版进度文件没有这个字段时，按 Markdown 里是否还有远程图片链接判断。
- 全部完整成功退出码为 0；有失败、缺图或因验证页停止为 1；Ctrl+C 为 130。

进度文件格式（键是规范化后的链接）：

```json
{
  "version": 1,
  "articles": {
    "https://mp.weixin.qq.com/s/xxx": {"status": "done", "id": "52a063f7", "path": "某公众号/2024-12-02_标题_52a063f7.md", "title": "标题", "images_skipped": false, "updated_at": "2026-11-10T19:00:00+08:00"},
    "https://mp.weixin.qq.com/s/zzz": {"status": "partial", "id": "1f3c9a20", "path": "某公众号/2024-12-03_标题2_1f3c9a20.md", "title": "标题2", "images_skipped": false, "missing_images": 1, "failed_images": ["https://mmbiz.qpic.cn/..."], "attempts": 1, "updated_at": "2026-11-10T19:00:03+08:00"},
    "https://mp.weixin.qq.com/s/yyy": {"status": "failed", "error": "文章不可用：该内容已被发布者删除", "attempts": 1, "updated_at": "2026-11-10T19:00:05+08:00"}
  }
}
```

### 下载整个公众号合集（`--album`）

公众号文章里的“合集/话题”标签（如 `#李想主义`）点开后，地址形如 `https://mp.weixin.qq.com/mp/appmsgalbum?__biz=...&action=getalbum&album_id=...`。合集列表不登录就能翻页拿到，所以可以一次下载整个合集：

```bash
python -m wechat_downloader.main --album "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzA3MDM3NjE5NQ==&action=getalbum&album_id=1375870284640911361" -o ~/Documents/公众号

# 合集更新后重新获取列表（已下载的文章仍会跳过）
python -m wechat_downloader.main --album "合集链接" -o ~/Documents/公众号 --refresh-album
```

- 先每页 20 篇翻完合集列表，再按 `--urls` 的流程逐篇下载，行为和上面完全一致：
  - 同样用 `--delay`/`--jitter` 限速，翻列表时每次请求至少间隔 3 秒。
  - 进度写在 `.wechat_progress.json`，已下载的自动跳过。
  - 缺图文章记为 `partial`，下次默认重下补齐；加 `--no-retry-images` 则跳过缺图文章。
  - `--no-images` 下载的有图文章标记 `images_skipped`，之后不加 `--no-images` 运行会补下图片（合集列表仍用缓存）。
  - 汇总和退出码规则相同：有失败、缺图或验证页停止时退出码为 1。
- 列表缓存在输出目录的 `.wechat_album_<album_id>.json`，每翻一页写一次。只有接口返回 `continue_flag=0` 才算翻完，之后再运行同一命令直接使用缓存，不会重新翻页；翻到一半被打断（包括遇到验证页）时，下次从断点接着翻。旧版本程序写的缓存无法确认是否翻完，会从头重新翻（已下载的文章仍跳过）。
- 接口说还有下一页（`continue_flag=1`）却没有返回新文章（空列表或整页重复），或返回里缺 `getalbum_resp`、`continue_flag` 缺失或不是 0/1 时，该页整页不收、游标不动，按 6、12 秒（`--delay` 更大时按比例加长）退避重试 2 次，仍然没有就停止，列表按未完成保存，稍后重新运行同一命令从断点接着翻。
- 合集接口返回的不是 JSON（一般是“环境异常”验证页）时立即停止，提示稍后再跑；返回 `ret=10004` 表示 album_id 错误或合集不存在，其他非 0 的 `ret` 会原样报出。

### 在 Python 代码里调用

```python
from wechat_downloader.batch import download_url_list, read_url_file
from wechat_downloader.downloader import ArticleDownloader

downloader = ArticleDownloader(output_dir="downloads")
urls = read_url_file("links.txt")  # 与 --urls 相同：忽略空行和 # 注释，自动去重
result = download_url_list(downloader, urls, delay=3, jitter=2)
print(f"新下载 {result.downloaded} 篇，跳过 {result.skipped} 篇，失败 {len(result.failed)} 篇，缺图 {len(result.partial)} 篇")
```

### 注意事项

遇到“环境异常”验证页时程序会停止后续请求；稍等一段时间，或在浏览器里打开该链接完成验证后再试。长链接缺少 `chksm` 等参数时微信可能返回“未知错误”页，请复制完整链接或改用 /s/ 短链接。图片/视频分享类消息暂不支持。

## 浏览器扩展

适用于 Chrome / Edge 等 Chromium 浏览器。

1. 打开 `chrome://extensions/`，开启右上角「开发者模式」。
2. 点「加载已解压的扩展程序」，选择本仓库的 `chrome_extension` 文件夹。
3. 打开一篇公众号文章，点工具栏里的扩展图标：
   - **保存为 Markdown**：直接用当前页面内容生成，保存到 `下载/公众号/<公众号名称>/<发布日期>_<标题>.md`。图片保留微信原始链接，不下载到本地；需要本地图片时用下面的按钮交给命令行。
   - **发送到本地命令行**：把当前链接交给本机的命令行下载，适合想统一存到某个目录的情况。需要先启动接收服务：

     ```bash
     python -m wechat_downloader.receiver -o ~/Documents/公众号
     ```

     服务只监听 `127.0.0.1:4546`，只接受浏览器扩展发来的 `mp.weixin.qq.com/s` 文章链接，收到后逐篇排队下载，进度显示在终端里。

## 开发

```bash
pip install -r requirements.txt pytest
python -m pytest tests
```

`tests/fixtures/real/` 是真实抓取的文章页面（用 `tests/fixtures/trim_page.py` 去掉了无关的内联 JS/CSS），解析逻辑可以离线测试。`tests/fixtures/album/` 是真实的合集接口响应（看理想 96 篇完整 6 页、RWKV 31 篇、津房字的次条文章游标、空列表和 ret=10004）。

浏览器扩展的 Markdown 转换有单独的 Node 测试（需要 Node 18+）：

```bash
cd tests/extension && npm install && npm test
```

## 来源

本仓库最初基于 [qiye45/wechatDownload](https://github.com/qiye45/wechatDownload) 的思路，现已重写为只做 Markdown 导出的命令行和浏览器扩展，与原项目的桌面软件无关。

## 免责声明

仅供个人学习、存档使用。文章版权归原作者所有，请勿用于转载或其他商业用途。
