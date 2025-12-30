# SPDX-FileCopyrightText: 2025 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: MIT

"""Tests for run_pull function in release-bot."""

import pytest
import sys
from unittest.mock import patch, Mock, MagicMock
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
from main import run_pull


class TestRunPull:
    """Test suite for run_pull function."""

    def test_run_pull_success(self):
        """Test successful pull command execution."""
        with patch('main.run_command') as mock_run_cmd, \
             patch('main.post_comment') as mock_post_comment:
            
            mock_run_cmd.return_value = ""
            
            # Should not raise any exception
            run_pull(
                base_cmd="release-tool --auto",
                debug=False,
                issue_number=None,
                event_name="workflow_dispatch",
                token="test_token",
                repo_name="test/repo"
            )
            
            # Verify command was called correctly
            mock_run_cmd.assert_called_once_with("release-tool --auto pull", debug=False)
            # No comment should be posted on success
            mock_post_comment.assert_not_called()

    def test_run_pull_with_debug(self):
        """Test pull command with debug flag."""
        with patch('main.run_command') as mock_run_cmd, \
             patch('main.post_comment') as mock_post_comment:
            
            mock_run_cmd.return_value = ""
            
            run_pull(
                base_cmd="release-tool --auto --debug",
                debug=True,
                issue_number=None,
                event_name="workflow_dispatch",
                token="test_token",
                repo_name="test/repo"
            )
            
            # Verify debug flag was passed
            mock_run_cmd.assert_called_once_with("release-tool --auto --debug pull", debug=True)

    def test_run_pull_failure_without_issue(self):
        """Test pull command failure without issue number."""
        with patch('main.run_command') as mock_run_cmd, \
             patch('main.post_comment') as mock_post_comment, \
             pytest.raises(SystemExit) as exc_info:
            
            mock_run_cmd.side_effect = Exception("Connection error")
            
            run_pull(
                base_cmd="release-tool --auto",
                debug=False,
                issue_number=None,
                event_name="workflow_dispatch",
                token="test_token",
                repo_name="test/repo"
            )
            
        # Should exit with code 1
        assert exc_info.value.code == 1
        # No comment should be posted (no issue number)
        mock_post_comment.assert_not_called()

    def test_run_pull_failure_with_issue_comment(self):
        """Test pull command failure with issue comment event."""
        with patch('main.run_command') as mock_run_cmd, \
             patch('main.post_comment') as mock_post_comment, \
             pytest.raises(SystemExit) as exc_info:
            
            mock_run_cmd.side_effect = Exception("API rate limit exceeded")
            
            run_pull(
                base_cmd="release-tool --auto",
                debug=False,
                issue_number=123,
                event_name="issue_comment",
                token="test_token",
                repo_name="test/repo"
            )
            
        # Should exit with code 1
        assert exc_info.value.code == 1
        
        # Should post error comment
        mock_post_comment.assert_called_once()
        call_args = mock_post_comment.call_args[0]
        assert call_args[0] == "test_token"
        assert call_args[1] == "test/repo"
        assert call_args[2] == 123
        assert "❌ Pull failed:" in call_args[3]
        assert "API rate limit exceeded" in call_args[3]

    def test_run_pull_failure_with_issue_non_comment_event(self):
        """Test pull command failure with issue number but non-comment event."""
        with patch('main.run_command') as mock_run_cmd, \
             patch('main.post_comment') as mock_post_comment, \
             pytest.raises(SystemExit) as exc_info:
            
            mock_run_cmd.side_effect = Exception("Network error")
            
            run_pull(
                base_cmd="release-tool --auto",
                debug=False,
                issue_number=456,
                event_name="issues",  # Not issue_comment
                token="test_token",
                repo_name="test/repo"
            )
            
        # Should exit with code 1
        assert exc_info.value.code == 1
        
        # Should NOT post comment (event is not issue_comment)
        mock_post_comment.assert_not_called()

    def test_run_pull_command_construction(self):
        """Test that the pull command is constructed correctly."""
        with patch('main.run_command') as mock_run_cmd:
            mock_run_cmd.return_value = ""
            
            # Test with config path
            run_pull(
                base_cmd="release-tool --auto --config /path/to/config.toml",
                debug=False,
                issue_number=None,
                event_name="workflow_dispatch",
                token="test_token",
                repo_name="test/repo"
            )
            
            # Verify the full command includes pull
            expected_cmd = "release-tool --auto --config /path/to/config.toml pull"
            mock_run_cmd.assert_called_once_with(expected_cmd, debug=False)

    def test_run_pull_prints_progress_messages(self, capsys):
        """Test that progress messages are printed."""
        with patch('main.run_command') as mock_run_cmd:
            mock_run_cmd.return_value = ""
            
            run_pull(
                base_cmd="release-tool --auto",
                debug=False,
                issue_number=None,
                event_name="workflow_dispatch",
                token="test_token",
                repo_name="test/repo"
            )
            
            captured = capsys.readouterr()
            assert "Pulling..." in captured.out
            assert "✅ Pull completed successfully" in captured.out
