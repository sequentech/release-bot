import os
import sys
import json
import subprocess
import shlex
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from github import Github
from release_tool.db import Database
from release_tool.config import load_config
from release_tool.commands.push import _find_draft_releases


@dataclass
class BotInputs:
    """Typed container for all bot input parameters."""
    token: str
    command: Optional[str]
    version: Optional[str]
    new_version_type: Optional[str]
    from_version: Optional[str]
    force: str
    debug: bool
    config_path: Optional[str]
    detect_mode: Optional[str]
    event_path: Optional[str]
    event_name: Optional[str]
    repo_name: str
    ref_name: Optional[str]


@dataclass
class ParsedEvent:
    """Typed container for parsed event data."""
    command: str
    version: Optional[str]
    issue_number: Optional[int]
    event: Dict[str, Any]


@dataclass
class CommandResult:
    """Typed container for command execution results."""
    success: bool
    message: str
    output: Optional[str] = None

def run_command(cmd: str, debug: bool = False, capture: bool = True) -> str:
    """
    Run a shell command.

    Args:
        cmd: Command to run
        debug: Enable debug output
        capture: Capture output instead of streaming (needed when parsing output)
        
    Returns:
        Command stdout output
        
    Raises:
        Exception: If command fails with non-zero exit code
    """
    print(f"Running: {cmd}")

    if capture:
        # Capture output for parsing (e.g., version detection)
        result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)

        if debug:
            print(f"Exit code: {result.returncode}")
            if result.stdout:
                print(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")

        if result.returncode != 0:
            raise Exception(result.stderr)
        return result.stdout
    else:
        # Stream output in real-time (better for CI/CD logs)
        result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)

        # Print output for visibility (before checking error)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            # Capture both stdout and stderr for better error messages
            error_parts = []
            if result.stderr and result.stderr.strip():
                error_parts.append(result.stderr.strip())
            if result.stdout and result.stdout.strip():
                # Sometimes errors are in stdout
                error_parts.append(result.stdout.strip())
            
            error_msg = "\n".join(error_parts) if error_parts else f"Command failed with exit code {result.returncode}"
            raise Exception(error_msg)
        
        return ""

def get_workflow_run_url() -> Optional[str]:
    """Build the GitHub Actions workflow run URL."""
    repo = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    
    if repo and run_id:
        return f"{server_url}/{repo}/actions/runs/{run_id}"
    return None

def post_comment(token: str, repo_name: str, issue_number: int, body: str) -> None:
    """Post a comment to a GitHub issue or PR."""
    from github import Auth
    auth = Auth.Token(token)
    g = Github(auth=auth)
    repo = g.get_repo(repo_name)
    issue = repo.get_issue(issue_number)
    
    # Add workflow run link if available
    run_url = get_workflow_run_url()
    if run_url:
        body = f"{body}\n\n<sub>[View workflow run details]({run_url})</sub>"
    
    issue.create_comment(body)

def get_version_from_issue(repo_name: str, issue_number: int, token: Optional[str] = None) -> Optional[str]:
    """Get version from issue by checking database and parsing issue title."""
    print(f"[get_version_from_issue] Looking up version for {repo_name} issue #{issue_number}")

    # First try: Check if this issue is associated with a version in release_issues
    print("[get_version_from_issue] Step 1: Checking release_issues database table...")
    try:
        db = Database()
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT version FROM release_issues WHERE repo_full_name=? AND issue_number=?",
            (repo_name, issue_number)
        )
        row = cursor.fetchone()
        db.close()
        if row:
            print(f"[get_version_from_issue] ✓ Found version in database: {row[0]}")
            return row[0]
        else:
            print("[get_version_from_issue] ✗ No database association found")
    except Exception as e:
        print(f"[get_version_from_issue] ✗ Error querying database: {e}")

    # Second try: Parse version from issue title (e.g., "✨ Prepare Release 0.0.1-rc.0")
    if token:
        print("[get_version_from_issue] Step 2: Fetching issue from GitHub to parse title...")
        try:
            from github import Auth
            auth = Auth.Token(token)
            g = Github(auth=auth)
            repo = g.get_repo(repo_name)
            issue = repo.get_issue(issue_number)

            print(f"[get_version_from_issue] Issue title: '{issue.title}'")

            # Try to extract version from title using regex
            # Matches patterns like "0.0.1-rc.0", "1.2.3", "v1.2.3", etc.
            import re
            print("[get_version_from_issue] Attempting to extract version with regex pattern: v?([0-9]+\\.[0-9]+\\.[0-9]+(?:-[a-zA-Z0-9.]+)?)")
            version_match = re.search(r'v?([0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?)', issue.title)
            if version_match:
                version = version_match.group(1)  # Use group 1, not 0
                print(f"[get_version_from_issue] ✓ Extracted version from title: {version}")
                return version
            else:
                print("[get_version_from_issue] ✗ No version pattern found in issue title")
        except Exception as e:
            print(f"[get_version_from_issue] ✗ Error fetching issue details: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[get_version_from_issue] ✗ No GitHub token available, skipping title parsing")

    print("[get_version_from_issue] Failed to determine version from issue")
    return None

