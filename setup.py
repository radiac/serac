import os

from setuptools import find_packages, setup


VERSION = "0.0.2"


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="serac",
    version=VERSION,
    author="Richard Terry",
    author_email="code@radiac.net",
    description=("Incremental permanent data archiver with encryption"),
    license="BSD",
    keywords="backup archive glacier",
    url="http://radiac.net/projects/serac/",
    long_description=read("README.rst"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: System :: Archiving :: Backup",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    install_requires=["click", "peewee", "pyAesCrypt", "smart-open"],
    setup_requires=["pytest-runner"],
    tests_require=[
        "pytest",
        "pytest-black",
        "pytest-cov",
        "pytest-flake8",
        "pytest-isort",
        "pytest-mypy",
        "pytest-mock",
        "pyfakefs",
        "typing_extensions",
        "doc8",
    ],
    dependency_links=[
        # Bugfix awaiting response to PR:
        # https://github.com/ktosiek/pytest-freezegun/pull/17
        "git+https://github.com/radiac/pytest-freezegun.git@bugfix/class-based-tests-with-duration-regression#egg=pytest-freezegun",
        # Bugfix merged but awaiting deployment to PyPI:
        # https://github.com/PyCQA/doc8/pull/17
        "git+https://github.com/radiac/doc8.git@feature/python-api#egg=doc8",
    ],
    zip_safe=True,
    packages=find_packages(exclude=("docs", "tests*")),
    include_package_data=True,
    entry_points={"console_scripts": ["serac=serac.commands:cli"]},
)
