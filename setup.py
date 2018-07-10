from distutils.core import setup
import subprocess
import sys

if sys.version_info < (3,5):
    raise RuntimeError("Minimum version python 3.5")

git_version = 'UNKNOWN'
try:
    git_version = str(subprocess.check_output(['git', 'rev-parse', '--verify', '--short', 'HEAD'])).strip()
except subprocess.CalledProcessError as e:
    #print("Got error when trying to read git version: %s" % e)
    pass

setup(
    name='scpi',
    version='2.0.0dev-%s' % git_version,
    #version='2.0.0',
    author='Eero "rambo" af Heurlin',
    author_email='rambo@iki.fi',
    packages=[ 'scpi', 'scpi.errors', 'scpi.transports', 'scpi.devices' ],
    license='GNU LGPL',
    long_description=open('README.md', 'rt', encoding='utf-8').read(),
    description='Implement SCPI in pure Python',
    install_requires=open('requirements.txt', 'rt', encoding='utf-8').readlines(),
    url='https://github.com/rambo/python-scpi',
)
