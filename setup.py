from setuptools import setup, find_packages

def get_version():
    return open("pyproject.toml").read().split("version")[1].replace("=", "").strip().split("\n")[0].strip("\"'")

setup(
    name="wikipedia2md",
    version=get_version(),
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