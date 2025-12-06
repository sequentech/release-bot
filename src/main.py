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
from release_tool.commands.publish import _find_draft_releases


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

def get_version_from_ticket(repo_name: str, ticket_number: int, token: Optional[str] = None) -> Optional[str]:
    """Get version from ticket by checking database and parsing ticket title."""
    print(f"[get_version_from_ticket] Looking up version for {repo_name} ticket #{ticket_number}")
    
    # First try: Check if this ticket is associated with a version in release_tickets
    print("[get_version_from_ticket] Step 1: Checking release_tickets database table...")
    try:
        db = Database()
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT version FROM release_tickets WHERE repo_full_name=? AND ticket_number=?",
            (repo_name, ticket_number)
        )
        row = cursor.fetchone()
        db.close()
        if row:
            print(f"[get_version_from_ticket] ✓ Found version in database: {row[0]}")
            return row[0]
        else:
            print("[get_version_from_ticket] ✗ No database association found")
    except Exception as e:
        print(f"[get_version_from_ticket] ✗ Error querying database: {e}")
    
    # Second try: Parse version from ticket title (e.g., "✨ Prepare Release 0.0.1-rc.0")
    if token:
        print("[get_version_from_ticket] Step 2: Fetching ticket from GitHub to parse title...")
        try:
            from github import Auth
            auth = Auth.Token(token)
            g = Github(auth=auth)
            repo = g.get_repo(repo_name)
            issue = repo.get_issue(ticket_number)
            
            print(f"[get_version_from_ticket] Ticket title: '{issue.title}'")
            
            # Try to extract version from title using regex
            # Matches patterns like "0.0.1-rc.0", "1.2.3", "v1.2.3", etc.
            import re
            print("[get_version_from_ticket] Attempting to extract version with regex pattern: v?([0-9]+\\.[0-9]+\\.[0-9]+(?:-[a-zA-Z0-9.]+)?)")
            version_match = re.search(r'v?([0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?)', issue.title)
            if version_match:
                version = version_match.group(1)  # Use group 1, not 0
                print(f"[get_version_from_ticket] ✓ Extracted version from title: {version}")
                return version
            else:
                print("[get_version_from_ticket] ✗ No version pattern found in ticket title")
        except Exception as e:
            print(f"[get_version_from_ticket] ✗ Error fetching ticket details: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[get_version_from_ticket] ✗ No GitHub token available, skipping title parsing")
    
    print("[get_version_from_ticket] Failed to determine version from ticket")
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

    # Handle PR Merge (Auto-Publish)
    elif event_name == "pull_request":
        action = event.get("action")
        merged = event.get("pull_request", {}).get("merged")
        if action == "closed" and merged:
            # Check if it's a release PR
            branch_name = event["pull_request"]["head"]["ref"]
            # Assuming release branch format: release/vX.Y.Z or release/X.Y.Z
            match = re.match(r"release/v?(.+)", branch_name)
            if match:
                version = match.group(1)
                command = "publish"
                print(f"Detected release PR merge for version {version}")
            else:
                print("PR merged but not a release branch. Exiting.")
                sys.exit(0)
        else:
            print(f"Pull request event {action} (merged={merged}) ignored.")
            sys.exit(0)

    # Handle Issue Close (Auto-Publish)
    elif event_name == "issues":
        if event.get("action") == "closed":
            issue_number = event["issue"]["number"]
            command = "publish"
            print(f"Issue #{issue_number} closed. Attempting to publish.")
        else:
            print(f"Issue event {event.get('action')} ignored.")
            sys.exit(0)
            
    elif event_name == "workflow_dispatch":
        # Manual trigger: Sync -> Generate -> Publish
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
    config_path: Optional[str]
) -> str:
    """
    Handle workflow_dispatch event: generate and publish release.
    
    Returns:
        Success message
        
    Raises:
        Exception: If version cannot be determined or command fails
    """
    # 1. Generate
    gen_cmd = f"{base_cmd} generate"
    if version:
        gen_cmd += f" {version}"
    elif new_version_type and new_version_type.lower() != "none":
        gen_cmd += f" --new {new_version_type}"
    else:
        # If no version or new_version_type, generate will auto-detect
        pass

    if from_version:
        gen_cmd += f" --from-version {from_version}"

    print(f"Generating release notes with command: {gen_cmd}")
    output = run_command(gen_cmd, debug=debug)
    if output:
        print(output)
    
    # 2. Determine version for publish
    publish_version = version if version else get_version_from_drafts(config_path)

    if publish_version:
        print(f"Using version for publish: {publish_version}")
    else:
        raise Exception("Could not determine version. No draft files found and no version specified. " +
                       "Please specify a version or ensure release notes are generated first.")

    # 3. Publish (respects config's release_mode setting)
    pub_cmd = f"{base_cmd} publish {publish_version}"
    if force and force.lower() != "none":
        pub_cmd += f" --force {force}"

    print(f"Publishing release {publish_version}...")
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

