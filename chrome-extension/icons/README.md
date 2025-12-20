# 图标文件说明

## 需要的图标文件

请在此文件夹中放置以下图标文件：

- `icon16.png` - 16x16 像素
- `icon48.png` - 48x48 像素
- `icon128.png` - 128x128 像素

## 快速创建图标

### 方法 1: 使用在线工具

1. 访问 https://www.favicon-generator.org/
2. 上传图片或使用文本生成
3. 下载不同尺寸的图标
4. 重命名并放到此文件夹

### 方法 2: 使用 ImageMagick（如果已安装）

```bash
# 创建简单图标
convert -size 128x128 xc:#667eea -pointsize 60 -fill white -gravity center -annotate +0+0 "📰" icon128.png
convert -size 48x48 xc:#667eea -pointsize 30 -fill white -gravity center -annotate +0+0 "📰" icon48.png
convert -size 16x16 xc:#667eea -pointsize 10 -fill white -gravity center -annotate +0+0 "📰" icon16.png
```

### 方法 3: 使用 Python（需要 Pillow）

```python
from PIL import Image, ImageDraw, ImageFont

def create_icon(size, filename):
    img = Image.new('RGB', (size, size), color='#667eea')
    draw = ImageDraw.Draw(img)
    # 可以添加文字或图标
    img.save(filename)

create_icon(128, 'icon128.png')
create_icon(48, 'icon48.png')
create_icon(16, 'icon16.png')
```

### 方法 4: 使用设计工具

使用 Photoshop、GIMP、Figma 等工具创建图标。

## 临时方案

如果没有图标文件，扩展仍然可以工作，只是会显示 Chrome 的默认图标。

功能不受影响！

