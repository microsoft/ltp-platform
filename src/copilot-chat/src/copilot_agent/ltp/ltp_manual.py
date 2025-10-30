# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""LTP User Manual module for LTP component, handling user manual related inquiries."""

from __future__ import annotations

import os
import json
import re

from ..utils.logger import logger
from ..utils.utils import get_prompt_from

from ..config import DATA_DIR, PROMPT_DIR


# User Manual
class UserManual:
    def __init__(self, feature: str, manual_dir: str, index_file: str) -> None:
        """Initialize UserManual with paths to the manual and its index.
        Args:
            manual_dir (str): Path to the manual directory.
            index_file (str): Index file (expected JSON) mapping keys to sections.
        """
        self.manual_root = os.path.join(DATA_DIR, 'LTP', 'manual')
        self.manual_dir = manual_dir
        self.index_file = index_file
        self.default_manual = get_prompt_from(os.path.join(PROMPT_DIR, feature, 'ltp_documentation.txt'))

    def _assemble_user_manual(self) -> str | None:
        """Assemble the user manual content based on the index.
        Returns:
            str: Assembled user manual content.
        """
        index_filepath = os.path.join(self.manual_root, self.manual_dir, self.index_file)
        logger.info(f'Index file path: {index_filepath}')
        if self.index_file.lower().endswith(".md") and os.path.exists(index_filepath):
            with open(index_filepath, 'r', encoding='utf-8') as f:
                index_content = f.read()
                manual_content = index_content
        else:
            manual_content = None

        return manual_content

    def _extract_section_files(self, index_cont: str) -> list[str] | None:
        """
        Abstracts file locations from a Markdown content string by searching the
        entire content for markdown list links.

        It looks for lines matching the pattern: - [Title](Path/to/file.md)
        """
        results: list[str] = []

        # Search the entire document, as the section_header input was removed.
        search_content = index_cont

        # 2. Define the regex pattern for markdown list links: - [Title](Path)
        # Group 1 captures the Title (ignored), Group 2 captures the Path/filepath
        link_pattern = re.compile(r'^\s*-\s*\[([^\]]+)\]\(([^)]+\.md)\)', re.MULTILINE)

        # 3. Find all matches in the content
        matches = link_pattern.findall(search_content)

        # 4. Process matches and format the output
        for title, filepath in matches:
            # Only append the filepath (Group 2) to the results list
            results.append(filepath.strip())

        return results

    def _replace_placeholders(self, content: str) -> str:
        """Replace placeholders in the content with actual values.
        Args:
            content (str): Content with placeholders.
        Returns:
            str: Content with placeholders replaced.
        """        # Example placeholder replacement logic
        placeholders_env_file = os.path.join(self.manual_root, 'setting', 'placeholders.json')
        ph_envs: list[str] = []
        
        if os.path.exists(placeholders_env_file):
            with open(placeholders_env_file, 'r', encoding='utf-8') as f:
                placeholders = json.load(f)
            for key, value in placeholders.items():
                ph_envs = value
        for ph_env in ph_envs:
            value_replaced = os.getenv(ph_env, f'<{ph_env}_NOT_SET>')
            logger.info(f'Replacing placeholder {ph_env} with value: {value_replaced}')
            content = content.replace(f'<ph:{ph_env.lower()}>', value_replaced)
        return content

    def get_content(self) -> str | None:
        """Get the full user manual content by assembling sections based on the index.
        Returns:
            str: Full user manual content.
        """
        manual_content = self._assemble_user_manual()
        if not manual_content:
            logger.warning("User manual index file not found or empty.")
            return None

        section_files = self._extract_section_files(manual_content)
        if not section_files:
            logger.warning("No section files found in the user manual index.")
            return None

        full_manual = ""
        for section_file in section_files:
            section_file = section_file.replace('./', '')  # Clean up relative path if present
            section_path = os.path.join(self.manual_root, self.manual_dir, section_file)
            if os.path.exists(section_path):
                with open(section_path, 'r', encoding='utf-8') as f:
                    section_content = f.read()
                    full_manual += section_content + "\n\n"
            else:
                logger.warning(f"Section file {section_file} not found.")

        final_manual = self._replace_placeholders(full_manual.strip() if full_manual else self.default_manual)
        logger.info(f"length of final_manual: {len(final_manual)}")
        return final_manual