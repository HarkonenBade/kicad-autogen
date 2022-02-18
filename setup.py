#!/usr/bin/env python

from distutils.core import setup

setup(name='KICAD Autogen',
      version='1.0',
      description='KICAD Automatic Generation Scripts',
      author='Thomas Bytheway',
      author_email='kicad_autogen@harkonen.net',
      install_requires=['PyYaml>=1.0'],
      scripts=['build_lib.py'],
     )