def get_version_from_drafts(config_path: Optional[str]) -> Optional[str]:
    """Extract version from draft release files."""
    try:
        # Load config (will use default path if None)
        config = load_config(config_path)
        draft_files = _find_draft_releases(config)
        if draft_files:
            # Use the newest draft file
            first_file = draft_files[0]
            filename = first_file.stem
            version_str = filename
            if filename.endswith("-doc"):
                version_str = filename[:-4]
            elif filename.endswith("-release"):
                version_str = filename[:-8]
            print(f"Detected version {version_str} from draft file: {first_file.name}")
            return version_str
        else:
            print("No draft files found")
    except Exception as e:
        print(f"Warning: Failed to detect version from draft files: {e}")
        import traceback
        traceback.print_exc()
    return None

def setup_workspace() -> Optional[str]:
    """Setup the GitHub workspace and return its path."""
    workspace = os.getenv("GITHUB_WORKSPACE")
    if workspace:
        # Fix for dubious ownership error in GitHub Actions
        try:
            subprocess.run(["git", "config", "--global", "--add", "safe.directory", workspace], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to set safe.directory: {e}")
        os.chdir(workspace)
    return workspace

def get_inputs() -> BotInputs:
    """
    Load and parse all input parameters from environment variables.
    
    Returns:
        BotInputs instance with all parsed parameters
    """
    token = os.getenv("INPUT_GITHUB_TOKEN")
    if not token:
        token = os.getenv("GITHUB_TOKEN")

    if token:
        os.environ["GITHUB_TOKEN"] = token
    
    debug_env = os.getenv("INPUT_DEBUG", "true")
    
    return BotInputs(
        token=token or "",
        command=os.getenv("INPUT_COMMAND"),
        version=os.getenv("INPUT_VERSION"),
        new_version_type=os.getenv("INPUT_NEW_VERSION_TYPE"),
        from_version=os.getenv("INPUT_FROM_VERSION"),
        force=os.getenv("INPUT_FORCE", "none"),
        debug=debug_env.lower() == "true" if debug_env else True,
        config_path=os.getenv("INPUT_CONFIG_PATH"),
        detect_mode=os.getenv("INPUT_DETECT_MODE"),
        event_path=os.getenv("GITHUB_EVENT_PATH"),
        event_name=os.getenv("GITHUB_EVENT_NAME"),
        repo_name=os.getenv("GITHUB_REPOSITORY", ""),
        ref_name=os.getenv("GITHUB_REF_NAME")
    )

def parse_event(inputs: BotInputs) -> ParsedEvent:
    """
    Parse GitHub event and extract command, version, and issue number.
    
    Args:
        inputs: Bot input parameters
        
    Returns:
        ParsedEvent with extracted information
    """
    event_path = inputs.event_path
    event_name = inputs.event_name
    command = inputs.command
    version = inputs.version
    issue_number: Optional[int] = None
    
    # Load event data
    if event_path and os.path.exists(event_path):
        with open(event_path) as f:
            event = json.load(f)
    else:
        event = {}

    # Handle ChatOps (Issue Comment)
    if event_name == "issue_comment":
        comment_body = event["comment"]["body"]
        issue_number = event["issue"]["number"]
        
        if not comment_body.startswith("/release-bot"):
            print("Not a release command.")
            sys.exit(0)
            
        parts = comment_body.strip().split()
        if len(parts) < 2:
            print("Invalid command format.")
            sys.exit(1)
            
        command = parts[1]
        
        # Parse key=value parameters
        valid_params = {
            "version": ["string"],
            "new_version_type": ["none", "patch", "minor", "major", "rc"],
            "from_version": ["string"],
            "force": ["none", "draft", "published"],
            "debug": ["true", "false"]
        }
        
        # Process remaining parts as either version or key=value pairs
        for i in range(2, len(parts)):
            part = parts[i]
            if "=" in part:
                key, value = part.split("=", 1)
                if key not in valid_params:
                    error_msg = f"❌ Invalid parameter: '{key}'\n\nValid parameters: {', '.join(valid_params.keys())}"
                    print(error_msg)
                    if inputs.token:
                        post_comment(inputs.token, inputs.repo_name, issue_number, error_msg)
                    sys.exit(1)
                
                # Validate value
                allowed_values = valid_params[key]
                if allowed_values != ["string"] and value.lower() not in allowed_values:
                    error_msg = f"❌ Invalid value for '{key}': '{value}'\n\nAllowed values: {', '.join(allowed_values)}"
                    print(error_msg)
                    if inputs.token:
                        post_comment(inputs.token, inputs.repo_name, issue_number, error_msg)
                    sys.exit(1)
                
                # Set the input value
                if key == "debug":
                    inputs.debug = value.lower() == "true"
                elif key == "version":
                    inputs.version = value
                elif key == "new_version_type":
                    inputs.new_version_type = value
                elif key == "from_version":
                    inputs.from_version = value
                elif key == "force":
                    inputs.force = value
                print(f"Set {key}={value}")
            else:
                # Assume it's a version if it looks like a version string
                if not version:
                    version = part
        
        # Map 'update' to workflow-like behavior
        if command == "update":
            command = "update"

    # Handle PR Merge (Auto-Push)
    elif event_name == "pull_request":
        action = event.get("action")
        merged = event.get("pull_request", {}).get("merged")
        if action == "closed" and merged:
            pr_data = event["pull_request"]
            pr_number = pr_data.get("number")
            source_branch = pr_data["head"]["ref"]
            target_branch = pr_data["base"]["ref"]
            pr_title = pr_data.get("title", "")
            pr_body = pr_data.get("body", "") or ""
            print(f"PR #{pr_number}: {source_branch} → {target_branch}")
            
            # Load config to get branch pattern
            try:
                config = load_config(inputs.config_path)
                branch_template = config.branch_policy.release_branch_template
                # Convert Jinja2 template to regex pattern
                # e.g., "release/{major}.{minor}" -> r"release/(\d+)\.(\d+)"
                # e.g., "release/v{major}.{minor}.{patch}" -> r"release/v(\d+)\.(\d+)\.(\d+)"
                pattern = branch_template.replace(".", r"\.")
                pattern = re.sub(r'\{[^}]+\}', r'([\\d.]+(?:-[a-zA-Z0-9.]+)?)', pattern)
                print(f"Using branch pattern from config: {branch_template} -> {pattern}")
            except Exception as e:
                # Fallback to default pattern if config loading fails
                pattern = r"release/v?(.+)"
                print(f"Warning: Could not load config, using default pattern: {e}")
            
            # Check if target branch (where PR merges TO) is a release branch
            match = re.match(pattern, target_branch)
            if match:
                # Extract version from all captured groups
                version = match.group(1) if match.lastindex == 1 else '.'.join(g for g in match.groups() if g)
                command = "push"
                print(f"Detected release PR merge for version {version} (PR #{pr_number})")
                
                # Try to extract associated issue from PR
                # Method 1: Look for closing keywords in PR body (e.g., "Closes #123", "Fixes #456")
                issue_pattern = r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)'
                issue_matches = re.findall(issue_pattern, pr_body, re.IGNORECASE)

                # Method 2: Look for issue references in PR body (e.g., "Related to #123")
                if not issue_matches:
                    issue_pattern = r'(?:related to|see|issue)\s+#(\d+)'
                    issue_matches = re.findall(issue_pattern, pr_body, re.IGNORECASE)

                # Method 3: Look for bare issue references (e.g., "#123")
                if not issue_matches:
                    issue_pattern = r'#(\d+)'
                    issue_matches = re.findall(issue_pattern, pr_body)

                # Use the first found issue
                if issue_matches:
                    issue_number = int(issue_matches[0])
                    print(f"Found associated issue from PR body: #{issue_number}")
                
                # Fallback: Try to extract version from PR title if branch version seems incomplete
                # Pattern: "Release v1.2.3" or "Prepare Release 1.2.3-rc.0"
                if not version or version == "":
                    version_match = re.search(r'v?([0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?)', pr_title)
                    if version_match:
                        version = version_match.group(1)
                        print(f"Extracted version from PR title: {version}")
            else:
                print(f"PR merged to '{target_branch}' which does not match release pattern '{pattern}'. Exiting.")
                sys.exit(0)
        else:
            print(f"Pull request event {action} (merged={merged}) ignored.")
            sys.exit(0)

    # Handle Issue Close (Auto-Push)
    elif event_name == "issues":
        if event.get("action") == "closed":
            issue_number = event["issue"]["number"]
            command = "push"
            print(f"Issue #{issue_number} closed. Attempting to push.")
        else:
            print(f"Issue event {event.get('action')} ignored.")
            sys.exit(0)
            
    elif event_name == "workflow_dispatch":
        # Manual trigger: Pull -> Generate -> Push
        command = "workflow_dispatch"
        
    elif not command:
        print(f"Event {event_name} not handled and no command provided.")
        sys.exit(0)
        
    return ParsedEvent(
        command=command,
        version=version,
        issue_number=issue_number,
        event=event
    )

