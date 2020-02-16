#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'Click>=6.0',
    'construct>=2.9,<2.10',
    'lxml>=4.3',
    'numpy>=1.16',
    'Pillow>=6.2.1',
]

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest', 'pytest-datadir']

setup(
    author="Peter Rowlands",
    author_email='peter@pmrowla.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="Python package for manipulating LiveMaker game resources.",
    entry_points={
        'console_scripts': [
            'lmar=livemaker.cli:lmar',
            'lmlsb=livemaker.cli:lmlsb',
            'lmpatch=livemaker.patch:lmpatch',
            'galconvert=livemaker.cli:galconvert',
        ],
    },
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='LiveMaker',
    name='pylivemaker',
    packages=find_packages(include=['livemaker', 'livemaker.lsb']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/pmrowla/pylivemaker',
    version='0.2.0',
    zip_safe=False,
)
