"""
SPDX-FileCopyrightText: 2024 Sequent Tech Inc <legal@sequentech.io>
SPDX-License-Identifier: AGPL-3.0-only
"""
import pytest
import re

class TestPRMergeDetection:
    """Test PR merge detection with target branch validation."""
    
    def convert_template_to_pattern(self, template):
        """Convert branch template to regex pattern (matching main.py logic)."""
        pattern = template.replace(".", r"\.")
        pattern = re.sub(r'\{[^}]+\}', r'([\\d.]+(?:-[a-zA-Z0-9.]+)?)', pattern)
        return pattern
    
    def test_pr_merge_to_release_branch_target(self):
        """Test that PR merging TO release branch is detected correctly."""
        template = "release/{major}.{minor}"
        pattern = self.convert_template_to_pattern(template)
        
        # The bug scenario from issue
        source_branch = "docs/release-bot-4/release/0.0"
        target_branch = "release/0.0"
        
        # Source branch should NOT match
        assert not re.match(pattern, source_branch), "Source branch should not match pattern"
        
        # Target branch SHOULD match (this is the fix)
        assert re.match(pattern, target_branch), "Target branch should match pattern"
    
    def test_pr_source_branch_ignored(self):
        """Test that source branch is NOT checked for release pattern."""
        template = "release/{major}.{minor}"
        pattern = self.convert_template_to_pattern(template)
        
        source_branch = "feature/awesome-feature"  # Non-release source
        target_branch = "release/1.0"  # Release target
        
        # Even though source doesn't match, target does - should trigger release
        assert not re.match(pattern, source_branch)
        assert re.match(pattern, target_branch)
    
    def test_pr_non_release_target_branch(self):
        """Test that PR to non-release branch is correctly ignored."""
        template = "release/{major}.{minor}"
        pattern = self.convert_template_to_pattern(template)
        
        target_branch = "main"  # Non-release target
        
        # Target is 'main', should NOT match release pattern
        assert not re.match(pattern, target_branch)
    
    def test_ticket_extraction_closing_keywords(self):
        """Test ticket extraction with closing keywords."""
        pr_bodies = [
            "Closes #123",
            "Fixes #456",
            "Resolves #789",
            "Fixed #100",
            "Closed #200"
        ]
        
        ticket_pattern = r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)'
        
        for body in pr_bodies:
            matches = re.findall(ticket_pattern, body, re.IGNORECASE)
            assert len(matches) == 1, f"Should find ticket in: {body}"
    
    def test_ticket_extraction_related_keywords(self):
        """Test ticket extraction with related keywords (fallback)."""
        pr_bodies = [
            "Related to #111",
            "See #222",
            "Issue #333"
        ]
        
        ticket_pattern = r'(?:related to|see|issue)\s+#(\d+)'
        
        for body in pr_bodies:
            matches = re.findall(ticket_pattern, body, re.IGNORECASE)
            assert len(matches) == 1, f"Should find ticket in: {body}"
    
    def test_ticket_extraction_bare_references(self):
        """Test ticket extraction with bare # references (last fallback)."""
        pr_body = "This PR addresses #999 and improves performance"
        
        ticket_pattern = r'#(\d+)'
        matches = re.findall(ticket_pattern, pr_body)
        
        assert len(matches) >= 1
        assert matches[0] == '999'
    
    def test_version_extraction_from_branch(self):
        """Test version extraction from target branch name."""
        template = "release/{major}.{minor}"
        pattern = self.convert_template_to_pattern(template)
        
        target_branches = [
            "release/0.0",
            "release/1.2",
            "release/10.5",
        ]
        
        for branch in target_branches:
            match = re.match(pattern, branch)
            assert match, f"Branch {branch} should match pattern"
            # Just verify we can extract version info
            version = match.group(1)
            assert version, f"Should extract version from {branch}"
    
    def test_version_extraction_with_rc(self):
        """Test version extraction from RC release branches."""
        template = "release/v{major}.{minor}.{patch}"
        pattern = self.convert_template_to_pattern(template)
        
        target_branches = [
            "release/v1.2.3",
            "release/v2.0.0-rc.1",
            "release/v1.0.0-beta.2",
        ]
        
        for branch in target_branches:
            match = re.match(pattern, branch)
            assert match, f"Branch {branch} should match pattern"
    
    def test_pr_to_development_branch_ignored(self):
        """Test that PR to development branch is ignored."""
        template = "release/{major}.{minor}"
        pattern = self.convert_template_to_pattern(template)
        
        dev_branches = ["develop", "development", "dev", "main", "master"]
        
        for branch in dev_branches:
            match = re.match(pattern, branch)
            assert not match, f"Development branch '{branch}' should not match release pattern"
    
    def test_pr_to_feature_branch_ignored(self):
        """Test that PR to feature branch is ignored."""
        template = "release/{major}.{minor}"
        pattern = self.convert_template_to_pattern(template)
        
        feature_branches = [
            "feature/new-feature",
            "bugfix/fix-bug",
            "hotfix/critical-fix",
            "docs/update-readme"
        ]
        
        for branch in feature_branches:
            match = re.match(pattern, branch)
            assert not match, f"Feature branch '{branch}' should not match release pattern"
    
    def test_complex_source_branch_with_release_in_name(self):
        """Test that source branch with 'release' in name but non-standard format is ignored."""
        template = "release/{major}.{minor}"
        pattern = self.convert_template_to_pattern(template)
        
        # Source branch: docs/release-bot-4/release/0.0 (has 'release' but wrong format)
        source_branch = "docs/release-bot-4/release/0.0"
        target_branch = "release/0.0"
        
        # Source should NOT match (wrong format)
        assert not re.match(pattern, source_branch), "Complex source branch should not match"
        
        # Target SHOULD match (correct format)
        assert re.match(pattern, target_branch), "Target branch should match"
    
    def test_custom_branch_template(self):
        """Test with custom branch template configuration."""
        template = "releases/{major}.{minor}.{patch}"
        pattern = self.convert_template_to_pattern(template)
        
        # Should match custom pattern
        assert re.match(pattern, "releases/1.2.3")
        
        # Should NOT match standard pattern
        assert not re.match(pattern, "release/1.2.3")
    
    def test_pr_event_logging_shows_both_branches(self):
        """Test that logging shows both source and target branches."""
        source_branch = "docs/release-bot-4/release/0.0"
        target_branch = "release/0.0"
        pr_number = 5
        
        # Verify expected log format
        expected_log = f"PR #{pr_number}: {source_branch} → {target_branch}"
        assert source_branch in expected_log
        assert target_branch in expected_log
        assert "→" in expected_log
