#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup


with open('requirements.txt') as fobj:
    install_requires = [line.strip() for line in fobj]


with open('README.md') as fobj:
    long_description = fobj.read()


packages = find_packages(exclude=['tests*'])
scripts = ['thermostatd']


setup(
    name='thermostat_daemon',
    version='0.0.1',
    author='Daniele Ricci',
    author_email='daniele@casaricci.it',
    packages=packages,
    url='https://github.com/daniele-athome/thermostat-daemon',
    license='LICENSE.txt',
    description='HTTP API and backend daemon for Raspberry PI Smart Thermostat',
    long_description=long_description,
    include_package_data=True,
    scripts=scripts,
    install_requires=install_requires)
