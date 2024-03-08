import dataclasses
import datetime
import itertools
import subprocess  # nosec
from dataclasses import field
from pathlib import PurePath, Path
from typing import Union, List, Optional


@dataclasses.dataclass
class GitChangeSet:
    items: list[tuple[str, ...]]
    changed_files: set[PurePath] = field(init=False)
    moved_files: list[tuple[PurePath, PurePath]] = field(init=False)
    touched_files: set[PurePath] = field(init=False)

    def __post_init__(self) -> None:
        self.touched_files = set()
        self.changed_files = set()
        self.moved_files = []
        for item in self.items:
            change_type, *extra_files, dst = item
            self.touched_files.add(PurePath(dst))
            if change_type.startswith("R"):
                # File moved (possibly with changes)
                if change_type != "R100":
                    self.changed_files.add(PurePath(dst))
                self.moved_files.append((PurePath(extra_files[0]), PurePath(dst)))
            else:
                # File changed/added/copied/deleted/...
                self.changed_files.add(PurePath(dst))

    def __bool__(self) -> bool:
        return bool(self.items)

    @staticmethod
    def parse(lines: Union[list[str], str]) -> "GitChangeSet":
        if isinstance(lines, str):
            lines = lines.splitlines()
        return GitChangeSet([tuple(line.split("\t")) for line in lines if line])


class GitCommitInfo:
    def __init__(
        self, author_date: Union[datetime.datetime, str], changes: Optional[GitChangeSet] = None
    ) -> None:
        if isinstance(author_date, str):
            author_date = datetime.datetime.fromisoformat(author_date)
        self.author_date = author_date
        self.changes = changes or GitChangeSet([])


class NotGitRepositoryException(Exception):
    pass


class GitRepository:
    def __init__(self, directory: Union[str, Path]) -> None:
        self.root = Path(directory)
        try:
            self.root = Path(self.run_command(["git", "rev-parse", "--show-toplevel"]))
        except subprocess.CalledProcessError as exc:
            raise NotGitRepositoryException(str(directory)) from exc

    def run_command(self, args: List[str]) -> str:
        out = subprocess.run(
            args,
            check=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.root),
        ).stdout  # nosec
        return out.removesuffix("\n")

    def command_fails(self, args: List[str]) -> bool:
        result = subprocess.run(
            args,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=self.root,
            check=False,
        )  # nosec
        return result.returncode != 0

    def commits(self, since: Optional[datetime.datetime] = None) -> List[GitCommitInfo]:
        if self.command_fails(["git", "rev-parse", "HEAD"]):
            # no commits yet
            return []

        # Get git log
        extra_args = []
        if since:
            extra_args += ["--since", since.isoformat()]
        log = self.run_command(["git", "log", "--name-status", "--pretty=format:%aI", *extra_args])
        # Parse command output
        commits = []
        for block in log.split("\n\n"):
            if not block:
                # possible on empty logs
                continue
            block_lines = [line for line in block.split("\n") if line]
            # There may be extra timestamps in a block (from commits without file changes)
            timestamp_lines = list(itertools.takewhile(lambda p: "\t" not in p, block_lines))
            for extra_timestamp in timestamp_lines[:-1]:
                commits.append(GitCommitInfo(extra_timestamp))
            commit_datetime = timestamp_lines[-1]
            change_lines = block_lines[len(timestamp_lines) :]
            commits.append(GitCommitInfo(commit_datetime, GitChangeSet.parse(change_lines)))
        return commits

    def staged_changeset(self) -> GitChangeSet:
        return GitChangeSet.parse(self.run_command(["git", "diff", "--name-status", "--cached"]))

    def staged_files(self) -> set[PurePath]:
        return set(PurePath(p) for p in self.run_command(["git", "ls-files", "--cached"]).splitlines())
