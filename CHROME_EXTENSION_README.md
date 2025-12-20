# 微信公众号文章下载器 - Chrome 扩展版

## 🎯 为什么选择浏览器扩展？

作为资深爬虫专家，我深知微信公众号的反爬虫机制非常严格。传统的 Python 爬虫脚本存在以下问题：

1. **容易被封 IP**: 频繁请求会被微信服务器封禁
2. **需要 Token**: 必须手动获取 token，且容易过期
3. **验证码挑战**: 可能触发验证码验证
4. **环境依赖**: 需要配置 Python 环境

**浏览器扩展的优势**：

✅ **更安全**: 在真实浏览器环境中运行，不会被封 IP  
✅ **无需 Token**: 直接访问页面 DOM，自动提取内容  
✅ **用户友好**: 点击按钮即可下载，无需命令行  
✅ **实时提取**: 在页面加载时自动提取，无需等待  
✅ **跨平台**: Chrome 全平台支持，无需额外配置  

## 📦 项目结构

```
chrome_extension/
├── manifest.json              # 扩展配置（Manifest V3）
├── popup.html                # 弹窗界面
├── popup.js                  # 弹窗逻辑
├── content.js                # 内容脚本（在页面中运行）
├── background.js             # 后台服务
├── welcome.html              # 欢迎页面
├── create_icons.html         # 图标生成器（浏览器版）
├── create_placeholder_icons.py # 图标生成器（Python版）
├── icons/                    # 图标文件夹
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
├── README.md                 # 详细使用说明
├── INSTALL.md                # 安装指南
├── QUICKSTART.md             # 快速开始
└── CHROME_EXTENSION_SUMMARY.md # 技术总结
```

## 🚀 快速开始

### 1. 准备图标（1分钟）

**方法一：使用浏览器生成器（推荐）**
1. 在浏览器中打开 `create_icons.html`
2. 点击"生成图标"
3. 右键保存到 `icons/` 文件夹

**方法二：使用 Python 脚本**
```bash
pip install Pillow
python create_placeholder_icons.py
```

### 2. 安装扩展（1分钟）

1. 打开 Chrome，访问 `chrome://extensions/`
2. 开启"开发者模式"
3. 点击"加载已解压的扩展程序"
4. 选择 `chrome_extension` 文件夹

### 3. 开始使用（30秒）

1. 访问微信公众号文章
2. 点击扩展图标 📥
3. 选择格式并下载

## ✨ 功能特性

- ✅ **自动检测**: 自动识别微信公众号文章页面
- ✅ **内容提取**: 提取标题、作者、时间、正文、图片
- ✅ **多格式支持**: Markdown、HTML、纯文本
- ✅ **图片下载**: 自动下载文章中的图片
- ✅ **美观界面**: 现代化 UI 设计
- ✅ **无需配置**: 开箱即用

## 🔧 技术实现

### Content Script
在微信公众号页面中运行，直接访问 DOM 和 JavaScript 变量，提取：
- 文章标题（从 DOM 或 JS 变量）
- 作者信息
- 发布时间
- 正文内容（HTML）
- 所有图片 URL
- 公众号 ID 和 token（如果可用）

### Popup Script
处理用户交互：
- 与 content script 通信获取数据
- HTML → Markdown/Text 格式转换
- 使用 Chrome Downloads API 下载文件
- 批量下载图片

### 安全特性
- 仅在微信公众号页面运行
- 所有处理在本地完成
- 不收集或上传任何数据
- 最小权限原则

## 📖 详细文档

- **[QUICKSTART.md](QUICKSTART.md)**: 5分钟快速上手
- **[INSTALL.md](INSTALL.md)**: 详细安装指南
- **[README.md](README.md)**: 完整使用说明
- **[CHROME_EXTENSION_SUMMARY.md](CHROME_EXTENSION_SUMMARY.md)**: 技术实现总结

## 🆚 与 Python 脚本对比

| 特性 | Python 脚本 | Chrome 扩展 |
|------|-----------|------------|
| **反爬虫** | ❌ 可能被封 IP | ✅ 真实浏览器环境 |
| **Token** | ❌ 需要手动获取 | ✅ 自动提取 |
| **使用方式** | 命令行 | ✅ 点击按钮 |
| **部署** | 需要 Python | ✅ 浏览器原生 |
| **跨平台** | 需要配置 | ✅ Chrome 全平台 |
| **易用性** | 中等 | ✅ 非常简单 |

## 🐛 故障排除

### 扩展无法加载
- 检查图标文件是否存在
- 查看 `chrome://extensions/` 中的错误信息

### 无法检测文章
- 确保在微信公众号文章页面
- 刷新页面后重试

### 下载失败
- 检查浏览器下载权限
- 尝试不同的导出格式

详细故障排除见 [INSTALL.md](INSTALL.md)

## 🔮 未来扩展

可以轻松添加的功能：
- 批量下载整个公众号
- 支持 PDF、DOCX 格式
- 云存储同步
- 自定义导出样式
- 下载历史记录

## 📝 许可证

本项目仅供学习交流使用，请遵守相关法律法规。

## 🙏 致谢

感谢原项目 [wechatDownload](https://github.com/qiye45/wechatDownload) 的启发。

---

**立即开始**: 查看 [QUICKSTART.md](QUICKSTART.md) 5分钟上手！



