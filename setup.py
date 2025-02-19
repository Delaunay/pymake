#!/usr/bin/env python
import os
from pathlib import Path
from setuptools import setup


if __name__ == "__main__":
    setup(
        name="pymake",
        version="0.0.0",
        extras_require=dict(),
        description="Parse GNU Makefiles with Python",
        long_description=(Path(__file__).parent / "README.md").read_text(),
        author="linuxlizard",
        author_email="{{cookiecutter.email}}",
        license="GNU General Public License v2.0",
        url="https://pymake.readthedocs.io",
        classifiers=[
            "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Operating System :: OS Independent",
        ],
        packages=[
            "pymake", 
        ],
        setup_requires=["setuptools"],
        install_requires=["pyparsing"],
    )
