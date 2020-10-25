#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "Click>=6.0",
    "construct>=2.9,<2.10",
    "funcy>=1.4",
    "loguru>=0.4.1",
    "lxml>=4.3",
    "networkx>=2.4",
    "numpy>=1.16",
    "Pillow>=7.1.2",
    "pydot>=1.4.1",
]

setup_requirements = [
    "pytest-runner>=5.2",
]

test_requirements = ["pytest>=5.4.1", "pytest-datadir>=1.3.1"]

setup(
    author="Peter Rowlands",
    author_email="peter@pmrowla.com",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Python package for manipulating LiveMaker game resources.",
    entry_points={
        "console_scripts": [
            "lmar=livemaker.cli:lmar",
            "lmgraph=livemaker.cli:lmgraph",
            "lmlpb=livemaker.cli:lmlpb",
            "lmlsb=livemaker.cli:lmlsb",
            "lmpatch=livemaker.cli:lmpatch",
            "galconvert=livemaker.cli:galconvert",
            "lmbmp=livemaker.cli:lmbmp",
        ],
    },
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="LiveMaker",
    name="pylivemaker",
    packages=find_packages(include=["livemaker", "livemaker.cli", "livemaker.lsb"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/pmrowla/pylivemaker",
    version="1.0.1",
    zip_safe=False,
)
