import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='nla_control',
    version='0.4.6',
    packages=['nla_control'],
    install_requires=[
        'appdirs',
        'django==2.2.8',
        'django-sizefield',
        'django-extensions',
        'django-multiselectfield',
        'psycopg2-binary',
        'pyparsing',
        'pytz',
        'requests',
    ],
    include_package_data=True,
    license='my License',  # example license
    description='A Django app to control retrival and cache managment for data held only on storage-d tape.',
    long_description=README,
    url='http://www.ceda.ac.uk/',
    author='Sam Pepler, Neil Massey',
    author_email='sam.pepler@stfc.ac.uk, neil.massey@stfc.ac.uk',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License', # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
