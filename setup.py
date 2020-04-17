from io import open
from setuptools import find_packages, setup

with open('src/bitarchitect/__init__.py', 'r') as f:
    for line in f:
        if line.startswith('__version__'):
            version = line.strip().split('=')[1].strip(' \'"')
            break
    else:
        version = '0.0.1'
with open('README.md','r') as f:
    readme = f.read()

REQUIRES = []

setup(
    name='bitarchitect',
    version=version,
    description='',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Matthew Miguel',
    author_email='mmiguel6288code@gmail.com',
    maintainer='Matthew Miguel',
    maintainer_email='mmiguel6288code@gmail.com',
    url='https://github.com/mmiguel6288code/bitarchitect',
    license='MIT',
    keywords=[
        'bit','byte','bitarchitect','parse','parsing','extract','extracting',
        'construct','constructing','blueprint','structure',
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
    ],

    install_requires=REQUIRES,
    tests_require=[],
    packages=find_packages('src'),
)
