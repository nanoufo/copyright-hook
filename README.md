# copyright-hook
This is a pre-commit hook that updates the years in copyright headers in source files. It uses the git log to find out when each file was updated. Please note that file movements are not viewed as modifications.

## Usage with pre-commit:
```yaml
  - repo: https://github.com/nanoufo/copyright-hook
    rev: <commit ID>
    hooks:
      - id: update-copyright
        # --required, --verbose, --dry-run, --config FILE
        args: []
        # Define the files to be processed by this hook
        # For more details, see https://pre-commit.com/filtering-files-with-types
        types_or: ["c++", "cmake"]
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
ignore_commits_before: 2024-01-01
```

## Running in CI/CD
### Running with Github actions
Remember to fetch the git history.
```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
```

### Running with [pre-commit.ci](pre-commit.ci)
pre-commit.ci doesn't fetch history so it is impossible to use it with this hook.
