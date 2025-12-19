# SPDX-FileCopyrightText: 2025 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: MIT

"""Tests for resolve_version_from_context function in release-bot."""

import pytest
import sys
from unittest.mock import patch, Mock
from pathlib import Path

# Add parent directory to path to import main module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from main import resolve_version_from_context


class TestResolveVersionIssueComment:
    """Test suite for resolve_version_from_context with issue_comment events (ChatOps)."""

    def test_issue_comment_with_version_provided(self):
        """Test issue_comment event when version is already provided - should use it."""
        version = resolve_version_from_context(
            command="push",
            version="1.2.3",
            issue_number=123,
            repo_name="test/repo",
            event_name="issue_comment",
            token="test_token"
        )
        assert version == "1.2.3"

    def test_issue_comment_with_issue_number_version_found(self):
        """Test issue_comment event with issue number - should detect from issue."""
        with patch('main.get_version_from_issue') as mock_get_version:
            mock_get_version.return_value = "2.0.0"

            version = resolve_version_from_context(
                command="push",
                version=None,
                issue_number=456,
                repo_name="test/repo",
                event_name="issue_comment",
                token="test_token"
            )

            assert version == "2.0.0"
            mock_get_version.assert_called_once_with("test/repo", 456, "test_token")

    def test_issue_comment_with_issue_number_version_not_found(self):
        """Test issue_comment event when version cannot be detected from issue."""
        with patch('main.get_version_from_issue') as mock_get_version, \
             patch('main.post_comment') as mock_post_comment, \
             pytest.raises(SystemExit) as exc_info:

            mock_get_version.return_value = None

            resolve_version_from_context(
                command="push",
                version=None,
                issue_number=789,
                repo_name="test/repo",
                event_name="issue_comment",
                token="test_token"
            )

        # Should exit with code 1
        assert exc_info.value.code == 1

        # Should post error comment
        mock_post_comment.assert_called_once()
        call_args = mock_post_comment.call_args[0]
        assert call_args[0] == "test_token"
        assert call_args[1] == "test/repo"
        assert call_args[2] == 789
        assert "Could not find a release version" in call_args[3]

    def test_issue_comment_without_issue_number(self):
        """Test issue_comment event without issue number - should fail."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_version_from_context(
                command="push",
                version=None,
                issue_number=None,
                repo_name="test/repo",
                event_name="issue_comment",
                token="test_token"
            )

        assert exc_info.value.code == 1

    def test_issue_comment_update_command(self):
        """Test issue_comment event with update command - should detect from issue."""
        with patch('main.get_version_from_issue') as mock_get_version:
            mock_get_version.return_value = "3.1.0"

            version = resolve_version_from_context(
                command="update",
                version=None,
                issue_number=100,
                repo_name="test/repo",
                event_name="issue_comment",
                token="test_token"
            )

            assert version == "3.1.0"
            mock_get_version.assert_called_once()


class TestResolveVersionIssuesEvent:
    """Test suite for resolve_version_from_context with issues events (auto-close)."""

    def test_issues_event_with_version_provided(self):
        """Test issues event when version is explicitly provided - should use it."""
        version = resolve_version_from_context(
            command="push",
            version="4.0.0",
            issue_number=200,
            repo_name="test/repo",
            event_name="issues",
            token="test_token"
        )
        assert version == "4.0.0"

    def test_issues_event_without_version_found_in_issue(self):
        """Test issues event without explicit version - should detect from issue."""
        with patch('main.get_version_from_issue') as mock_get_version:
            mock_get_version.return_value = "4.1.0"

            version = resolve_version_from_context(
                command="push",
                version=None,
                issue_number=300,
                repo_name="test/repo",
                event_name="issues",
                token="test_token"
            )

            assert version == "4.1.0"
            mock_get_version.assert_called_once_with("test/repo", 300, "test_token")

    def test_issues_event_version_not_found_exits_gracefully(self, capsys):
        """Test issues event when version can't be found - should exit gracefully (code 0)."""
        with patch('main.get_version_from_issue') as mock_get_version, \
             pytest.raises(SystemExit) as exc_info:

            mock_get_version.return_value = None

            resolve_version_from_context(
                command="push",
                version=None,
                issue_number=400,
                repo_name="test/repo",
                event_name="issues",
                token="test_token"
            )

        # Should exit with code 0 (graceful), not 1 (error)
        assert exc_info.value.code == 0

        # Should try to get version from issue
        mock_get_version.assert_called_once()

        # Check graceful message
        captured = capsys.readouterr()
        assert "no release version found" in captured.out.lower()
        assert "Skipping release push" in captured.out

    def test_issues_event_without_issue_number_exits_gracefully(self, capsys):
        """Test issues event without issue number - should exit gracefully."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_version_from_context(
                command="push",
                version=None,
                issue_number=None,
                repo_name="test/repo",
                event_name="issues",
                token="test_token"
            )

        # Should exit gracefully
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Skipping release push" in captured.out


class TestResolveVersionWorkflowDispatch:
    """Test suite for resolve_version_from_context with workflow_dispatch events."""

    def test_workflow_dispatch_with_version_provided(self):
        """Test workflow_dispatch event when version is provided - should use it."""
        version = resolve_version_from_context(
            command="workflow_dispatch",
            version="5.0.0",
            issue_number=None,
            repo_name="test/repo",
            event_name="workflow_dispatch",
            token="test_token"
        )
        assert version == "5.0.0"

    def test_workflow_dispatch_push_command_with_version(self):
        """Test workflow_dispatch with push command and version provided."""
        version = resolve_version_from_context(
            command="push",
            version="6.0.0",
            issue_number=None,
            repo_name="test/repo",
            event_name="workflow_dispatch",
            token="test_token"
        )
        assert version == "6.0.0"

    def test_workflow_dispatch_push_command_without_version(self):
        """Test workflow_dispatch with push command but no version - should fail."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_version_from_context(
                command="push",
                version=None,
                issue_number=None,
                repo_name="test/repo",
                event_name="workflow_dispatch",
                token="test_token"
            )

        assert exc_info.value.code == 1

    def test_workflow_dispatch_with_issue_number_and_no_version(self):
        """Test workflow_dispatch with push command, issue number, but no version - should try to detect."""
        with patch('main.get_version_from_issue') as mock_get_version:
            mock_get_version.return_value = "5.5.0"

            version = resolve_version_from_context(
                command="push",
                version=None,
                issue_number=500,
                repo_name="test/repo",
                event_name="workflow_dispatch",
                token="test_token"
            )

            # Should detect from issue since issue_number is present
            assert version == "5.5.0"
            mock_get_version.assert_called_once_with("test/repo", 500, "test_token")


