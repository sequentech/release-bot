import os
import sys
import json
import subprocess
import shlex
import re
from github import Github
from release_tool.db import Database

def run_command(cmd, debug=False, capture=True):
    """
    Run a shell command.

    Args:
        cmd: Command to run
        debug: Enable debug output
        capture: Capture output instead of streaming (needed when parsing output)
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
        result = subprocess.run(shlex.split(cmd), text=True)

        if result.returncode != 0:
            raise Exception(f"Command failed with exit code {result.returncode}")
        return ""

def post_comment(token, repo_name, issue_number, body):
    g = Github(token)
    repo = g.get_repo(repo_name)
    issue = repo.get_issue(issue_number)
    issue.create_comment(body)

def get_version_from_ticket(repo_name, ticket_number):
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
            return row[0]
    except Exception as e:
        print(f"Error querying database: {e}")
    return None

def main():
    # Ensure we are in the workspace
    workspace = os.getenv("GITHUB_WORKSPACE")
    if workspace:
        # Fix for dubious ownership error in GitHub Actions
        try:
            subprocess.run(["git", "config", "--global", "--add", "safe.directory", workspace], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to set safe.directory: {e}")
        os.chdir(workspace)

    token = os.getenv("INPUT_GITHUB_TOKEN")
    if not token:
        token = os.getenv("GITHUB_TOKEN")

    if token:
        os.environ["GITHUB_TOKEN"] = token

    command = os.getenv("INPUT_COMMAND")
    version = os.getenv("INPUT_VERSION")
    new_version_type = os.getenv("INPUT_NEW_VERSION_TYPE")
    from_version = os.getenv("INPUT_FROM_VERSION")
    force = os.getenv("INPUT_FORCE", "none")
    debug = os.getenv("INPUT_DEBUG", "false").lower() == "true"
    config_path = os.getenv("INPUT_CONFIG_PATH")

    # Debug output
    if debug:
        print(f"[DEBUG] Token status: {'Present' if token else 'Missing'}")
        if token:
            print(f"[DEBUG] Token length: {len(token)} chars")
            print(f"[DEBUG] Token prefix: {token[:7]}..." if len(token) > 7 else "[DEBUG] Token too short")
        print(f"[DEBUG] Config path: {config_path}")
        print(f"[DEBUG] Command: {command}")
        print(f"[DEBUG] Version: {version}")
        print(f"[DEBUG] New version type: {new_version_type}")
        print(f"[DEBUG] Workspace: {workspace}")
    
    event_path = os.getenv("GITHUB_EVENT_PATH")
    event_name = os.getenv("GITHUB_EVENT_NAME")
    repo_name = os.getenv("GITHUB_REPOSITORY")
    
    issue_number = None
    
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
        
        if not comment_body.startswith("/release"):
            print("Not a release command.")
            sys.exit(0)
            
        parts = comment_body.strip().split()
        if len(parts) < 2:
            print("Invalid command format.")
            sys.exit(1)
            
        command = parts[1]
        if len(parts) > 2:
            version = parts[2]

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

    print(f"Starting Release Bot. Command: {command}, Version: {version}")
    
    # Setup Git
    subprocess.run(["git", "config", "--global", "user.name", "Release Bot"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "release-bot@sequentech.io"], check=True)
    repo_url = f"https://x-access-token:{token}@github.com/{repo_name}.git"
    subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)

    current_branch = os.getenv("GITHUB_REF_NAME")
    
    # If PR comment, checkout the PR branch
    if event_name == "issue_comment" and "pull_request" in event["issue"]:
        g = Github(token)
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(issue_number)
        current_branch = pr.head.ref
        print(f"Checking out PR branch: {current_branch}")
        subprocess.run(["git", "fetch", "origin", current_branch], check=True)
        subprocess.run(["git", "checkout", current_branch], check=True)

    base_cmd = "release-tool --auto"
    if config_path:
        base_cmd += f" --config {config_path}"
    
    # Add --debug flag to base command if debug is enabled
    if debug:
        base_cmd += " --debug"

    # Stateless: Always sync first
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

    # Resolve version if missing for publish
    if command == "publish" and not version:
        if issue_number:
            version = get_version_from_ticket(repo_name, issue_number)
            if not version:
                msg = f"❌ Could not find a release version associated with ticket #{issue_number}."
                print(msg)
                if event_name == "issue_comment":
                    post_comment(token, repo_name, issue_number, msg)
                sys.exit(1)
            print(f"Resolved version {version} from ticket #{issue_number}")
        else:
             print("❌ Version is required for publish.")
             sys.exit(1)

    # Execute command
    try:
        output = ""
        if command == "workflow_dispatch":
            # 1. Generate
            gen_cmd = f"{base_cmd} generate"
            if version:
                gen_cmd += f" {version}"
            if new_version_type and new_version_type.lower() != "none":
                gen_cmd += f" --new {new_version_type}"

            if from_version:
                gen_cmd += f" --from-version {from_version}"

            print(f"Generating release notes...")
            gen_output = run_command(gen_cmd, debug=debug)
            
            # 2. Determine version for publish
            # If version was explicit, use it.
            # If auto-bumped, we need to find it.
            publish_version = version
            if not publish_version:
                # Try to parse from output: "Generated release notes for [bold]1.2.3[/bold]"
                # Or "Release notes written to: .../1.2.3.md"
                match = re.search(r"Generated release notes for .*?(\d+\.\d+\.\d+(?:-\w+\.\d+)?)", gen_output)
                if not match:
                    # Try finding the file path in output
                    match = re.search(r"Release notes written to:.*?/([\d\.]+[\w\.-]*)\.md", gen_output, re.DOTALL)
                
                if match:
                    publish_version = match.group(1)
                    print(f"Detected generated version: {publish_version}")
                else:
                    raise Exception("Could not determine generated version from output.")

            # 3. Publish
            pub_cmd = f"{base_cmd} publish {publish_version}"
            if force and force.lower() != "none":
                pub_cmd += f" --force {force}"

            print(f"Publishing release {publish_version}...")
            run_command(pub_cmd, debug=debug)
            output = f"✅ Release {publish_version} processed successfully."

        elif command == "generate" or command == "update":
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
                output = "✅ Changes committed and pushed."
            else:
                output = "(No changes to commit)"

        elif command == "publish":
            cmd = f"{base_cmd} publish {version}"
            # If auto-publishing (merged PR or closed issue), force published mode
            if event_name in ["pull_request", "issues"]:
                 cmd += " --release-mode published"

            run_command(cmd, debug=debug)
            output = "✅ Published successfully."

        elif command == "list":
             cmd = f"{base_cmd} publish --list"
             run_command(cmd, debug=debug)
             output = "✅ List command completed."
        
        else:
            raise Exception(f"Unknown command: {command}")
            
        print(output)
        if issue_number and event_name == "issue_comment":
            post_comment(token, repo_name, issue_number, f"✅ Command `{command}` succeeded:\n\n{output}")
            
    except Exception as e:
        msg = f"❌ Command `{command}` failed:\n```\n{e}\n```"
        print(msg)
        if issue_number and event_name == "issue_comment":
            post_comment(token, repo_name, issue_number, msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
