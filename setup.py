from distutils.core import setup
import subprocess

git_version = 'UNKNOWN'
try:
    git_version = str(subprocess.check_output(['git', 'rev-parse', '--verify', '--short', 'HEAD'])).strip()
except subprocess.CalledProcessError,e:
    #print "Got error when trying to read git version: %s" % e
    pass

setup(
    name='scpi',
    #version='0.6.5dev-%s' % git_version,
    version='0.6.5',
    author='Eero "rambo" af Heurlin',
    author_email='rambo@iki.fi',
    packages=[ 'scpi', 'scpi.errors', 'scpi.transports', 'scpi.devices' ],
    license='GNU LGPL',
    long_description=open('README.md').read(),
    description='Implement SCPI in pure Python',
    install_requires=[
        'pyserial>=2.7',
    ],
    url='https://github.com/rambo/python-scpi',
)
