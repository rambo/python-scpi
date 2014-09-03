from distutils.core import setup
import subprocess

git_version = str(subprocess.check_output(['git', 'rev-parse', '--verify', '--short', 'HEAD'])).strip()

setup(
    name='scpi',
#    version='0.5.dev-%s' % git_version,
    version='0.5',
    author='Eero "rambo" af Heurlin',
    author_email='rambo@iki.fi',
    packages=['scpi',],
    license='GNU LGPL',
    long_description=open('README.md').read(),
    install_requires=[
        'pyserial>=2.7',
    ],
    url='https://github.com/rambo/python-scpi',
)

