from setuptools import setup, find_packages

setup(
    name="social-scraper-cli",
    version="1.0.0",
    description="Universal Terminal CLI Scraper for YouTube, Reddit, and Instagram",
    author="Piyush Bisht",
    packages=find_packages(),
    install_requires=[
        "rich>=13.0.0",
        "requests>=2.28.0",
        "curl_cffi>=0.7.0",
        "openpyxl>=3.1.0",
        "pandas>=2.0.0",
        "pyyaml>=6.0.0",
        "emoji>=2.10.0",
        "youtube-comment-downloader>=0.1.75",
        "praw>=7.7.0",
        "instagrapi>=2.1.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "social-scraper=src.cli:main",
        ],
    },
    python_requires=">=3.9",
)
