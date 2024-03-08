import datetime
import glob
import os.path
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Iterator, Union, Optional, Sequence

import pytest
import yaml

from copyrighthook.copyright import (
    run_copyright_updater,
    FatalException,
    NOT_STAGED,
    NO_FILES_TO_PROCESS,
    OUTSIDE_OF_REPOSITORY,
)
from copyrighthook.git_utilities import GitRepository


class TestRepository:
    def __init__(self, path: Path):
        self.repo = GitRepository(path)
        self.run_command = self.repo.run_command
        self.file_version = 0
        self.start_dt = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        self.commit_counter = 0
        self.current_dt = self.start_dt
        self.config_file = self.repo.root / ".copyright-updater.yaml"

    def modify_file(self, path: Union[PurePath, str], header: Optional[str] = None, stage: bool = True):
        self.file_version += 1
        new_content = (header + "\n" if header else "") + "\n" + str(self.file_version)
        full_path = self.repo.root / path
        full_path.write_text(new_content, "utf-8")
        if stage:
            self.repo.run_command(["git", "add", str(path)])

    def move_file(self, src: Union[PurePath, str], dst: Union[PurePath, str]):
        src = Path(self.repo.root / src)
        dst = Path(self.repo.root / dst)
        src.rename(dst)
        self.repo.run_command(["git", "add", str(src), str(dst)])

    def load_first_line(self, path: Union[PurePath, str]) -> str:
        return (self.repo.root / path).read_text("utf-8").splitlines()[0]

    def commit(self):
        self.commit_counter += 1
        self.repo.run_command(
            [
                "git",
                "commit",
                "--allow-empty",
                "-m",
                f"commit{self.commit_counter}",
                "--date",
                self.current_dt.isoformat(),
            ]
        )

    def generate_config(self, pattern: str, ignore_commits_before: Optional[datetime.datetime] = None):
        config = {"pattern": pattern, "ignore_commits_before": ignore_commits_before}
        with self.config_file.open("wt", encoding="utf-8") as f:
            yaml.dump(config, f)

    def skip_time(self, delta: datetime.timedelta):
        self.current_dt += delta

    def skip_year(self):
        self.current_dt = self.current_dt.replace(year=self.current_dt.year + 1)

    def run_copyright_updater_on_all_files(self, *args: str) -> bool:
        all_files = [f for f in glob.glob(str(self.repo.root / "**"), recursive=True) if os.path.isfile(f)]
        return self.run_copyright_updater(all_files, args=args)

    def run_copyright_updater(self, files: Sequence[Union[PurePath, str]], args: Sequence[str] = ()) -> bool:
        files = [str((self.repo.root / f).resolve()) for f in files]
        return run_copyright_updater([*args, "--verbose", *files], now=self.current_dt)


@contextmanager
def temporary_repository() -> Iterator[TestRepository]:
    with tempfile.TemporaryDirectory() as tempdir_path_str:
        tempdir_path = Path(tempdir_path_str)
        repo_root = Path(tempdir_path / "repo")
        repo_root.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_root)
        yield TestRepository(repo_root)


def test_fail_on_unstaged():
    with pytest.raises(FatalException, match=NOT_STAGED):
        with temporary_repository() as r:
            r.generate_config("# (c) {years}, developers")
            r.commit()
            r.modify_file("a.txt", stage=False)
            assert not r.run_copyright_updater_on_all_files()


def test_no_files_repo():
    with pytest.raises(FatalException, match=NO_FILES_TO_PROCESS):
        with temporary_repository() as r:
            assert r.run_copyright_updater_on_all_files()


def test_ok_on_repository_without_commits():
    with temporary_repository() as r:
        r.generate_config("# (c) {years}, developers")
        r.modify_file("a.txt")
        assert not r.run_copyright_updater_on_all_files()


def test_require_header():
    with temporary_repository() as r:
        r.generate_config("# (c) {years}, developers")
        r.modify_file("a.txt")
        r.commit()
        assert r.run_copyright_updater_on_all_files("--required")


def test_correct_year_in_header():
    with temporary_repository() as r:
        r.generate_config("# (c) {years}, developers")
        r.commit()
        r.modify_file("a.txt", header=f"# (c) {r.current_dt.year}, developers")
        assert not r.run_copyright_updater_on_all_files("--required")


def test_wrong_year_in_header():
    with temporary_repository() as r:
        r.generate_config("# (c) {years}, developers")
        r.modify_file("a.txt", header=f"# (c) {r.current_dt.year - 1}, developers")  # committed
        r.modify_file("c.txt", header=f"# (c) {r.current_dt.year - 1}, developers")
        r.commit()
        r.modify_file("b.txt", header=f"# (c) {r.current_dt.year - 1}, developers")  # staged only
        r.modify_file("c.txt", header=f"# (c) {r.current_dt.year - 1}, developers")  # both
        assert r.run_copyright_updater_on_all_files()
        assert r.load_first_line("a.txt") == f"# (c) {r.current_dt.year - 1}-{r.current_dt.year}, developers"
        assert r.load_first_line("b.txt") == f"# (c) {r.current_dt.year - 1}-{r.current_dt.year}, developers"
        assert r.load_first_line("c.txt") == f"# (c) {r.current_dt.year - 1}-{r.current_dt.year}, developers"


def test_file_move_does_not_change_year():
    with temporary_repository() as r:
        r.generate_config("# (c) {years}, developers")
        r.modify_file("a.txt", header=f"# (c) {r.current_dt.year}, developers")
        r.commit()
        r.move_file("a.txt", "b.txt")
        r.skip_year()
        assert not r.run_copyright_updater_on_all_files()


def test_file_move_with_modification():
    with temporary_repository() as r:
        r.generate_config("# (c) {years}, developers")
        r.modify_file("a.txt", header=f"# (c) {r.current_dt.year}, developers")
        r.commit()
        r.move_file("a.txt", "b.txt")
        r.modify_file("b.txt", header=f"# (c) {r.current_dt.year}, developers")
        r.skip_year()
        assert r.run_copyright_updater_on_all_files()
        assert r.load_first_line("b.txt") == f"# (c) {r.current_dt.year - 1}-{r.current_dt.year}, developers"


def test_ignore_commits_before():
    with temporary_repository() as r:
        r.modify_file("a.txt", header=f"# (c) {r.current_dt.year - 1}, developers")
        r.commit()
        r.skip_year()
        r.generate_config("# (c) {years}, developers", ignore_commits_before=r.current_dt)
        assert not r.run_copyright_updater_on_all_files()


def test_file_out_of_repo():
    with temporary_repository() as r:
        r.modify_file("../out.txt", stage=False)
        r.modify_file("a.txt")
        with pytest.raises(FatalException, match=OUTSIDE_OF_REPOSITORY):
            assert not r.run_copyright_updater(["a.txt", "../out.txt"])
        with pytest.raises(FatalException, match=OUTSIDE_OF_REPOSITORY):
            assert not r.run_copyright_updater(["../out.txt"])
