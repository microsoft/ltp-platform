"""Main module."""

from .copilot_service import CoPilotService
from .copilot_conversation import CoPilotConversation


def main():
    """Main function."""
    copilot_conversation = CoPilotConversation()
    api = CoPilotService(copilot_conversation)
    api.run()


if __name__ == "__main__":
    """Entry point."""
    main()
