from setuptools import setup, find_packages

setup(
    name="wikipedia2md",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "beautifulsoup4>=4.9.0",
        "click>=8.0.0",
        "requests>=2.25.0",
    ],
    entry_points={
        "console_scripts": [
            "wikipedia2md=wikipedia2md.cli:main",
        ],
    },
    author="Benjamin Poile",
    author_email="",
    description="A tool to convert Wikipedia articles to markdown format",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/poiley/wikipedia2md",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
) 