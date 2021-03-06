import os
import shutil
import subprocess
from argparse import Namespace
from distutils.dir_util import copy_tree
from pathlib import Path
from typing import Dict, Optional, List

from .fileutils import chdir, write_json_file
from .manifest import Repo, load_manifest
from .path import LOCK_PATH, MANIFEST_PATH, ROOT


def load_channel_repos(path: Path) -> Dict[str, Repo]:
    channel_manifest = load_manifest(
        path.joinpath("repos.json"), path.joinpath("repos.json.lock")
    )
    repos = {}
    for repo in channel_manifest.repos:
        repos[repo.name] = repo
    return repos


def repo_source(name: str) -> str:
    cmd = [
        "nix-build",
        str(ROOT),
        "--no-out-link",
        "-A",
        f"repo-sources.{name}",
    ]
    out = subprocess.check_output(cmd)
    return out.strip().decode("utf-8")


def repo_changed() -> bool:
    diff_cmd = subprocess.Popen(["git", "diff", "--staged", "--exit-code"])
    return diff_cmd.wait() == 1


def commit_files(files: List[str], message: str) -> None:
    cmd = ["git", "add"]
    cmd.extend(files)
    subprocess.check_call(cmd)
    if repo_changed():
        subprocess.check_call(["git", "commit", "-m", message])


def commit_repo(repo: Repo, message: str, path: Path) -> None:
    repo_path = str(path.joinpath(repo.name).resolve())
    copy_tree(repo_source(repo.name), repo_path)

    with chdir(str(path)):
        commit_files([repo_path], message)


def update_channel_repo(channel_repo: Optional[Repo], repo: Repo, path: Path) -> None:
    if repo.locked_version is None:
        return

    new_rev = repo.locked_version.rev
    if channel_repo is None:
        return commit_repo(repo, f"{repo.name}: init at {new_rev}", path)
    assert channel_repo.locked_version is not None
    old_rev = channel_repo.locked_version.rev

    if channel_repo.locked_version == repo.locked_version:
        return

    if new_rev != new_rev:
        message = f"{repo.name}: {old_rev} -> {new_rev}"
    else:
        message = f"{repo.name}: update"

    return commit_repo(repo, message, path)


def update_channel(path: Path) -> None:
    manifest = load_manifest(MANIFEST_PATH, LOCK_PATH)

    old_channel_repos = load_channel_repos(path)
    channel_repos = old_channel_repos.copy()

    repos_path = path.joinpath("repos")
    os.makedirs(repos_path, exist_ok=True)

    for repo in manifest.repos:
        channel_repo = None
        if repo.name in channel_repos:
            channel_repo = channel_repos[repo.name]
            del channel_repos[repo.name]
        update_channel_repo(channel_repo, repo, repos_path)


def setup_channel() -> None:
    manifest_path = "repos.json"

    if not Path(".git").exists():
        cmd = ["git", "init", "."]
        subprocess.check_call(cmd)

    if not os.path.exists(manifest_path):
        write_json_file(dict(repos={}), manifest_path)

    manifest_lib = "lib"
    copy_tree(str(ROOT.joinpath("lib")), manifest_lib)
    default_nix = "default.nix"
    shutil.copy(ROOT.joinpath("default.nix"), default_nix)

    vcs_files = [manifest_path, manifest_lib, default_nix]

    commit_files(vcs_files, "update channel code")


def build_channel_command(args: Namespace) -> None:
    channel_path = Path(args.directory)

    with chdir(channel_path):
        setup_channel()
    update_channel(channel_path)