def setup_git(token: str, repo_name: str) -> None:
    """Configure git credentials and remote URL."""
    subprocess.run(["git", "config", "--global", "user.name", "Release Bot"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "release-bot@sequentech.io"], check=True)
    repo_url = f"https://x-access-token:{token}@github.com/{repo_name}.git"
    subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)

def checkout_pr_branch(token: str, repo_name: str, issue_number: int) -> str:
    """
    Checkout the branch associated with a pull request.
    
    Returns:
        The name of the checked out branch
    """
    from github import Auth
    auth = Auth.Token(token)
    g = Github(auth=auth)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(issue_number)
    current_branch = pr.head.ref
    print(f"Checking out PR branch: {current_branch}")
    subprocess.run(["git", "fetch", "origin", current_branch], check=True)
    subprocess.run(["git", "checkout", current_branch], check=True)
    return current_branch

def handle_workflow_dispatch(
    base_cmd: str,
    version: Optional[str],
    new_version_type: Optional[str],
    from_version: Optional[str],
    force: str,
    debug: bool,
    config_path: Optional[str],
    detect_mode: Optional[str] = None,
    issue: Optional[int] = None
) -> str:
    """
    Handle workflow_dispatch event: generate and publish release.
    
    Returns:
        Success message
        
    Raises:
        Exception: If version cannot be determined or command fails
    """
    if debug:
        print(f"[DEBUG] handle_workflow_dispatch called with force='{force}'")
    
    # 1. Generate
    gen_cmd = f"{base_cmd} generate"
    if version:
        gen_cmd += f" {version}"
        # Support partial version + bump type (e.g., "0.0.1 --new rc" → "0.0.1-rc.1")
        if new_version_type and new_version_type.lower() != "none":
            gen_cmd += f" --new {new_version_type}"
    elif new_version_type and new_version_type.lower() != "none":
        gen_cmd += f" --new {new_version_type}"
    else:
        # If no version or new_version_type, generate will auto-detect
        pass

    if from_version:
        gen_cmd += f" --from-version {from_version}"
    
    if detect_mode:
        gen_cmd += f" --detect-mode {detect_mode}"

    print(f"Generating release notes with command: {gen_cmd}")
    output = run_command(gen_cmd, debug=debug)
    if output:
        print(output)
    
    # 2. Determine version for push
    # Always detect from draft files after generation, since --new flags can modify the version
    # (e.g., "0.0.1 --new rc" creates "0.0.1-rc.0", not "0.0.1")
    publish_version = get_version_from_drafts(config_path)

    if publish_version:
        print(f"Using version for push: {publish_version}")
    else:
        raise Exception("Could not determine version. No draft files found after generation. " +
                       "Please check the generate command output for errors.")

    # 3. Push (respects config's release_mode setting)
    pub_cmd = f"{base_cmd} push {publish_version}"
    if debug:
        print(f"[DEBUG] Checking force parameter: force='{force}', condition result: {force and force.lower() != 'none'}")
    if force and force.lower() != "none":
        pub_cmd += f" --force {force}"
        if debug:
            print(f"[DEBUG] Added --force {force} to command")
    
    # Add issue number if provided
    if issue:
        pub_cmd += f" --issue {issue}"
        if debug:
            print(f"[DEBUG] Added --issue {issue} to command")

    print(f"Pushing release {publish_version}...")
    output = run_command(pub_cmd, debug=debug)
    if output:
        print(output)
    return f"✅ Release {publish_version} processed successfully."