class TestResolveVersionPullRequest:
    """Test suite for resolve_version_from_context with pull_request events."""

    def test_pull_request_with_version_provided(self):
        """Test pull_request event when version is provided - should use it."""
        version = resolve_version_from_context(
            command="push",
            version="7.0.0",
            issue_number=None,
            repo_name="test/repo",
            event_name="pull_request",
            token="test_token"
        )
        assert version == "7.0.0"

    def test_pull_request_without_version_no_issue(self):
        """Test pull_request event without version and no linked issue - should fail."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_version_from_context(
                command="push",
                version=None,
                issue_number=None,
                repo_name="test/repo",
                event_name="pull_request",
                token="test_token"
            )

        assert exc_info.value.code == 1

    def test_pull_request_without_version_but_has_issue(self):
        """Test pull_request event without version but with linked issue - should detect from issue."""
        with patch('main.get_version_from_issue') as mock_get_version:
            mock_get_version.return_value = "7.1.0"

            version = resolve_version_from_context(
                command="push",
                version=None,
                issue_number=600,
                repo_name="test/repo",
                event_name="pull_request",
                token="test_token"
            )

            assert version == "7.1.0"
            mock_get_version.assert_called_once_with("test/repo", 600, "test_token")

    def test_pull_request_without_version_issue_not_found(self):
        """Test pull_request event when version can't be found in issue - should fail."""
        with patch('main.get_version_from_issue') as mock_get_version, \
             pytest.raises(SystemExit) as exc_info:

            mock_get_version.return_value = None

            resolve_version_from_context(
                command="push",
                version=None,
                issue_number=650,
                repo_name="test/repo",
                event_name="pull_request",
                token="test_token"
            )

        # Should exit with error (not graceful like issues event)
        assert exc_info.value.code == 1
        mock_get_version.assert_called_once()


