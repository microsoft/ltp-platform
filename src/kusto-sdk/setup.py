# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from setuptools import setup, find_packages

setup(
    name="ltp-kusto-sdk",
    version="0.1.0",
    packages=find_packages(),
    package_dir={"ltp_kusto_sdk": "ltp_kusto_sdk"},
    install_requires=[
        "azure-kusto-data>=0.0.45",
        "azure-kusto-ingest>=0.0.45",
        "azure-identity>=1.5.0",
        "azure-mgmt-compute",
        "pandas>=1.0.0",
        "requests>=2.25.0",
        "joblib>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ]
    },
    python_requires=">=3.8",
    description="A Python SDK for interacting with Azure Data Explorer (Kusto).",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/microsoft/pai",
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