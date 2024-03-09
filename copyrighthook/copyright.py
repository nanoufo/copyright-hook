"""Update the copyright header of the files."""

import argparse
import datetime
import sys
from pathlib import Path, PurePath
from typing import Optional, Dict, Sequence, List, Union, Callable, Iterable

from copyrighthook.config import CopyrightConfig
from copyrighthook.git_utilities import (
    GitCommitInfo,
    GitRepository,
    NotGitRepositoryException,
    GitCallException,
)
from copyrighthook.years_pattern import YearsPattern

NO_CONFIG_FOUND = "no configuration file found"
INVALID_CONFIGURATION = "invalid configuration"
NO_FILES_TO_PROCESS = "no files to process"
NOT_STAGED = "file is not staged"
NOT_EXISTS = "file does not exist"
NOT_A_FILE = "file is not a regular file"
OUTSIDE_OF_REPOSITORY = "outside ot the repository"

NO_COPYRIGHT_HEADER_FOUND = "no copyright comment found"
RANGE_USED_FOR_A_SINGLE_YEAR = "range syntax is used for a single year"


class FatalException(Exception):
    def __init__(self, message: str, file: Optional[Path] = None, extra: Optional[str] = None) -> None:
        if file:
            full_message = f"{file}: {message}"
        else:
            full_message = message
        if extra:
            full_message += f", {extra}"
        super().__init__(full_message)
        self.full_message = full_message
        self.message = message
        self.extra = extra
        self.file = file


def compute_last_modified_dict(commits: Sequence[GitCommitInfo]) -> Dict[PurePath, datetime.datetime]:
    last_modified_dict: Dict[PurePath, datetime.datetime] = {}
    for commit in reversed(commits):
        for src, dst in commit.changes.moved_files:
            if src in last_modified_dict:
                # `src` may be missing in dict in case only part of history is loaded
                last_modified_dict[dst] = last_modified_dict[src]
        for file in commit.changes.changed_files:
            last_modified_dict[file] = commit.author_date
    return last_modified_dict


def run_copyright_updater(args_list: List[str], *, now: Optional[datetime.datetime] = None) -> bool:
    """returns True if any file has invalid copyright header"""

    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    elif not now.tzinfo:
        raise ValueError("now must have tzinfo defined")

    # Parse cli args
    args_parser = argparse.ArgumentParser("Update the copyright header of the files")
    args_parser.add_argument("--config", help="The configuration file", type=Path)
    args_parser.add_argument("--required", action="store_true", help="The copyright is required")
    args_parser.add_argument("--verbose", action="store_true", help="Verbose mode")
    args_parser.add_argument("--dry-run", action="store_true", help="Dry run")
    args_parser.add_argument("files", nargs=argparse.REMAINDER, type=Path, help="The files to update")
    args = args_parser.parse_args(args_list)

    # Utility functions
    def print_verbose(message: Union[str, Callable[[], str]]) -> None:
        if not args.verbose:
            return
        if callable(message):
            message = message()
        print(message)

    # Check that all required files are present and in the repository
    if not args.files:
        raise FatalException(NO_FILES_TO_PROCESS)
    try:
        repo = GitRepository(args.files[0].parent)
    except NotGitRepositoryException as exc:
        raise FatalException(OUTSIDE_OF_REPOSITORY, file=args.files[0]) from exc
    print_verbose(f"Repository root is {repo.root}")
    files = validate_and_resolve_files(args.files, repo)

    # Find config file
    config_path = find_config_path(args.config, repo.root)

    # Load config file
    try:
        print_verbose(f"Loading config from {config_path}")
        config = CopyrightConfig.load_from_file(config_path)
    except ValueError as err:
        raise FatalException(INVALID_CONFIGURATION, config_path, extra=str(err)) from err

    # Scan commit history and build mapping (file -> last committed datetime)
    commits = repo.commits(since=config.ignore_commits_before)
    if staged_changes := repo.staged_changeset():
        # Add pseudo-commit for staged changes
        commits.insert(0, GitCommitInfo(now, staged_changes))
    if not commits:
        print_verbose("No staged changes and no commits")
        return False

    last_repo_modification_datetime: Optional[datetime.datetime] = commits[0].author_date
    last_modified_dict = compute_last_modified_dict(commits)

    success = True
    for rel_path in files:
        # Determine last year when that file was changed
        if rel_path != config.license_file:
            last_change_datetime = last_modified_dict.get(rel_path)
            if rel_path not in staged_changes.changed_files:
                print_verbose(f"File '{rel_path}' was committed at {last_change_datetime or '<unknown>'}")
            else:
                print_verbose(f"File '{rel_path}' has staged changes")
        else:
            last_change_datetime = last_repo_modification_datetime
            print_verbose(
                f"File '{rel_path}' is a license file, "
                f"last modification in git repository is at {last_change_datetime}"
            )

        # Ignore copyright year in too old files
        if last_change_datetime is None:
            print_verbose(f"Ignoring '{rel_path}' because its last modification time is unknown")
            continue
        if config.ignore_commits_before and last_change_datetime < config.ignore_commits_before:
            print_verbose(f"Ignoring '{rel_path}' because it is too old")
            continue

        expected_year = str(last_change_datetime.year)

        # Check copyright header is correct
        full_path = repo.root / rel_path
        try:
            content = Path(full_path).read_text("utf-8")
        except UnicodeDecodeError:
            print_verbose(f"'{rel_path}': is not valid utf-8 text file, skipping")
            continue
        error_comment, content = update_file(
            content,
            last_year=expected_year,
            pattern=config.pattern,
            current_year=str(now.year),
            required=args.required,
        )
        success &= error_comment is None
        if error_comment:
            print(f"File '{rel_path}': {error_comment}")
            if not args.dry_run:
                Path(full_path).write_text(content, "utf-8")
        elif args.verbose:
            years = config.pattern.extract(content)
            print_verbose(f"File '{rel_path}': ok, {'no header' if not years else expected_year}")

    return not success


