#!/usr/bin/env python3
"""
创建占位图标
如果无法使用在线工具，可以运行此脚本生成简单的占位图标
需要安装 Pillow: pip install Pillow
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    """创建图标"""
    # 创建图像
    img = Image.new('RGB', (size, size), color='#667eea')
    draw = ImageDraw.Draw(img)
    
    # 绘制渐变效果（简化版）
    for i in range(size):
        alpha = int(255 * (1 - i / size))
        color = (102, 126, 234) if i < size // 2 else (118, 75, 162)
        draw.line([(0, i), (size, i)], fill=color)
    
    # 绘制下载箭头
    center = size // 2
    arrow_size = size // 3
    
    # 绘制向下的箭头
    points = [
        (center, center - arrow_size // 2),  # 上
        (center - arrow_size // 2, center),  # 左
        (center, center + arrow_size // 2),  # 下
        (center + arrow_size // 2, center),  # 右
    ]
    draw.polygon(points, fill='white')
    
    # 保存
    img.save(output_path, 'PNG')
    print(f"✓ 已创建: {output_path}")

def main():
    """主函数"""
    icons_dir = 'icons'
    os.makedirs(icons_dir, exist_ok=True)
    
    sizes = [16, 48, 128]
    
    try:
        for size in sizes:
            output_path = os.path.join(icons_dir, f'icon{size}.png')
            create_icon(size, output_path)
        
        print("\n✓ 所有图标创建完成！")
        print("图标保存在 icons/ 文件夹中")
    except ImportError:
        print("错误: 需要安装 Pillow 库")
        print("运行: pip install Pillow")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == '__main__':
    main()




