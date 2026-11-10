> **本项目已停止维护**
>
> - 单篇下载仍可能使用，但兼容性不再保证。
> - 历史批量下载功能已不可靠，不再维护。
> - 有需要的用户可自行评估其他持续维护的微信文章转 Markdown 工具。
>
> ---

## Python 命令行版：下载文章为 Markdown

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
- 全部完整成功退出码为 0；有失败、缺图或因验证页停止为 1；Ctrl+C 为 130。

进度文件格式（键是规范化后的链接）：

```json
{
  "version": 1,
  "articles": {
    "https://mp.weixin.qq.com/s/xxx": {"status": "done", "id": "52a063f7", "path": "某公众号/2024-12-02_标题_52a063f7.md", "title": "标题", "updated_at": "2026-11-10T19:00:00+08:00"},
    "https://mp.weixin.qq.com/s/zzz": {"status": "partial", "id": "1f3c9a20", "path": "某公众号/2024-12-03_标题2_1f3c9a20.md", "title": "标题2", "missing_images": 1, "failed_images": ["https://mmbiz.qpic.cn/..."], "attempts": 1, "updated_at": "2026-11-10T19:00:03+08:00"},
    "https://mp.weixin.qq.com/s/yyy": {"status": "failed", "error": "文章不可用：该内容已被发布者删除", "attempts": 1, "updated_at": "2026-11-10T19:00:05+08:00"}
  }
}
```

### 注意事项

遇到“环境异常”验证页时程序会停止后续请求；稍等一段时间，或在浏览器里打开该链接完成验证后再试。长链接缺少 `chksm` 等参数时微信可能返回“未知错误”页，请复制完整链接或改用 /s/ 短链接。图片/视频分享类消息暂不支持。

运行测试：`pip install pytest && python -m pytest tests`。`tests/fixtures/real/` 是真实抓取的文章页面（用 `tests/fixtures/trim_page.py` 去掉了无关的内联 JS/CSS），解析逻辑可以离线测试。

# 微信公众号文章批量下载工具

一款可以批量下载微信公众号文章内容的小工具，无需安装证书，支持Window、MacOS

支持下载微信公众号的历史消息，可以保存文章为html/mhtml/md/pdf/docx文件，支持评论、合集下载，保存文章内图片、视频、音频文件

<img width="1254" height="892" alt="image" src="https://github.com/user-attachments/assets/a8e74f9c-8f02-48dd-a444-43c066f9a048" />
4.0更新 支持图片下载、日志记录；修复文章中视频下载失败、图文下载失败、自定义时间的问题

下载链接：https://pan.quark.cn/s/09bdfa78d09b

**macOS 用户注意**：如果在 macOS 上无法打开应用程序，请查看 [macOS 安装指南](MACOS_INSTALL.md) 或运行修复脚本：
```bash
./fix_macos_app.sh
```

欢迎关注公众号：长风的储物柜，获取最新更新消息🥳

![微信公众号](https://github.com/user-attachments/assets/584c65c4-da1c-4e31-bd92-b18e3589483d)

聊天群：https://t.me/changfengbox

# 使用教程：
1.打开想要下载的公众号里面的随便一篇文章，复制链接到软件中，点击获取公众号id
![image](https://github.com/user-attachments/assets/9e8d05ea-0c23-4ac0-b337-c2e0958dbe8e)
![image](https://github.com/user-attachments/assets/62faabee-9d93-4e0d-a4c7-5d045d47b791)


2.在微信打开刚刚复制的链接（把自动复制好的链接，发到微信的文件传输助手，再点击打开），等待一会，软件会自动获取秘钥
![image](https://github.com/user-attachments/assets/5120f2ba-1049-4381-9c48-81d89c88a7c2)

3.然后就可以下载公众号的文章啦

![image](https://github.com/user-attachments/assets/6c461c86-0cd6-4f5c-8c19-c6770e5e9cee)
![image](https://github.com/qiye45/wechatDownload/assets/138199658/f5e95a6d-a22d-4bc0-980f-f0e91644145e)

注意事项：需要用微信内置浏览器打开复制的链接

![image](https://github.com/qiye45/wechatDownload/assets/138199658/bca604e8-d756-4971-aa6d-8b0c8cf88753)

# 免责声明

- **本软件提供的所有内容，仅可用作学习交流使用，禁止用于其他用途。请在下载24小时内删除。为尊重作者版权，请前往资源的原始发布网站观看，支持原创，谢谢。**


# 更新日志：

3.9更新 修复批量下载失败的问题；优化Markdown排版；导出公众号数据中，Excel增加公众号名称列表

3.8更新 支持可选下载封面/音频/视频；支持下载纯文字文章；修复多篇文章时，只能下载第一篇的问题；修复合集下载失败的问题

3.7更新 支持微信4.0测试版；修复部分合集下载失败的问题；修复自定义时间范围下载的问题

3.6更新 支持微信4.0测试版本；支持只下载原创文章；修复部分合集下载失败的问题；适配黑暗模式；文件开头添加日期增加分隔符

3.5更新：修复获取公众号id失败、下载失败的问题；支持下载公众号合集（专栏）[#148](https://github.com/qiye45/wechatDownload/issues/148)；添加开始下载页数提示

3.4更新 添加暂停下载功能、添加开始下载页数小于0，会重新下载（填-1）、修复获取阅读量失败的问题

3.3更新 下载的封面视频音频支持添加日期前缀，修复评论和评论回复下载失败的问题、导出表格功能标题被截断的问题

3.2更新 修复获取秘钥、公众号id失败、自定义时长闪退的问题；提示前面加上当前时间

3.1更新 修复获取秘钥失败问题 [#161](https://github.com/qiye45/wechatDownload/issues/161)

3.0更新 优化文章排版 [#134](https://github.com/qiye45/wechatDownload/issues/134) ；支持翻页到指定日期范围，手动调整页数；支持mhtml下载；修复闪退问题

2.7更新 支持下载评论回复，自动保存设置的选项，跳过已下载的文章；修复剪切板监听失败的问题

2.6更新 修复下载空白的问题 https://github.com/qiye45/wechatDownload/issues/111 ，支持图文格式下载，支持以公众号文章标题命名视频、音频和封面啦

2.5 支持了Macos版本🥳；支持表格的实时导出；修复数据采集缺失的问题；修复下载一些公众号失败、导出表格的数据不完整的问题；支持多篇文章下载

2.4 支持下载视频、音频、封面图；修复微信文章下载失败的问题#58；添加自动监听剪切板功能，方便下载；添加下载失败的提示，修复无限出现暂停的提示

2.3更新：支持阅读量，点赞数，分享数，评论数的数据导出；文章会下载到以公众号名称的目录下；支持按照阅读量下载，支持其他链接导出Word、PDF、MD格式；下载md格式时，去掉结尾一些无关信息

2.2更新，支持暂停下载，支持按时间段下载，支持下载多篇推文的情况，支持导出公众号文章到表格，优化markdown的下载，支持markdown显示图片，修复下载闪退的问题

2.1更新：支持下载评论，支持调整间隔时间，添加了快捷打开下载目录功能，修复下载失败时暂停的问题

2.0更新：支持下载word、pdf文件
![image](https://github.com/qiye45/wechatDownload/assets/138199658/82934da3-ca55-4440-9f0d-3c8ba0a2106a)

1.1版本更新：支持下载图片，支持单篇微信文章下载，无需手动获取秘钥（微信打开文章时，能自动抓取秘钥）
