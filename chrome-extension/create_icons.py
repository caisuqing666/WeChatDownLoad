#!/usr/bin/env python3
"""
快速创建扩展图标
需要安装 Pillow: pip install Pillow
"""
try:
    from PIL import Image, ImageDraw, ImageFont
    import os
except ImportError:
    print("需要安装 Pillow: pip install Pillow")
    exit(1)

def create_icon(size, filename):
    """创建图标"""
    # 创建渐变背景
    img = Image.new('RGB', (size, size), color='#667eea')
    draw = ImageDraw.Draw(img)
    
    # 绘制圆形背景
    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill='#764ba2',
        outline='#667eea',
        width=2
    )
    
    # 添加文字（如果尺寸足够大）
    if size >= 48:
        try:
            # 尝试使用系统字体
            font_size = size // 3
            font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", font_size)
            text = "📰"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((size - text_width) // 2, (size - text_height) // 2)
            draw.text(position, text, font=font, fill='white')
        except:
            # 如果字体加载失败，使用默认字体
            font_size = size // 2
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
            text = "W"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((size - text_width) // 2, (size - text_height) // 2)
            draw.text(position, text, font=font, fill='white')
    
    # 保存
    img.save(filename, 'PNG')
    print(f"✓ 创建图标: {filename} ({size}x{size})")

def main():
    """主函数"""
    icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
    os.makedirs(icons_dir, exist_ok=True)
    
    print("正在创建图标...")
    create_icon(16, os.path.join(icons_dir, 'icon16.png'))
    create_icon(48, os.path.join(icons_dir, 'icon48.png'))
    create_icon(128, os.path.join(icons_dir, 'icon128.png'))
    print("\n完成！图标已保存到 icons/ 文件夹")

if __name__ == '__main__':
    main()

