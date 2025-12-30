# SPDX-FileCopyrightText: 2025 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: MIT

"""Tests for run_command function in release-bot."""

import pytest
import sys
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import subprocess

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
from main import run_command


class TestRunCommandSuccess:
    """Test suite for successful run_command executions."""

    def test_run_command_success_with_output(self):
        """Test successful command with stdout output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Command output\n"
        mock_result.stderr = ""

        with patch('subprocess.run', return_value=mock_result):
            output = run_command("echo test", debug=False)

        assert output == "Command output\n"

    def test_run_command_success_empty_output(self):
        """Test successful command with no output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch('subprocess.run', return_value=mock_result):
            output = run_command("true", debug=False)

        assert output == ""

    def test_run_command_success_with_stderr_warnings(self):
        """Test successful command with warnings in stderr (exit code 0)."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success\n"
        mock_result.stderr = "Warning: something minor\n"

        with patch('subprocess.run', return_value=mock_result):
            output = run_command("some-tool", debug=False)

        assert output == "Success\n"


class TestRunCommandFailureCapture:
    """Test suite for failed run_command executions with capture=True (default)."""

    def test_run_command_failure_stderr_only(self):
        """Test command failure with error message in stderr only."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: file not found"

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("cat nonexistent.txt", debug=False)

        assert "Error: file not found" in str(exc_info.value)

    def test_run_command_failure_stdout_only(self):
        """Test command failure with error message in stdout only."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Fatal: operation failed"
        mock_result.stderr = ""

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("git status", debug=False)

        assert "Fatal: operation failed" in str(exc_info.value)

    def test_run_command_failure_both_stderr_and_stdout(self):
        """Test command failure with error messages in both stderr and stdout."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Additional context from stdout"
        mock_result.stderr = "Error from stderr"

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("complex-command", debug=False)

        error_message = str(exc_info.value)
        assert "Error from stderr" in error_message
        assert "Additional context from stdout" in error_message

    def test_run_command_failure_empty_output(self):
        """Test command failure with no output (empty stderr and stdout)."""
        mock_result = Mock()
        mock_result.returncode = 127
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("nonexistent-command", debug=False)

        # Should provide a fallback message with exit code
        assert "Command failed with exit code 127" in str(exc_info.value)

    def test_run_command_failure_whitespace_only(self):
        """Test command failure with only whitespace in output."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "   \n  "
        mock_result.stderr = "\n\t  "

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("failing-command", debug=False)

        # Should provide a fallback message since whitespace is stripped
        assert "Command failed with exit code 1" in str(exc_info.value)


class TestRunCommandFailureNoCapture:
    """Test suite for failed run_command executions with capture=False."""

    def test_run_command_no_capture_failure_stderr(self):
        """Test command failure without capture, error in stderr."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Deployment failed"

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("deploy", debug=False, capture=False)

        assert "Deployment failed" in str(exc_info.value)

    def test_run_command_no_capture_failure_both(self):
        """Test command failure without capture, error in both streams."""
        mock_result = Mock()
        mock_result.returncode = 2
        mock_result.stdout = "Partial progress made"
        mock_result.stderr = "Then it crashed"

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("risky-operation", debug=False, capture=False)

        error_message = str(exc_info.value)
        assert "Then it crashed" in error_message
        assert "Partial progress made" in error_message

    def test_run_command_no_capture_failure_empty(self):
        """Test command failure without capture, no output."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("silent-failure", debug=False, capture=False)

        assert "Command failed with exit code 1" in str(exc_info.value)


class TestRunCommandDebug:
    """Test suite for run_command with debug mode enabled."""

    def test_run_command_debug_success(self, capsys):
        """Test debug output for successful command."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success output"
        mock_result.stderr = "Debug info"

        with patch('subprocess.run', return_value=mock_result):
            run_command("test-cmd", debug=True)

        captured = capsys.readouterr()
        assert "Exit code: 0" in captured.out
        assert "STDOUT:\nSuccess output" in captured.out
        assert "STDERR:\nDebug info" in captured.out

    def test_run_command_debug_failure(self, capsys):
        """Test debug output for failed command."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Attempted operation"
        mock_result.stderr = "Error occurred"

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception):
                run_command("failing-cmd", debug=True)

        captured = capsys.readouterr()
        assert "Exit code: 1" in captured.out
        assert "STDOUT:\nAttempted operation" in captured.out
        assert "STDERR:\nError occurred" in captured.out

    def test_run_command_debug_empty_streams(self, capsys):
        """Test debug output when streams are empty."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch('subprocess.run', return_value=mock_result):
            run_command("quiet-cmd", debug=True)

        captured = capsys.readouterr()
        assert "Exit code: 0" in captured.out
        # Should not print STDOUT/STDERR labels when empty
        assert "STDOUT:" not in captured.out
        assert "STDERR:" not in captured.out


class TestRunCommandIntegration:
    """Integration-like tests with more realistic scenarios."""

    def test_run_command_prints_command(self, capsys):
        """Test that the command being run is printed."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch('subprocess.run', return_value=mock_result):
            run_command("release-tool pull", debug=False)

        captured = capsys.readouterr()
        assert "Running: release-tool pull" in captured.out

    def test_run_command_multiline_error(self):
        """Test command failure with multiline error message."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = """Error: Multiple issues found
  - Issue 1: Missing configuration
  - Issue 2: Invalid credentials
  - Issue 3: Network timeout"""

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("complex-tool", debug=False)

        error = str(exc_info.value)
        assert "Multiple issues found" in error
        assert "Missing configuration" in error
        assert "Invalid credentials" in error
        assert "Network timeout" in error

    def test_run_command_preserves_newlines(self):
        """Test that newlines in error messages are preserved."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Line 1\nLine 2\nLine 3"
        mock_result.stderr = "Error A\nError B"

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(Exception) as exc_info:
                run_command("some-tool", debug=False)

        error = str(exc_info.value)
        # Both stderr and stdout should be present with newline separator
        assert "Error A\nError B" in error
        assert "Line 1\nLine 2\nLine 3" in error

    def test_run_command_no_capture_success(self):
        """Test successful command without capture."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Build successful"
        mock_result.stderr = ""

        with patch('subprocess.run', return_value=mock_result):
            output = run_command("make build", debug=False, capture=False)

        # capture=False should return empty string on success
        assert output == ""

    def test_run_command_captures_exit_codes(self):
        """Test that different exit codes are properly captured."""
        for exit_code in [1, 2, 127, 255]:
            mock_result = Mock()
            mock_result.returncode = exit_code
            mock_result.stdout = ""
            mock_result.stderr = ""

            with patch('subprocess.run', return_value=mock_result):
                with pytest.raises(Exception) as exc_info:
                    run_command("test", debug=False)

            assert f"Command failed with exit code {exit_code}" in str(exc_info.value)
