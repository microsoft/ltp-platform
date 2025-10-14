# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Main module."""

from .copilot_service import CoPilotService


def main():
    """Main function."""
    api = CoPilotService()
    api.run()


if __name__ == "__main__":
    """Entry point."""
    main()
