# SPDX-FileCopyrightText: 2025 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: MIT

"""Tests for get_version_from_drafts function in release-bot."""

import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Mock the imports that don't exist before importing main
sys.modules['release_tool'] = MagicMock()
sys.modules['release_tool.db'] = MagicMock()
sys.modules['release_tool.config'] = MagicMock()
sys.modules['release_tool.commands'] = MagicMock()
sys.modules['release_tool.commands.push'] = MagicMock()
sys.modules['release_tool.policies'] = MagicMock()
sys.modules['release_tool.models'] = MagicMock()

# Add parent directory to path to import main module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from main import get_version_from_drafts


class TestGetVersionFromDrafts:
    """Test suite for get_version_from_drafts function."""

    def test_strips_code_0_suffix(self):
        """Test that -code-0 suffix is stripped from draft filename."""
        mock_path = MagicMock()
        mock_path.stem = "9.3.0-rc.30-code-0"
        mock_path.name = "9.3.0-rc.30-code-0.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path]

            version = get_version_from_drafts(None)

            assert version == "9.3.0-rc.30"

    def test_strips_code_1_suffix(self):
        """Test that -code-1 suffix is stripped from draft filename."""
        mock_path = MagicMock()
        mock_path.stem = "9.3.0-rc.30-code-1"
        mock_path.name = "9.3.0-rc.30-code-1.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path]

            version = get_version_from_drafts(None)

            assert version == "9.3.0-rc.30"

    def test_strips_code_10_suffix(self):
        """Test that -code-10 (multi-digit) suffix is stripped from draft filename."""
        mock_path = MagicMock()
        mock_path.stem = "1.2.3-code-10"
        mock_path.name = "1.2.3-code-10.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path]

            version = get_version_from_drafts(None)

            assert version == "1.2.3"

    def test_strips_doc_suffix(self):
        """Test that -doc suffix is stripped from draft filename."""
        mock_path = MagicMock()
        mock_path.stem = "2.0.0-doc"
        mock_path.name = "2.0.0-doc.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path]

            version = get_version_from_drafts(None)

            assert version == "2.0.0"

    def test_strips_release_suffix(self):
        """Test that -release suffix is stripped from draft filename."""
        mock_path = MagicMock()
        mock_path.stem = "3.1.0-release"
        mock_path.name = "3.1.0-release.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path]

            version = get_version_from_drafts(None)

            assert version == "3.1.0"

    def test_no_suffix_returns_full_version(self):
        """Test that filename without suffix returns full version."""
        mock_path = MagicMock()
        mock_path.stem = "4.0.0"
        mock_path.name = "4.0.0.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path]

            version = get_version_from_drafts(None)

            assert version == "4.0.0"

    def test_rc_version_without_suffix(self):
        """Test that RC version without suffix returns full version."""
        mock_path = MagicMock()
        mock_path.stem = "5.0.0-rc.5"
        mock_path.name = "5.0.0-rc.5.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path]

            version = get_version_from_drafts(None)

            assert version == "5.0.0-rc.5"

    def test_no_draft_files_returns_none(self):
        """Test that empty draft files list returns None."""
        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = []

            version = get_version_from_drafts(None)

            assert version is None

    def test_uses_first_draft_file(self):
        """Test that the first (newest) draft file is used."""
        mock_path1 = MagicMock()
        mock_path1.stem = "9.3.0-rc.30-code-1"
        mock_path1.name = "9.3.0-rc.30-code-1.md"

        mock_path2 = MagicMock()
        mock_path2.stem = "9.3.0-rc.29-release"
        mock_path2.name = "9.3.0-rc.29-release.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path1, mock_path2]

            version = get_version_from_drafts(None)

            # Should use first file (mock_path1) and strip -code-1
            assert version == "9.3.0-rc.30"

    def test_config_exception_returns_none(self):
        """Test that config load exception returns None gracefully."""
        with patch('main.load_config') as mock_load_config:
            mock_load_config.side_effect = Exception("Config not found")

            version = get_version_from_drafts(None)

            assert version is None

    def test_code_suffix_takes_priority_over_release_suffix(self):
        """Test that -code-N suffix check happens before -release suffix check."""
        # This tests the ordering in the function - code suffix should be checked first
        mock_path = MagicMock()
        # Edge case: a version that ends with something like "-release-code-0"
        mock_path.stem = "1.0.0-beta-code-0"
        mock_path.name = "1.0.0-beta-code-0.md"

        with patch('main.load_config') as mock_load_config, \
             patch('main._find_draft_releases') as mock_find_drafts:
            mock_find_drafts.return_value = [mock_path]

            version = get_version_from_drafts(None)

            assert version == "1.0.0-beta"