def handle_generate(base_cmd: str, command: str, version: Optional[str], debug: bool, current_branch: str) -> str:
    """
    Handle generate command: create release notes.
    
    Returns:
        Status message about changes
    """
    cmd = f"{base_cmd} generate"
    if version:
        if version.lower() in ['major', 'minor', 'patch', 'rc']:
            cmd += f" --new {version}"
        else:
            cmd += f" {version}"
    run_command(cmd, debug=debug)

    # Commit and push changes if any
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if status.stdout.strip():
        print("Committing changes...")
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: update release notes ({command})"], check=True)
        print(f"Pushing to {current_branch}...")
        subprocess.run(["git", "push", "origin", current_branch], check=True)
        return "✅ Changes committed and pushed."
    else:
        return "(No changes to commit)"

def handle_push(base_cmd: str, version: str, event_name: str, debug: bool) -> str:
    """
    Handle publish command: push a release.
    
    Returns:
        Success message
    """
    cmd = f"{base_cmd} push {version}"
    # If auto-pushing closed issue, force published mode
    # Note: PR merges are handled separately with mark-published mode
    if event_name == "issues":
            cmd += " --release-mode published"

    run_command(cmd, debug=debug)
    return "✅ Pushed successfully."

def handle_list(base_cmd: str, debug: bool) -> str:
    """
    Handle list command: show available releases.

    Returns:
        Success message
    """
    cmd = f"{base_cmd} publish --list"
    run_command(cmd, debug=debug)
    return "✅ List command completed."

