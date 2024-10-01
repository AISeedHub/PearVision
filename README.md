# AISEED Python Project Template

## Introduction

AISEED, an AI company, handles numerous Python projects.  
Unlike before, we now go beyond research to develop actual products, which require maintenance.

This means that in addition to **writing code**, we must also focus on **managing code**.  
However, maintaining a project is no easy task.

- Standardizing code conventions
- Designing project structure
- Writing test codes
- Managing virtual environments and dependencies
- ...

When starting a new project or onboarding new team members, explaining and setting up all these aspects every time is inefficient.

Thus, we've created a consistent template for company-wide use.

## Components

The basic components used in this template are as follows:

- [rye](https://rye.astral.sh/guide/) - Project and package management
- [ruff](https://docs.astral.sh/ruff/) - Code formatting and rules
- [mypy](https://mypy.readthedocs.io/en/stable/) - Type checking
- [pytest](https://docs.pytest.org/) - Test framework
- [pre-commit](https://pre-commit.com/) - Pre-commit hooks for Git

## Getting Started

### Setting Up the Development Environment

- Install `rye`. ([Installation Guide](https://rye.astral.sh/guide/installation/))

### Project Setup

- Create a repository from this template on GitHub and clone it.
  ![Github Repository's Use this template](./assets/use-this-template.jpeg)
- Modify the `name`, `version`, `description`, and `authors` fields in the `pyproject.toml` file according to your project.
- Run the following scripts in the project's root directory:
  ```bash
  $ rye sync
  $ pre-commit install # If you encounter errors, try restarting the terminal
  ```

### Running the Main Function

Execute the main function in the `app` package.

```bash
$ rye run app
```

If the message "Hello, AISEED" is displayed in the terminal, the setup was successful!

## Project Guidelines

### Dependency Management

When handling dependencies, use `rye` instead of `pip`.  
Make sure to differentiate between packages required for development and those for production.

```bash
# install production dependency
$ rye add numpy

# uninstall production dependency
$ rye remove numpy

# install development dependency
$ rye add --dev pytest

# uninstall development dependency
$ rye remove --dev pytest
```

### Type Checking

Use `mypy` to identify type errors in your code.

```bash
$ rye run type
```

### Linting

Check for code convention issues using `ruff`.

```bash
$ rye run lint
```

### Running Tests

Run tests in the `tests/` folder using `pytest`.

```bash
# run test
$ rye run test

# run test with duration
$ rye run test:duration
```

**Writing test code** is a vast and challenging topic, so we won't cover it here.  
Instead, focus on writing **code usage examples** to help others understand the code easily.

### Git

When committing your changes, `pre-commit` will inspect the code.  
Currently, only code conventions are checked using `ruff`.

\* Plans to include pytest and mypy checks in the future

[Further details to be added]

## Miscellaneous

### Check Project Environment

```bash
$ rye show
```

### View Available Scripts

```bash
$ rye run
```

### Script Management

You can add or modify scripts in the `[tool.rye.scripts]` section of the `pyproject.toml` file.

### Changing Python Version

1. Modify the version in `.python-version` as needed.

   (Also, update the `requires-version` field in `pyproject.toml`.)

2. Run the sync script.

   ```bash
   $ rye sync
   ```
