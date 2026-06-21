from setuptools import setup, find_packages

setup(
    name='ghostql',
    version='1.0.0',
    description='Composable sequential database engine for unstructured associative memory',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Toridion Ltd',
    url='https://github.com/toridion/ghostql',
    license='MIT',
    packages=find_packages(exclude=['examples', 'docs', 'tests']),
    python_requires='>=3.11',
    install_requires=[
        'requests>=2.28',
        'urllib3>=1.26',
    ],
    entry_points={
        'console_scripts': [
            'ghostql=ghostql.server:main',
        ],
    },
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Database',
        'Topic :: Software Development :: Libraries',
        'Intended Audience :: Developers',
    ],
)
