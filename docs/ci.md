# Continuous Integration for Twi Bot Shard

This document explains the continuous integration (CI) setup for the Twi Bot Shard project, including what it does, how it works, and how to use it.

## Overview

Continuous Integration (CI) is a development practice that requires developers to integrate code into a shared repository frequently. Each integration is verified by an automated build and automated tests to detect integration errors as quickly as possible.

In the Twi Bot Shard project, we use GitHub Actions for CI. GitHub Actions is a CI/CD (Continuous Integration/Continuous Deployment) platform that allows you to automate your build, test, and deployment pipeline.

## CI Workflow

Our CI workflow is defined in the `.github/workflows/ci.yml` file and consists of three main jobs:

1. **Test**: Runs the tests and generates a coverage report
2. **Lint**: Runs linting and type checking
3. **Build**: Builds the package

### Test Job

The test job performs the following steps:

1. Checks out the code
2. Sets up Python 3.12
3. Installs dependencies using uv
4. Runs pytest with coverage reporting
5. Uploads the coverage report to Codecov

This job ensures that all tests pass and tracks code coverage over time.

### Lint Job

The lint job performs the following steps:

1. Checks out the code
2. Sets up Python 3.12
3. Installs dependencies using uv
4. Runs ruff for linting
5. Runs black for code formatting checking
6. Runs mypy for type checking

This job ensures that the code follows our style guidelines and type annotations are correct.

### Build Job

The build job performs the following steps:

1. Checks out the code
2. Sets up Python 3.12
3. Installs dependencies using uv
4. Builds the package using build
5. Archives the built package as an artifact

This job ensures that the package can be built successfully and makes the built package available as an artifact.

## When the CI Runs

The CI workflow is triggered on:

- Pushes to the main branch
- Pull requests to the main branch

This ensures that code is tested and validated before it is merged into the main branch.

## Viewing CI Results

You can view the results of the CI workflow in the "Actions" tab of the GitHub repository. Each workflow run will show the status of each job and any errors or warnings that occurred.

### Test Results

The test results show which tests passed and which failed. If a test fails, you can see the error message and stack trace to help diagnose the issue.

### Coverage Report

The coverage report shows which parts of the code are covered by tests and which are not. You can view the coverage report on Codecov, which provides a detailed breakdown of coverage by file and line.

### Lint Results

The lint results show any style violations or type errors in the code. If there are any issues, you can see the file and line number where the issue occurred, along with a description of the issue.

### Build Results

The build results show whether the package was built successfully. If the build succeeds, the built package is available as an artifact that you can download.

## Using the CI in Development

When developing new features or fixing bugs, you can use the CI to ensure that your changes don't break existing functionality and follow our style guidelines.

### Before Pushing Changes

Before pushing your changes, you can run the same checks locally to catch issues early:

1. Run the tests with coverage:
   ```bash
   pytest tests/ --cov=.
   ```

2. Run the linters:
   ```bash
   ruff check .
   black --check .
   mypy .
   ```

3. Build the package:
   ```bash
   python -m build
   ```

### After Pushing Changes

After pushing your changes, you can monitor the CI workflow in the "Actions" tab of the GitHub repository. If any issues are found, you can fix them and push the changes again.

## Adding New Tests to the CI

When adding new tests to the project, they will automatically be included in the CI workflow if they are in the `tests/` directory and follow the naming convention `test_*.py`.

## Adding New Linting Rules

If you want to add new linting rules, you can modify the configuration files:

- `pyproject.toml` for ruff and black
- `mypy.ini` for mypy

## Troubleshooting CI Issues

If you encounter issues with the CI workflow, here are some common problems and solutions:

### Tests Failing

If tests are failing in CI but passing locally, it could be due to:

- Different Python versions
- Different dependency versions
- Environment-specific issues

Try running the tests in a clean environment with the same Python version and dependencies as the CI.

### Linting Issues

If linting is failing in CI but passing locally, it could be due to:

- Different linter versions
- Different configuration files

Try running the linters with the same versions and configuration files as the CI.

### Build Issues

If the build is failing in CI but succeeding locally, it could be due to:

- Different build tool versions
- Missing dependencies
- Platform-specific issues

Try building the package in a clean environment with the same build tool versions and dependencies as the CI.

## Conclusion

Continuous Integration is an essential part of our development process. It helps us catch issues early, maintain code quality, and ensure that the project is always in a releasable state.

By following the guidelines in this document, you can use the CI effectively in your development workflow and contribute to the project with confidence.