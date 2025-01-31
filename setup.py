from setuptools import setup, find_packages

setup(
    name="wikipedia2md",
    version="1.0.2",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "beautifulsoup4",
        "click",
        "wikipedia",
    ],
    extras_require={
        "test": [
            "pytest",
            "pytest-cov",
            "pytest-mock",
        ],
    },
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "wikipedia2md=wikipedia2md.cli:main",
        ],
    },
) 