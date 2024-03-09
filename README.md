# copyright-hook
This is a pre-commit hook that updates the years in copyright headers in source files. It uses the git log to find out when each file was updated. Please note that file movements are not viewed as modifications.

## Quick start
Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/nanoufo/copyright-hook
    rev: v1.0.0
    hooks:
      - id: update-copyright
```
Create `.copyright-updater.yaml`:
```yaml
# Adjust pattern to your needs
pattern: ' Copyright {years} MyProject contributors (see AUTHORS)'
```
Run this hook on all files to fix outdated headers:
```
pre-commit run update-copyright -a
```
Look at the results:
```bash
$ git diff
```
```diff
...
-# Copyright 2009-2023 MyProject contributors (see AUTHORS)
+# Copyright 2009-2024 MyProject contributors (see AUTHORS)
...
```

## Args:
| Option | Description |
| --- | --- |
| --required | Triggers failure if copyright headers are absent |
| --verbose | Prints more information, which is helpful for debugging |
| --dry-run | Omits writing to any files |
| --config FILE | Specifies the path to the configuration file |

## Configuration
The default location is `.copyright-updater.{yml,yaml}` in the root directory of the repository.

```yaml
# The pattern must include a {years} placeholder
pattern: ' Copyright {years} MyProject contributors (see AUTHORS)'

# This allows you to disregard files modified prior to the provided date
# This is particularly useful for the `pre-commit run --all-files` command when you don't want to update a large number 
# of old files with the incorrect year in the copyright headers.
# Also a recent date here speeds up this hook.
ignore_commits_before: 2024-01-01
```

## Running in CI/CD
### Running with Github actions
```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0 # Important!
- uses: actions/setup-python@v5
- uses: pre-commit/action@v3.0.1
```

### Running with [pre-commit.ci](pre-commit.ci)
pre-commit.ci doesn't fetch git history so it is impossible to use it with this hook.