def handle_merge(
    base_cmd: str,
    version: Optional[str],
    issue_number: Optional[int],
    pr_number: Optional[int],
    debug: bool
) -> str:
    """
    Handle merge command: merge PR, mark release as published, close issue.

    Args:
        base_cmd: The base release-tool command
        version: Optional version (can be partial)
        issue_number: Optional issue number
        pr_number: Optional PR number
        debug: Enable debug output

    Returns:
        Success message
    """
    cmd = f"{base_cmd} merge"

    if version:
        cmd += f" {version}"

    if issue_number:
        cmd += f" --issue {issue_number}"

    if pr_number:
        cmd += f" --pr {pr_number}"

    print(f"Executing merge command...")
    run_command(cmd, debug=debug)
    return "✅ Merge completed successfully."

def resolve_version_from_context(
    command: str,
    version: Optional[str],
    issue_number: Optional[int],
    repo_name: str,
    event_name: str,
    token: str
) -> Optional[str]:
    """
    Resolve version from issue if missing for commands that require it.

    Args:
        command: The command being executed
        version: The version provided (may be None)
        issue_number: The issue number
        repo_name: The repository name
        event_name: The GitHub event name
        token: GitHub token for posting comments

    Returns:
        The resolved version string

    Raises:
        SystemExit: If version cannot be resolved
    """
    if command in ["push", "update"] and not version:
        if issue_number:
            version = get_version_from_issue(repo_name, issue_number, token)
            if not version:
                msg = f"❌ Could not find a release version associated with issue #{issue_number}.\nPlease specify version explicitly or ensure the issue title contains the version (e.g., 'Prepare Release 1.2.3')."
                print(msg)
                if event_name == "issue_comment":
                    post_comment(token, repo_name, issue_number, msg)
                sys.exit(1)
            print(f"Resolved version {version} from issue #{issue_number}")
        else:
            print(f"❌ Version is required for {command}.")
            sys.exit(1)
    return version

def build_base_command(config_path: Optional[str], debug: bool) -> str:
    """
    Build the base release-tool command with appropriate flags.
    
    Args:
        config_path: Path to the config file
        debug: Whether debug mode is enabled
        
    Returns:
        The base command string
    """
    base_cmd = "release-tool --auto"
    if config_path:
        base_cmd += f" --config {config_path}"
    if debug:
        base_cmd += " --debug"
    return base_cmd

def run_pull(
    base_cmd: str,
    debug: bool,
    issue_number: Optional[int],
    event_name: str,
    token: str,
    repo_name: str
) -> None:
    """
    Run the pull command and handle errors.

    Args:
        base_cmd: The base release-tool command
        debug: Whether debug mode is enabled
        issue_number: The issue number (for error reporting)
        event_name: The GitHub event name
        token: GitHub token for posting comments
        repo_name: The repository name

    Raises:
        SystemExit: If pull fails
    """
    try:
        print("Pulling...")
        run_command(f"{base_cmd} pull", debug=debug)
        print("✅ Pull completed successfully")
    except Exception as e:
        msg = f"❌ Pull failed:\n```\n{e}\n```"
        print(msg)
        if issue_number and event_name == "issue_comment":
            post_comment(token, repo_name, issue_number, msg)
        sys.exit(1)

