"""
ChannelIdentifiarr - Configuration
"""
import subprocess
import os

# Application version - single source of truth
# Format: MAJOR.MINOR.PATCH[-pre-release][+build]
BASE_VERSION = "0.6.5"

def get_version():
    """
    Get version string with automatic dev/branch detection

    Returns:
        - "X.Y.Z" on main/master branch (stable release)
        - "X.Y.Z-dev+SHA" on dev branch with commit SHA
        - "X.Y.Z-branch+SHA" on other branches
    """
    version = BASE_VERSION
    branch = None
    sha = None

    # First, try to read from Docker build-time files (created in Dockerfile)
    try:
        config_dir = os.path.dirname(os.path.abspath(__file__))
        branch_file = os.path.join(config_dir, '.git-branch')
        sha_file = os.path.join(config_dir, '.git-sha')

        if os.path.exists(branch_file):
            with open(branch_file, 'r') as f:
                branch = f.read().strip()

        if os.path.exists(sha_file):
            with open(sha_file, 'r') as f:
                sha = f.read().strip()
    except:
        pass

    # Fallback to environment variables (also set in Dockerfile)
    if not branch:
        branch = os.environ.get('GIT_BRANCH')
    if not sha:
        sha = os.environ.get('GIT_SHA')

    # Last fallback: try git commands (for local development)
    if not branch or branch == 'unknown':
        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                branch = result.stdout.strip()

                if not sha or sha == 'unknown':
                    result = subprocess.run(
                        ['git', 'rev-parse', '--short', 'HEAD'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        sha = result.stdout.strip()
        except:
            pass

    # Build version string
    if branch and branch != 'unknown':
        if branch in ['main', 'master']:
            # Clean version for production
            pass
        elif sha and sha != 'unknown':
            # Dev and feature branches get SHA suffix
            version = f"{BASE_VERSION}-{branch}+{sha}"
        else:
            # Fallback without SHA
            version = f"{BASE_VERSION}-{branch}"

    return version

VERSION = get_version()

# Application settings
APP_NAME = "ChannelIdentifiarr"
APP_DESCRIPTION = "Channel management for Dispatcharr with Gracenote TV database integration"