def validate_and_resolve_files(files: Iterable[Path], repo: GitRepository) -> List[PurePath]:
    staged_files = set(repo.staged_files())
    files_relative_to_repo_root: List[PurePath] = []
    file_arg: Path
    for file_arg in files:
        if not file_arg.exists():
            raise FatalException(NOT_EXISTS, file_arg)
        if not file_arg.is_file():
            raise FatalException(NOT_A_FILE, file_arg)
        abs_path = file_arg.absolute().resolve()
        if not abs_path.is_relative_to(repo.root):
            raise FatalException(OUTSIDE_OF_REPOSITORY, file_arg)
        file_rel = abs_path.relative_to(repo.root)
        if file_rel not in staged_files:
            raise FatalException(NOT_STAGED, file_rel)
        files_relative_to_repo_root.append(file_rel)
    return files_relative_to_repo_root


def find_config_path(args_config: Optional[Path], config_root: Path) -> Path:
    if args_config:
        return args_config
    default_config_names = [".copyright-updater.yaml", ".copyright-updater.yml"]
    for config_filename in default_config_names:
        config_path = config_root / config_filename
        if config_path.exists():
            return config_path
    raise FatalException(
        NO_CONFIG_FOUND, extra="searched for " + ", ".join(default_config_names) + f" in {config_root}"
    )


def update_file(
    content: str,
    last_year: str,
    pattern: YearsPattern,
    current_year: str,
    required: bool = False,
) -> tuple[Optional[str], str]:
    """Update the copyright header of the file content."""
    years = pattern.extract(content)
    if years is None:
        if required:
            return NO_COPYRIGHT_HEADER_FOUND, content
        return None, content
    if isinstance(years, tuple):
        y_from, y_to = years
        if y_from == y_to:
            err_message = RANGE_USED_FOR_A_SINGLE_YEAR
            if y_from == current_year:
                return err_message, pattern.replace(content, current_year)
            return err_message, pattern.replace(content, (y_from, current_year))
        if last_year == y_to:
            return None, content
        return f"expected year {last_year}, actual is {y_to}", pattern.replace(
            content, (y_from, current_year)
        )
    # years is str
    if years == last_year:
        return None, content
    new_range = (years, current_year)
    return f"expected year {last_year}, actual is {years}", pattern.replace(content, new_range)


def main() -> None:
    try:
        if run_copyright_updater(sys.argv[1:]):
            sys.exit(128)
    except FatalException as exc:
        print(exc.full_message)
        sys.exit(1)
    except GitCallException as exc:
        exit_code_comment = f" (exit code {exc.return_code})" if exc.return_code else ""
        print(f"failed to run git{exit_code_comment}: {exc.comment}")
        sys.exit(2)


if __name__ == "__main__":
    main()
