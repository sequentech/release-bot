# SPDX-FileCopyrightText: 2025 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: MIT

"""Tests for release-bot cancel command handling."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
from pathlib import Path

# Mock the imports that don't exist before importing main
sys.modules['release_tool'] = MagicMock()
sys.modules['release_tool.db'] = MagicMock()
sys.modules['release_tool.config'] = MagicMock()
sys.modules['release_tool.commands'] = MagicMock()
sys.modules['release_tool.commands.push'] = MagicMock()
sys.modules['release_tool.policies'] = MagicMock()
sys.modules['release_tool.models'] = MagicMock()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import handle_cancel


def test_handle_cancel_basic():
    """Test handle_cancel builds correct command."""
    with patch('main.run_command') as mock_run:
        mock_run.return_value = "✓ Cancel completed"

        result = handle_cancel(
            base_cmd="release-tool",
            version="1.2.3",
            issue_number=42,
            pr_number=None,
            force=False,
            debug=False
        )

        # Verify command was built correctly with --auto before cancel
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "release-tool --auto cancel 1.2.3 --issue 42" == cmd


def test_handle_cancel_with_force():
    """Test handle_cancel with force flag."""
    with patch('main.run_command') as mock_run:
        mock_run.return_value = "✓ Cancel completed"

        result = handle_cancel(
            base_cmd="release-tool",
            version="1.2.3",
            issue_number=42,
            pr_number=None,
            force=True,
            debug=False
        )

        cmd = mock_run.call_args[0][0]
        assert "--force" in cmd
        assert "--auto cancel" in cmd


def test_handle_cancel_with_pr():
    """Test handle_cancel with PR number."""
    with patch('main.run_command') as mock_run:
        mock_run.return_value = "✓ Cancel completed"

        result = handle_cancel(
            base_cmd="release-tool",
            version="1.2.3",
            issue_number=42,
            pr_number=123,
            force=False,
            debug=False
        )

        cmd = mock_run.call_args[0][0]
        assert "--pr 123" in cmd
        assert "--auto cancel" in cmd


def test_handle_cancel_with_debug():
    """Test handle_cancel with debug mode."""
    with patch('main.run_command') as mock_run:
        mock_run.return_value = "✓ Cancel completed"

        result = handle_cancel(
            base_cmd="release-tool --debug",
            version="1.2.3",
            issue_number=42,
            pr_number=None,
            force=False,
            debug=True
        )

        cmd = mock_run.call_args[0][0]
        assert "release-tool --debug --auto cancel" in cmd


def test_handle_cancel_minimal():
    """Test handle_cancel with minimal parameters."""
    with patch('main.run_command') as mock_run:
        mock_run.return_value = "✓ Cancel completed"

        result = handle_cancel(
            base_cmd="release-tool",
            version=None,
            issue_number=42,
            pr_number=None,
            force=False,
            debug=False
        )

        cmd = mock_run.call_args[0][0]
        assert "release-tool --auto cancel --issue 42" == cmd


def test_handle_cancel_command_string_validation():
    """Test that cancel command string is built correctly with --auto in right place."""
    with patch('main.run_command') as mock_run:
        mock_run.return_value = ""

        # Test basic command
        handle_cancel(
            base_cmd="release-tool",
            version="1.2.3",
            issue_number=None,
            pr_number=None,
            force=False,
            debug=False
        )

        cmd = mock_run.call_args[0][0]
        # Verify --auto comes BEFORE cancel, not after
        assert "--auto cancel" in cmd
        assert "cancel --auto" not in cmd


def test_handle_cancel_with_all_options():
    """Test cancel with all possible options."""
    with patch('main.run_command') as mock_run:
        mock_run.return_value = ""

        handle_cancel(
            base_cmd="release-tool --debug",
            version="1.2.3",
            issue_number=42,
            pr_number=123,
            force=True,
            debug=True
        )

        cmd = mock_run.call_args[0][0]
        # Verify all parts are present
        assert "release-tool --debug --auto cancel" in cmd
        assert "1.2.3" in cmd
        assert "--issue 42" in cmd
        assert "--pr 123" in cmd
        assert "--force" in cmd
