# Python 版本运行指南

## 📋 运行前准备

### 1. 确认 Python 环境

```bash
# 检查 Python 版本（需要 3.7+）
python3 --version

# 或
python --version
```

### 2. 安装依赖（如果还没安装）

```bash
# 进入项目目录
cd ~/Documents/GitHub/wechatDownload

# 安装依赖
pip3 install -r requirements.txt

# 或使用 pip
pip install -r requirements.txt
```

### 3. 验证安装

```bash
# 运行测试脚本
python3 test_basic.py
```

如果所有测试通过，说明环境配置正确。

## 🚀 如何运行

### 方法一：交互式脚本（推荐新手）

这是最简单的方式，会引导您完成操作：

```bash
# 进入项目目录
cd ~/Documents/GitHub/wechatDownload

# 运行交互式脚本
python3 example_usage.py
```

然后按照提示：
1. 选择功能（单篇下载 或 批量下载）
2. 输入文章 URL
3. 输入 token（如果需要）
4. 等待下载完成

### 方法二：命令行方式

#### 下载单篇文章

```bash
cd ~/Documents/GitHub/wechatDownload

python3 -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxxxx" \
  --token "your_token"
```

#### 批量下载

```bash
python3 -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxxxx" \
  --token "your_token" \
  --batch \
  --count 20
```

#### 从剪贴板读取 token

```bash
python3 -m wechat_downloader.main \
  --url "https://mp.weixin.qq.com/s/xxxxx" \
  --token-clipboard
```

## 📍 在哪里运行

### 在终端（Terminal）中运行

1. **打开终端**
   - 按 `Cmd + Space` 搜索 "Terminal"
   - 或打开"应用程序" → "实用工具" → "终端"

2. **进入项目目录**
   ```bash
   cd ~/Documents/GitHub/wechatDownload
   ```

3. **运行脚本**
   ```bash
   python3 example_usage.py
   ```

### 在 VS Code 中运行

1. 打开项目文件夹
2. 打开 `example_usage.py` 文件
3. 点击右上角的运行按钮 ▶️
4. 或在终端中运行命令

## 🔑 获取 Token（重要）

批量下载需要 token。获取方法：

### 方法一：从微信浏览器获取

1. 在微信中打开任意一篇公众号文章
2. 复制文章链接
3. 在微信内置浏览器中打开（发送到文件传输助手，然后点击）
4. 按 `F12` 打开开发者工具
5. 在 Network 标签中，找到任意请求
6. 查看请求参数，找到 `appmsg_token` 或 `pass_ticket`

### 方法二：单篇下载不需要 token

如果只是下载单篇文章，可以不提供 token，但功能会受限。

## 📂 输出位置

下载的文件保存在：

```
~/Documents/GitHub/wechatDownload/downloads/
└── 公众号名称/
    ├── 文章标题.md
    └── 文章标题_images/
        └── image_1.jpg
```

## ⚠️ 常见问题

### Q: 提示 "No module named 'requests'"

**解决：**
```bash
pip3 install -r requirements.txt
```

### Q: 提示 "找不到模块 wechat_downloader"

**解决：**
确保在项目根目录运行：
```bash
cd ~/Documents/GitHub/wechatDownload
python3 example_usage.py
```

### Q: 单篇下载可以，批量下载失败

**解决：**
- 检查 token 是否有效（可能已过期）
- 重新获取 token
- 减少批量下载数量（--count 10）

### Q: 下载的文件在哪里？

**解决：**
- 默认在 `downloads/` 文件夹
- 可以在 Finder 中打开项目目录查看

## 🎯 快速测试

### 测试 1: 基础功能

```bash
cd ~/Documents/GitHub/wechatDownload
python3 test_basic.py
```

### 测试 2: 单篇下载（不需要 token）

```bash
python3 example_usage.py
# 选择 1（单篇下载）
# 输入文章 URL
# token 留空（按 Enter）
```

### 测试 3: 批量下载（需要 token）

```bash
python3 example_usage.py
# 选择 2（批量下载）
# 输入文章 URL
# 输入 token
# 输入下载数量
```

## 📝 完整示例

```bash
# 1. 打开终端
# 2. 进入项目目录
cd ~/Documents/GitHub/wechatDownload

# 3. 运行交互式脚本
python3 example_usage.py

# 4. 按照提示操作：
#    - 选择功能（1 或 2）
#    - 输入文章 URL
#    - 输入 token（批量下载需要）
#    - 等待完成

# 5. 查看下载的文件
open downloads/
```

## 🔄 与 Chrome 扩展对比

| 特性 | Python 版本 | Chrome 扩展 |
|------|------------|------------|
| **使用方式** | 命令行/终端 | 浏览器点击 |
| **需要 token** | 批量下载需要 | 不需要 |
| **易用性** | 中等 | 简单 |
| **批量下载** | 支持 | 支持 |
| **跨平台** | ✅ 全平台 | ✅ Chrome |

## 💡 提示

- **首次使用**：建议先用交互式脚本（`example_usage.py`）
- **批量下载**：需要 token，建议每次下载 10-20 篇
- **单篇下载**：不需要 token，可以直接使用
- **查看文件**：下载的文件在 `downloads/` 文件夹中

