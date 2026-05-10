# https://just.systems

set script-interpreter := ['pwsh', '-ExecutionPolicy', 'ByPass', '-File']
set shell := ['pwsh', '-ExecutionPolicy', 'ByPass', '-Command']

error := "Write-Host -ForegroundColor Red"
title := "Write-Host -ForegroundColor Cyan"

# Run just without specifying a recipe lists all available recipes
_default:
    @just --list --unsorted

[confirm('This will remove the virtual environment and other files ignored by git. Do you want to continue? [y/N])')]
[doc('Clean environment artifacts (removes everything in .gitignore, including .venv)')]
clean:
    @{{ title }} "Removing all files and folders ignored by git..."
    "n" | git clean -fdX

[doc('Run pre-commit hooks (examples: `just prek` or `just prek sync-with-uv`)')]
[script]
prek hook="":
    $ErrorActionPreference = 'Stop'
    $PSNativeCommandUseErrorActionPreference = $true
    if ("{{ hook }}" -eq "") {
        {{ title }} "Running pre-commit hooks..."
        uv run prek run --all-files
    } else {
        {{ title }} "Running pre-commit hook {{ hook }}..."
        uv run prek run --all-files --hook-stage manual {{ hook }}
    }

[doc('Download igdbapi.proto and compile it to Python with betterproto2')]
proto:
    @{{ title }} "Downloading igdbapi.proto..."
    New-Item -ItemType Directory -Force -Path downloads | Out-Null
    Invoke-WebRequest -Uri "https://api.igdb.com/v4/igdbapi.proto" -OutFile "downloads/igdbapi.proto"
    @{{ title }} "Compiling igdbapi.proto..."
    New-Item -ItemType Directory -Force -Path notion_videogames/proto | Out-Null
    uv run --with betterproto2_compiler --with grpcio-tools python -m grpc.tools.protoc \
        -I . \
        --python_betterproto2_opt=pydantic_dataclasses \
        --python_betterproto2_out=notion_videogames/proto \
        downloads/igdbapi.proto

[doc('Run the main application')]
run:
    @{{ title }} "Running main.py..."
    uv run -m notion_videogames.main

[doc('Update uv.lock to reflect the latest compatible versions of dependencies listed in pyproject.toml')]
[group('Dependencies')]
lock:
    @{{ title }} "Updating uv.lock to the latest compatible versions of dependencies..."
    uv lock --upgrade

[doc('Export runtime dependencies to requirements.txt for use in other contexts')]
[group('Dependencies')]
uv-export:
    {{ title }} "Exporting runtime dependencies to requirements.txt..."
    uv export --frozen --no-dev --output-file=requirements.txt

[doc('Install project dependencies, ensuring that installed versions are compatible with uv.lock')]
[group('Dependencies')]
sync:
    {{ title }} "Synchronizing development dependencies..."
    uv sync --frozen

[doc('Format code automatically')]
[group('QA')]
format:
    @{{ title }} "Running automatic formatting/cleanup..."
    -uv run ty check --fix
    -uv run ruff check --fix
    uv run ruff format

[doc('Static code analysis')]
[group('QA')]
lint:
    @{{ title }} "Running linting tools..."
    uv run ruff check
    uv run flake8 notion_videogames
    uv run pylint notion_videogames

[doc('Static type analysis')]
[group('QA')]
type-check:
    @{{ title }} "Running static type checking with mypy..."
    uv run ty check
    uv run mypy notion_videogames

[doc('Run all QA checks')]
[group('QA')]
qa: format lint type-check
