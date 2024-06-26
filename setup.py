import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='nla_control',
    version='1.2.3',
    packages=['nla_control'],
    install_requires=[
        'appdirs',
        'asgiref',
        'certifi',
        'charset-normalizer',
        'click',
        'colorama',
        'Django',
        'django-extensions',
        'django-multiselectfield',
        'django-sizefield',
        'elastic-transport',
        'elasticsearch',
        'fbi-core',
        'idna',
        'psycopg2-binary',
        'pyparsing',
        'pytz',
        'PyYAML',
        'requests',
        'sqlparse',
        'tabulate',
        'tqdm',
        'urllib3',
        'fbi-core @ git+https://github.com/cedadev/fbi-core.git#egg=fbi_core'
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
