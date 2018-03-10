#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os

setup(
    name='scanscripts',
    author='Mark Wolf, Doga Gursoy, Francesco De Carlo',
    # packages=find_packages(),
    packages=['aps_32id', 'aps_02bm', 'scanlib'],
    version=open(os.path.join(os.path.dirname(__file__), 'VERSION')).read().strip(),
    description = 'Control software for various X-ray imaging beamlines.',
    license='BSD-3',
    platforms='Any',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: BSD-3',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)
