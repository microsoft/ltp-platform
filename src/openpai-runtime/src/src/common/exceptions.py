# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

class UnknownError(Exception):
    pass


class ImageCheckError(Exception):
    pass


class ImageAuthenticationError(ImageCheckError):
    pass


class ImageNameError(ImageCheckError):
    pass