def main() -> None:
    """
    Main entry point for the release bot.
    
    Keep this function simple and focused on orchestration.
    Move complex logic into dedicated subfunctions.
    """
    # Ensure we are in the workspace
    workspace = setup_workspace()

    # Get inputs (with defaults applied)
    inputs = get_inputs()
    debug = inputs.debug
    
    # Debug output
    if debug:
        print(f"[DEBUG] Workspace: {workspace}")
    
    parsed = parse_event(inputs)
    command = parsed.command
    version = parsed.version
    issue_number = parsed.issue_number
    event = parsed.event

    print(f"Starting Release Bot. Command: {command}, Version: {version}")
    
    if debug:
        print(f"[DEBUG] inputs.force from environment: '{inputs.force}' (type: {type(inputs.force).__name__})")
    
    # Setup Git
    setup_git(inputs.token, inputs.repo_name)

    current_branch = os.getenv("GITHUB_REF_NAME") or "main"
    
    # If PR comment, checkout the PR branch
    if inputs.event_name == "issue_comment" and "pull_request" in event.get("issue", {}):
        current_branch = checkout_pr_branch(inputs.token, inputs.repo_name, issue_number)

    # Build base command
    base_cmd = build_base_command(inputs.config_path, debug)

    # Stateless: Always pull first
    run_pull(base_cmd, debug, issue_number, inputs.event_name, inputs.token, inputs.repo_name)

    # Resolve version from context if needed
    version = resolve_version_from_context(
        command, 
        version, 
        issue_number, 
        inputs.repo_name, 
        inputs.event_name,
        inputs.token
    )

    # Execute command
    try:
        output = ""
        if command == "workflow_dispatch":
            output = handle_workflow_dispatch(
                base_cmd,
                version,
                inputs.new_version_type,
                inputs.from_version,
                inputs.force,
                debug,
                inputs.config_path,
                detect_mode=inputs.detect_mode,
                issue=issue_number
            )

        elif command == "update":
            # Update behaves like workflow_dispatch: generate + publish
            # For update, force should default to "draft" if not explicitly set
            force_mode = inputs.force if (inputs.force and inputs.force.lower() != "none") else "draft"
            if debug:
                print(f"[DEBUG] Update command: inputs.force='{inputs.force}', force_mode='{force_mode}'")
                if issue_number:
                    print(f"[DEBUG] Using issue_number={issue_number} as issue")
            output = handle_workflow_dispatch(
                base_cmd,
                version,
                inputs.new_version_type,
                inputs.from_version,
                force_mode,
                debug,
                inputs.config_path,
                detect_mode=inputs.detect_mode,
                issue=issue_number
            )

        elif command == "push":
            if not version:
                raise Exception("Version is required for publish command")
            # For PR merge events, use mark-published mode and associate issue
            if inputs.event_name == "pull_request":
                pub_cmd = f"{base_cmd} push {version} --release-mode mark-published"
                if issue_number:
                    pub_cmd += f" --issue {issue_number}"
                    if debug:
                        print(f"[DEBUG] Publishing with issue #{issue_number}")
                if debug:
                    print(f"[DEBUG] Using mark-published mode for PR merge")
                print(f"Pushing release {version}...")
                output_text = run_command(pub_cmd, debug=debug)
                if output_text:
                    print(output_text)
                output = f"✅ Release {version} marked as published successfully."
            else:
                output = handle_push(base_cmd, version, inputs.event_name, debug)
        
        elif command == "generate":
            output = handle_generate(base_cmd, command, version, debug, current_branch)

        elif command == "list":
             output = handle_list(base_cmd, debug)

        elif command == "merge":
            # Extract PR number if available from parsed event
            pr_number = event.get("pull_request", {}).get("number") if event else None
            output = handle_merge(base_cmd, version, issue_number, pr_number, debug)

        else:
            raise Exception(f"Unknown command: {command}")
            
        print(output)
        if issue_number and inputs.event_name == "issue_comment":
            post_comment(
                inputs.token,
                inputs.repo_name,
                issue_number,
                f"✅ Command `{command}` succeeded:\n\n{output}"
            )
            
    except Exception as e:
        import traceback
        error_details = str(e) if str(e) else traceback.format_exc()
        msg = f"❌ Command `{command}` failed:\n```\n{error_details}\n```"
        print(msg)
        print("Full traceback:")
        traceback.print_exc()
        if issue_number and inputs.event_name == "issue_comment":
            post_comment(inputs.token, inputs.repo_name, issue_number, msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
