# SPDX-FileCopyrightText: 2025 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: MIT

"""Tests for initial issue comment functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
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

from main import (
    parse_push_output,
    post_initial_issue_comment,
    get_release_url_from_github,
    post_initial_comment_after_push,
)


class TestParsePushOutput:
    """Tests for parse_push_output function."""

    def test_parse_created_issue(self):
        """Test parsing output when issue is created."""
        output = """
        Created issue #123
        Issue URL: https://github.com/owner/repo/issues/123
        """
        result = parse_push_output(output)

        assert result['issue_number'] == 123
        assert result['issue_url'] == "https://github.com/owner/repo/issues/123"

    def test_parse_updated_issue(self):
        """Test parsing output when issue is updated."""
        output = "Updated issue #456 details (title, body, labels, milestone, type)"
        result = parse_push_output(output)

        assert result['issue_number'] == 456

    def test_parse_reused_issue(self):
        """Test parsing output when existing issue is reused."""
        output = "Reusing existing issue #789 (--force)"
        result = parse_push_output(output)

        assert result['issue_number'] == 789

    def test_parse_release_url(self):
        """Test parsing release URL from output."""
        output = """
        Created GitHub release: https://github.com/owner/repo/releases/tag/v1.2.3
        """
        result = parse_push_output(output)

        assert result['release_url'] == "https://github.com/owner/repo/releases/tag/v1.2.3"

    def test_parse_complete_output(self):
        """Test parsing output with all information."""
        output = """
        Generating release notes...
        Created issue #123
        Issue URL: https://github.com/owner/repo/issues/123
        Created GitHub release: https://github.com/owner/repo/releases/tag/v1.2.3
        """
        result = parse_push_output(output)

        assert result['issue_number'] == 123
        assert result['issue_url'] == "https://github.com/owner/repo/issues/123"
        assert result['release_url'] == "https://github.com/owner/repo/releases/tag/v1.2.3"

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_push_output("")

        assert result['issue_number'] is None
        assert result['issue_url'] is None
        assert result['release_url'] is None

    def test_parse_none_output(self):
        """Test parsing None output."""
        result = parse_push_output(None)

        assert result['issue_number'] is None
        assert result['issue_url'] is None
        assert result['release_url'] is None

    def test_parse_issue_without_url(self):
        """Test parsing when issue number is present but URL is not."""
        output = "Created issue #999"
        result = parse_push_output(output)

        assert result['issue_number'] == 999
        assert result['issue_url'] is None

    def test_parse_lowercase_issue(self):
        """Test parsing lowercase 'issue' pattern."""
        output = "Creating issue #111 in owner/repo..."
        result = parse_push_output(output)

        assert result['issue_number'] == 111

    def test_parse_alternative_release_url_format(self):
        """Test parsing alternative release URL formats."""
        output = "View release: https://github.com/owner/repo/releases/v2.0.0"
        result = parse_push_output(output)

        assert result['release_url'] == "https://github.com/owner/repo/releases/v2.0.0"

    def test_parse_long_untagged_release_url(self):
        """Test parsing long untagged release URLs with hash suffixes."""
        output = """
        URL: https://github.com/sequentech/release-tool/releases/tag/untagged-c646978674c90c99ae21
        """
        result = parse_push_output(output)

        assert result['release_url'] == "https://github.com/sequentech/release-tool/releases/tag/untagged-c646978674c90c99ae21"

    def test_parse_release_url_with_ansi_codes(self):
        """Test parsing release URL when output contains ANSI escape codes."""
        # Simulate Rich console output with ANSI codes
        output = "\x1b[33m  URL: https://github.com/owner/repo/releases/tag/v1.2.3\x1b[0m"
        result = parse_push_output(output)

        assert result['release_url'] == "https://github.com/owner/repo/releases/tag/v1.2.3"


class TestPostInitialIssueComment:
    """Tests for post_initial_issue_comment function."""

    @patch('main.Github')
    def test_post_comment_with_all_info(self, mock_github_class):
        """Test posting comment with all information available."""
        # Setup mocks
        mock_issue = Mock()
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        post_initial_issue_comment(
            token="fake_token",
            repo_name="owner/repo",
            issue_number=123,
            version="1.2.3",
            release_url="https://github.com/owner/repo/releases/tag/v1.2.3",
            workflow_run_url="https://github.com/owner/repo/actions/runs/123456"
        )

        # Assertions
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.create_comment.assert_called_once()

        # Check comment content
        comment_body = mock_issue.create_comment.call_args[0][0]
        assert "## 🤖 Release Bot" in comment_body
        assert "`1.2.3`" in comment_body
        assert "https://github.com/owner/repo/releases/tag/v1.2.3" in comment_body
        assert "https://github.com/owner/repo/actions/runs/123456" in comment_body
        assert "/release-bot update" in comment_body
        assert "/release-bot push" in comment_body
        assert "/release-bot generate" in comment_body
        assert "/release-bot list" in comment_body
        assert "/release-bot merge" in comment_body

    @patch('main.Github')
    def test_post_comment_without_release_url(self, mock_github_class):
        """Test posting comment when release URL is not available."""
        # Setup mocks
        mock_issue = Mock()
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        post_initial_issue_comment(
            token="fake_token",
            repo_name="owner/repo",
            issue_number=123,
            version="1.2.3",
            release_url=None,
            workflow_run_url="https://github.com/owner/repo/actions/runs/123456"
        )

        # Assertions
        mock_issue.create_comment.assert_called_once()
        comment_body = mock_issue.create_comment.call_args[0][0]
        assert "## 🤖 Release Bot" in comment_body
        assert "`1.2.3`" in comment_body
        assert "GitHub Release" not in comment_body  # Should not include release link
        assert "https://github.com/owner/repo/actions/runs/123456" in comment_body

    @patch('main.Github')
    def test_post_comment_without_workflow_url(self, mock_github_class):
        """Test posting comment when workflow URL is not available."""
        # Setup mocks
        mock_issue = Mock()
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        post_initial_issue_comment(
            token="fake_token",
            repo_name="owner/repo",
            issue_number=123,
            version="1.2.3",
            release_url="https://github.com/owner/repo/releases/tag/v1.2.3",
            workflow_run_url=None
        )

        # Assertions
        mock_issue.create_comment.assert_called_once()
        comment_body = mock_issue.create_comment.call_args[0][0]
        assert "## 🤖 Release Bot" in comment_body
        assert "https://github.com/owner/repo/releases/tag/v1.2.3" in comment_body
        assert "Workflow Run" not in comment_body  # Should not include workflow link

    @patch('main.Github')
    def test_post_comment_minimal(self, mock_github_class):
        """Test posting comment with only required fields."""
        # Setup mocks
        mock_issue = Mock()
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        post_initial_issue_comment(
            token="fake_token",
            repo_name="owner/repo",
            issue_number=123,
            version="1.2.3"
        )

        # Assertions
        mock_issue.create_comment.assert_called_once()
        comment_body = mock_issue.create_comment.call_args[0][0]
        assert "## 🤖 Release Bot" in comment_body
        assert "`1.2.3`" in comment_body
        assert "/release-bot update" in comment_body

    @patch('main.Github')
    def test_comment_format_includes_all_commands(self, mock_github_class):
        """Test that comment includes all available commands."""
        # Setup mocks
        mock_issue = Mock()
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        post_initial_issue_comment(
            token="fake_token",
            repo_name="owner/repo",
            issue_number=123,
            version="1.2.3"
        )

        comment_body = mock_issue.create_comment.call_args[0][0]

        # Verify all commands are listed
        assert "/release-bot update" in comment_body
        assert "/release-bot push" in comment_body
        assert "/release-bot generate" in comment_body
        assert "/release-bot list" in comment_body
        assert "/release-bot merge" in comment_body

        # Verify command descriptions
        assert "Regenerate release notes and publish" in comment_body
        assert "Publish the release" in comment_body
        assert "Generate release notes only" in comment_body
        assert "List all draft releases" in comment_body
        assert "Merge PR, publish release, and close this issue" in comment_body

    @patch('main.Github')
    def test_comment_with_rc_version(self, mock_github_class):
        """Test posting comment for release candidate version."""
        # Setup mocks
        mock_issue = Mock()
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        post_initial_issue_comment(
            token="fake_token",
            repo_name="owner/repo",
            issue_number=123,
            version="1.2.3-rc.0"
        )

        comment_body = mock_issue.create_comment.call_args[0][0]
        assert "`1.2.3-rc.0`" in comment_body


class TestGetReleaseUrlFromGithub:
    """Tests for get_release_url_from_github function."""

    @patch('main.Github')
    def test_get_release_by_tag_success(self, mock_github_class):
        """Test successfully getting release URL by tag."""
        # Setup mocks
        mock_release = Mock()
        mock_release.html_url = "https://github.com/owner/repo/releases/tag/v1.2.3"
        mock_repo = Mock()
        mock_repo.get_release.return_value = mock_release
        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        result = get_release_url_from_github(
            token="fake_token",
            repo_name="owner/repo",
            version="1.2.3"
        )

        # Assertions
        assert result == "https://github.com/owner/repo/releases/tag/v1.2.3"
        mock_repo.get_release.assert_called_once_with("v1.2.3")

    @patch('main.Github')
    def test_get_release_by_search_when_tag_fails(self, mock_github_class):
        """Test finding release by searching when direct tag lookup fails."""
        from github import GithubException

        # Setup mocks
        mock_release1 = Mock()
        mock_release1.html_url = "https://github.com/owner/repo/releases/tag/untagged-abc123"
        mock_release1.title = "Release 1.2.3"
        mock_release1.tag_name = "untagged-abc123"

        mock_repo = Mock()
        # First call (get_release) fails
        mock_repo.get_release.side_effect = GithubException(404, "Not found")
        # Second call (get_releases) returns list
        mock_repo.get_releases.return_value = [mock_release1]

        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        result = get_release_url_from_github(
            token="fake_token",
            repo_name="owner/repo",
            version="1.2.3"
        )

        # Assertions
        assert result == "https://github.com/owner/repo/releases/tag/untagged-abc123"

    @patch('main.Github')
    def test_get_release_returns_none_when_not_found(self, mock_github_class):
        """Test returning None when release not found."""
        from github import GithubException

        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_release.side_effect = GithubException(404, "Not found")
        mock_repo.get_releases.return_value = []  # No releases

        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        # Call function
        result = get_release_url_from_github(
            token="fake_token",
            repo_name="owner/repo",
            version="1.2.3"
        )

        # Assertions
        assert result is None


class TestPostInitialCommentAfterPush:
    """Tests for post_initial_comment_after_push helper function."""

    @patch('main.post_initial_issue_comment')
    @patch('main.get_release_url_from_github')
    @patch('main.parse_push_output')
    def test_post_comment_with_github_api_url(self, mock_parse, mock_get_url, mock_post_comment):
        """Test posting comment using URL from GitHub API."""
        # Setup mocks
        mock_parse.return_value = {
            'issue_number': 123,
            'issue_url': None,
            'release_url': None
        }
        mock_get_url.return_value = "https://github.com/owner/repo/releases/tag/v1.2.3"

        # Call function
        post_initial_comment_after_push(
            token="fake_token",
            repo_name="owner/repo",
            version="1.2.3",
            push_output="Created issue #123",
            workflow_run_url="https://github.com/owner/repo/actions/runs/123"
        )

        # Assertions
        mock_get_url.assert_called_once_with("fake_token", "owner/repo", "1.2.3")
        mock_post_comment.assert_called_once()
        call_args = mock_post_comment.call_args[1]
        assert call_args['issue_number'] == 123
        assert call_args['release_url'] == "https://github.com/owner/repo/releases/tag/v1.2.3"

    @patch('main.post_initial_issue_comment')
    @patch('main.get_release_url_from_github')
    @patch('main.parse_push_output')
    def test_post_comment_fallback_to_parsed_url(self, mock_parse, mock_get_url, mock_post_comment):
        """Test falling back to parsed URL when GitHub API fails."""
        # Setup mocks
        mock_parse.return_value = {
            'issue_number': 123,
            'issue_url': None,
            'release_url': "https://github.com/owner/repo/releases/tag/untagged-abc"
        }
        mock_get_url.return_value = None  # GitHub API fails

        # Call function
        post_initial_comment_after_push(
            token="fake_token",
            repo_name="owner/repo",
            version="1.2.3",
            push_output="Created issue #123\nURL: https://github.com/owner/repo/releases/tag/untagged-abc",
            workflow_run_url=None
        )

        # Assertions
        mock_post_comment.assert_called_once()
        call_args = mock_post_comment.call_args[1]
        assert call_args['release_url'] == "https://github.com/owner/repo/releases/tag/untagged-abc"

    @patch('main.post_initial_issue_comment')
    @patch('main.get_release_url_from_github')
    @patch('main.parse_push_output')
    def test_no_comment_when_no_issue_number(self, mock_parse, mock_get_url, mock_post_comment):
        """Test skipping comment when no issue number found."""
        # Setup mocks
        mock_parse.return_value = {
            'issue_number': None,
            'issue_url': None,
            'release_url': None
        }

        # Call function
        post_initial_comment_after_push(
            token="fake_token",
            repo_name="owner/repo",
            version="1.2.3",
            push_output="Some output without issue",
            workflow_run_url=None
        )

        # Assertions
        mock_get_url.assert_not_called()
        mock_post_comment.assert_not_called()
