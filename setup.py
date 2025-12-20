"""
安装脚本
"""
from setuptools import setup, find_packages

with open("README_NEW.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="wechat-downloader",
    version="1.0.0",
    author="WeChat Downloader",
    description="简洁的微信公众号文章下载工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/qiye45/wechatDownload",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.31.0",
    ],
    extras_require={
        "clipboard": ["pyperclip>=1.8.2"],
    },
    entry_points={
        "console_scripts": [
            "wechat-downloader=wechat_downloader.main:main",
        ],
    },
)




