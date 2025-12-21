# 快速开始指南

## 5分钟快速上手

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Token

**方法一：从微信浏览器获取**

1. 在微信中打开任意一篇公众号文章
2. 复制文章链接，发送到"文件传输助手"
3. 在微信中点击链接打开（必须在微信内置浏览器中打开）
4. 按 F12 打开开发者工具（或右键 -> 检查）
5. 在 Network 标签中，找到任意一个请求
6. 查看请求参数，找到 `appmsg_token` 或 `pass_ticket`，这就是 token

**方法二：使用浏览器扩展**

某些浏览器扩展可以自动提取 token，但需要手动配置。

### 3. 下载单篇文章

```bash
python -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxx" \
  --token "你的token"
```

### 4. 批量下载

```bash
python -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxx" \
  --token "你的token" \
  --batch \
  --count 20
```

## 使用交互式脚本

如果不想使用命令行参数，可以使用交互式脚本：

```bash
python example_usage.py
```

然后按照提示操作即可。

## 常见问题快速解决

### Q: 提示"需要提供token"

A: 批量下载需要 token。单篇文章下载可以不提供 token，但功能会受限。

### Q: 下载失败

A: 检查：
1. Token 是否有效（可能已过期）
2. 网络连接是否正常
3. URL 是否正确

### Q: 找不到模块

A: 确保在项目根目录运行，或使用：
```bash
python -m wechat_downloader.main
```

## 输出文件位置

默认保存在 `downloads/` 目录下，结构如下：

```
downloads/
└── 公众号名称/
    ├── 文章标题.md
    └── 文章标题_images/
        └── image_1.jpg
```

## 下一步

- 查看 [README_NEW.md](README_NEW.md) 了解详细功能
- 查看 [example_usage.py](example_usage.py) 了解代码示例





