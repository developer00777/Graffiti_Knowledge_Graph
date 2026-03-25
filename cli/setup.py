"""Setup for cli-anything-champ — CLI harness for CHAMP Graph."""
from setuptools import setup, find_packages

setup(
    name="cli-anything-champ",
    version="1.0.0",
    description="CLI harness for CHAMP Graph — Centralized High-context Agent Memory Platform",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.1",
        "httpx>=0.24.0",
        "prompt-toolkit>=3.0; extra == 'repl'",
    ],
    extras_require={
        "repl": ["prompt-toolkit>=3.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-champ=cli_anything_champ.main:main",
            "champ=cli_anything_champ.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
