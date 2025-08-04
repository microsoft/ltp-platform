"""Main module."""

import argparse  # noqa: E402

from .copilot import CoPilot  # noqa: E402


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', type=str, help='user question, query or inquery', default=None)
    args = parser.parse_args()
    return args


def main():
    """Main function."""
    args = parse_args()
    apiserver = CoPilot(args)
    apiserver.run()


if __name__ == '__main__':
    """Entry point."""
    main()
