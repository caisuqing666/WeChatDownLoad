# 微信公众号文章下载工具（简洁版）

一个简洁、跨平台的微信公众号文章下载工具，使用 Python 实现。

## 特性

- ✅ **简洁易用**: 纯 Python 实现，无需复杂配置
- ✅ **跨平台**: 支持 Windows、macOS、Linux
- ✅ **轻量级**: 仅依赖标准库和少量第三方库
- ✅ **Markdown 导出**: 自动转换为 Markdown 格式，便于阅读和编辑
- ✅ **图片下载**: 自动下载文章中的图片
- ✅ **批量下载**: 支持批量下载公众号历史文章

## 安装

### 1. 安装 Python

确保已安装 Python 3.7 或更高版本：

```bash
python --version
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 获取 Token

1. 在微信中打开任意一篇公众号文章
2. 复制文章链接
3. 在微信内置浏览器中打开链接（发送到文件传输助手，然后点击打开）
4. 打开浏览器开发者工具（F12 或右键 -> 检查）
5. 在 Network 标签中找到请求，从请求头或 Cookie 中获取 `appmsg_token` 或 `pass_ticket`

### 下载单篇文章

```bash
python -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxx" \
  --token "your_token"
```

### 批量下载公众号文章

```bash
python -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxx" \
  --token "your_token" \
  --batch \
  --count 20
```

### 从剪贴板读取 Token

```bash
python -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxx" \
  --token-clipboard
```

### 指定输出目录

```bash
python -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxx" \
  --token "your_token" \
  --output "./my_downloads"
```

## 参数说明

- `--url, -u`: 微信公众号文章链接（必需）
- `--token, -t`: 访问 token（必需，除非使用 --token-clipboard）
- `--token-clipboard`: 从剪贴板读取 token
- `--output, -o`: 输出目录（默认: downloads）
- `--batch, -b`: 启用批量下载模式
- `--count, -c`: 批量下载数量（默认: 10）
- `--offset`: 起始偏移量（默认: 0）

## 输出格式

下载的文章会保存为 Markdown 格式（.md），包含：

- 文章标题
- 作者信息
- 发布时间
- 文章正文（Markdown 格式）
- 图片（保存在单独文件夹中）

文件结构示例：

```
downloads/
└── 公众号名称/
    ├── 文章标题1.md
    ├── 文章标题1_images/
    │   ├── image_1.jpg
    │   └── image_2.jpg
    └── 文章标题2.md
```

## 常见问题

### Q: 如何获取 token？

A: 在微信内置浏览器中打开文章，使用开发者工具查看网络请求，从请求参数中获取 `appmsg_token` 或 `pass_ticket`。

### Q: token 有效期多久？

A: token 通常有时效性，如果下载失败，请重新获取 token。

### Q: 支持哪些格式导出？

A: 目前支持 Markdown 格式。Markdown 可以轻松转换为 HTML、PDF 等其他格式。

### Q: 批量下载失败怎么办？

A: 可能是 token 失效或网络问题。尝试：
1. 重新获取 token
2. 减少批量下载数量（--count）
3. 增加起始偏移量（--offset）跳过已下载的文章

## 技术实现

- **API 模块** (`api.py`): 封装微信公众号 API 调用
- **下载模块** (`downloader.py`): 处理文章下载和格式转换
- **主程序** (`main.py`): 命令行接口

## 注意事项

1. 本工具仅供学习交流使用
2. 请遵守微信公众号的使用条款
3. 不要对服务器造成过大压力
4. 尊重原创作者的版权

## 许可证

本项目基于原项目改进，遵循相同的使用条款。

## 与原版对比

| 特性 | 原版 | 简洁版 |
|------|------|--------|
| 平台 | Windows/macOS 桌面应用 | 跨平台命令行工具 |
| 依赖 | 较大（Electron等） | 轻量（仅 Python） |
| 安装 | 需要下载安装包 | pip install |
| 使用 | GUI 界面 | 命令行 |
| 导出格式 | HTML/MD/PDF/DOCX | Markdown（可转换） |
| 代码量 | 较大 | 简洁 |

## 贡献

欢迎提交 Issue 和 Pull Request！




