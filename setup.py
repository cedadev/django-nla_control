import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='nla_control',
    version='0.4',
    packages=['nla_control'],
    install_requires=[
        'appdirs',
        'django==1.11.15',
        'django-sizefield==0.9.1',
        'django-extensions==1.7.9',
        'django-multiselectfield==0.1.7',
        'psycopg2',
        'packaging',
        'pyparsing',
        'pytz',
        'six',
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
        # Replace these appropriately if you are stuck on Python 2.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