class TestResolveVersionOtherCommands:
    """Test suite for commands that don't require version resolution."""

    def test_generate_command_no_version_resolution(self):
        """Test generate command - should not attempt version resolution."""
        version = resolve_version_from_context(
            command="generate",
            version=None,
            issue_number=123,
            repo_name="test/repo",
            event_name="issue_comment",
            token="test_token"
        )
        # Should return None without trying to resolve
        assert version is None

    def test_list_command_no_version_resolution(self):
        """Test list command - should not attempt version resolution."""
        version = resolve_version_from_context(
            command="list",
            version=None,
            issue_number=None,
            repo_name="test/repo",
            event_name="workflow_dispatch",
            token="test_token"
        )
        assert version is None

    def test_merge_command_no_version_resolution(self):
        """Test merge command - should not attempt version resolution."""
        version = resolve_version_from_context(
            command="merge",
            version=None,
            issue_number=None,
            repo_name="test/repo",
            event_name="issue_comment",
            token="test_token"
        )
        assert version is None


class TestResolveVersionEdgeCases:
    """Test edge cases and error conditions."""

    def test_version_provided_overrides_issue_detection(self):
        """Test that explicitly provided version is used even with issue number."""
        with patch('main.get_version_from_issue') as mock_get_version:
            # This should not be called since version is provided
            mock_get_version.return_value = "wrong.version"

            version = resolve_version_from_context(
                command="push",
                version="8.0.0",
                issue_number=700,
                repo_name="test/repo",
                event_name="issue_comment",
                token="test_token"
            )

            # Should use provided version, not call get_version_from_issue
            assert version == "8.0.0"
            mock_get_version.assert_not_called()

    def test_error_message_formatting(self, capsys):
        """Test that error messages are properly formatted for different events."""
        # issues event should exit gracefully (0)
        with pytest.raises(SystemExit) as exc_info:
            resolve_version_from_context(
                command="push",
                version=None,
                issue_number=None,
                repo_name="test/repo",
                event_name="issues",
                token="test_token"
            )
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Skipping release push" in captured.out

        # Other events should fail with error (1)
        for event_name in ["workflow_dispatch", "pull_request"]:
            with pytest.raises(SystemExit) as exc_info:
                resolve_version_from_context(
                    command="push",
                    version=None,
                    issue_number=None,
                    repo_name="test/repo",
                    event_name=event_name,
                    token="test_token"
                )

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Version is required" in captured.out

    def test_empty_version_string_treated_as_none_issues_event(self):
        """Test that empty string version is treated as missing for issues event."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_version_from_context(
                command="push",
                version="",  # Empty string
                issue_number=None,
                repo_name="test/repo",
                event_name="issues",
                token="test_token"
            )
        # issues event should exit gracefully
        assert exc_info.value.code == 0

    def test_empty_version_string_treated_as_none_other_events(self):
        """Test that empty string version is treated as missing for other events."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_version_from_context(
                command="push",
                version="",  # Empty string
                issue_number=None,
                repo_name="test/repo",
                event_name="workflow_dispatch",
                token="test_token"
            )
        # Other events should fail
        assert exc_info.value.code == 1
