# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from setuptools import setup, find_packages

setup(
    name="ltp-storage-common",
    version="0.1.0",
    packages=find_packages(),
    package_dir={"ltp_storage": "ltp_storage"},
    install_requires=[
        "python-dateutil>=2.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ]
    },
    python_requires=">=3.8",
    description="Common storage interfaces, data schemas, and utilities for LTP platform.",
    long_description="Shared package for LTP storage backends (Kusto, PostgreSQL). "
                     "Provides data models, abstract interfaces, and factory pattern for runtime backend selection.",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)