def handle_publish(base_cmd: str, version: str, event_name: str, debug: bool) -> str:
    """
    Handle publish command: publish a release.
    
    Returns:
        Success message
    """
    cmd = f"{base_cmd} publish {version}"
    # If auto-publishing (merged PR or closed issue), force published mode
    if event_name in ["pull_request", "issues"]:
            cmd += " --release-mode published"

    run_command(cmd, debug=debug)
    return "✅ Published successfully."

def handle_list(base_cmd: str, debug: bool) -> str:
    """
    Handle list command: show available releases.
    
    Returns:
        Success message
    """
    cmd = f"{base_cmd} publish --list"
    run_command(cmd, debug=debug)
    return "✅ List command completed."

def resolve_version_from_context(
    command: str,
    version: Optional[str],
    issue_number: Optional[int],
    repo_name: str,
    event_name: str,
    token: str
) -> Optional[str]:
    """
    Resolve version from ticket if missing for commands that require it.
    
    Args:
        command: The command being executed
        version: The version provided (may be None)
        issue_number: The issue/ticket number
        repo_name: The repository name
        event_name: The GitHub event name
        token: GitHub token for posting comments
        
    Returns:
        The resolved version string
        
    Raises:
        SystemExit: If version cannot be resolved
    """
    if command in ["publish", "update"] and not version:
        if issue_number:
            version = get_version_from_ticket(repo_name, issue_number, token)
            if not version:
                msg = f"❌ Could not find a release version associated with ticket #{issue_number}.\nPlease specify version explicitly or ensure the ticket title contains the version (e.g., 'Prepare Release 1.2.3')."
                print(msg)
                if event_name == "issue_comment":
                    post_comment(token, repo_name, issue_number, msg)
                sys.exit(1)
            print(f"Resolved version {version} from ticket #{issue_number}")
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

def run_sync(
    base_cmd: str,
    debug: bool,
    issue_number: Optional[int],
    event_name: str,
    token: str,
    repo_name: str
) -> None:
    """
    Run the sync command and handle errors.
    
    Args:
        base_cmd: The base release-tool command
        debug: Whether debug mode is enabled
        issue_number: The issue/ticket number (for error reporting)
        event_name: The GitHub event name
        token: GitHub token for posting comments
        repo_name: The repository name
        
    Raises:
        SystemExit: If sync fails
    """
    try:
        print("Syncing...")
        run_command(f"{base_cmd} sync", debug=debug)
        print("✅ Sync completed successfully")
    except Exception as e:
        msg = f"❌ Sync failed:\n```\n{e}\n```"
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
    
    # Setup Git
    setup_git(inputs.token, inputs.repo_name)

    current_branch = os.getenv("GITHUB_REF_NAME") or "main"
    
    # If PR comment, checkout the PR branch
    if inputs.event_name == "issue_comment" and "pull_request" in event.get("issue", {}):
        current_branch = checkout_pr_branch(inputs.token, inputs.repo_name, issue_number)

    # Build base command
    base_cmd = build_base_command(inputs.config_path, debug)

    # Stateless: Always sync first
    run_sync(base_cmd, debug, issue_number, inputs.event_name, inputs.token, inputs.repo_name)

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
                inputs.config_path
            )

        elif command == "update":
            # Update behaves like workflow_dispatch: generate + publish
            # For update, force should default to "draft" if not explicitly set
            force_mode = inputs.force if inputs.force != "none" else "draft"
            output = handle_workflow_dispatch(
                base_cmd,
                version,
                inputs.new_version_type,
                inputs.from_version,
                force_mode,
                debug,
                inputs.config_path
            )

        elif command == "publish":
            if not version:
                raise Exception("Version is required for publish command")
            output = handle_publish(base_cmd, version, inputs.event_name, debug)
        
        elif command == "generate":
            output = handle_generate(base_cmd, command, version, debug, current_branch)

        elif command == "list":
             output = handle_list(base_cmd, debug)
        
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
