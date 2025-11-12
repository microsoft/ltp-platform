# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""logger"""

import logging
import sys
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored terminal text and force colors
init(autoreset=True, strip=False)

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA,
    }

    def format(self, record):
        # Get the original formatted message
        message = super().format(record)
        
        # Add color to the level name
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_levelname = f"{self.COLORS[levelname]}[{levelname}]{Style.RESET_ALL}"
            # Replace the levelname in the formatted message
            message = message.replace(f" - {levelname} - ", f" - {colored_levelname} - ")
        
        return message

# Define a function to set up the logging configuration
def setup_logging():
    """
    Configures the root logger for the application.
    Messages of INFO level and higher will be printed to stdout (console).
    """
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Set the overall minimum level for the logger
    root_logger.setLevel(logging.INFO)

    # Prevent adding multiple handlers if setup_logging is called multiple times
    if not root_logger.handlers:
        # Create a StreamHandler to output logs to stdout (so tee can capture them)
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Set the level for this specific handler
        console_handler.setLevel(logging.INFO)

        # Create a colored formatter for the log messages
        formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Set the formatter for the console handler
        console_handler.setFormatter(formatter)
        
        # Add the console handler to the root logger
        root_logger.addHandler(console_handler)

# Call setup_logging when this module is imported
setup_logging()

# Expose a proper logger instance
logger = logging.getLogger(__name__)
