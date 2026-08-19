"""cupdate - Python requirements.txt updater."""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
from datetime import datetime
from typing import Any

import requests
from tabulate import tabulate

# only a line matching this gets rewritten, so direct references, option lines
# and multi-specifier ranges are left alone instead of being mangled
PIN = re.compile(
    r"^(?P<head>\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(?P<operator>==|>=|<=)\s*)"
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9.*+!-]*)"
    r"(?P<tail>(?:[\s;#].*)?)$"
)


def match_pin(line: str) -> re.Match[str] | None:
    """Match a single pinned requirement, or return None for any other line."""
    return PIN.match(line.rstrip("\r\n"))


def read_requirements(file_path: str) -> dict[str, str]:
    """Read requirements.txt and return a dictionary with package and version."""
    requirements: dict[str, str] = {}
    if not os.path.exists(file_path):
        return requirements

    with open(file_path) as file:
        for line in file:
            match = match_pin(line)
            if not match:
                continue

            operator = match.group("operator")
            version = match.group("version")
            requirements[match.group("name")] = version if operator == "==" else f"{operator}{version}"

    return requirements


def read_excluded_packages(config_path: str) -> set[str]:
    """Read cupdate.config.txt and return a set of packages that should not be updated."""
    excluded: set[str] = set()
    if not os.path.exists(config_path):
        return excluded

    with open(config_path) as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                excluded.add(line)

    return excluded


def get_latest_versions(packages: list[str]) -> dict[str, dict[str, str]]:
    """Determine the latest versions for a list of packages with additional information."""
    package_info: dict[str, dict[str, str]] = {}

    for package in packages:
        try:
            # Get latest version
            result = subprocess.run(
                ["pip", "index", "versions", package], capture_output=True, text=True, check=True
            )
            output = result.stdout

            version_match = re.search(r"Available versions:\s*([^\s,]+)", output)
            latest_version = version_match.group(1) if version_match else None

            if latest_version:
                # Get package info from PyPI
                try:
                    response = requests.get(f"https://pypi.org/pypi/{package}/json", timeout=5)
                    if response.status_code == 200:
                        pypi_data = response.json()

                        # Get project URL
                        project_url = (
                            pypi_data.get("info", {}).get("project_urls", {}).get("Homepage")
                            or pypi_data.get("info", {}).get("home_page")
                            or f"https://pypi.org/project/{package}/"
                        )

                        # Calculate release age
                        release_date = None
                        release_info: list[dict[str, str]] = pypi_data.get("releases", {}).get(
                            latest_version, []
                        )
                        if release_info and len(release_info) > 0:
                            upload_time = release_info[0].get("upload_time")
                            if upload_time:
                                try:
                                    release_date = datetime.strptime(upload_time, "%Y-%m-%dT%H:%M:%S")
                                except ValueError:
                                    with contextlib.suppress(ValueError):
                                        release_date = datetime.strptime(upload_time, "%Y-%m-%dT%H:%M:%S.%f")

                        age = _calculate_age(release_date)
                        package_info[package] = {"version": latest_version, "url": project_url, "age": age}
                    else:
                        package_info[package] = {
                            "version": latest_version,
                            "url": f"https://pypi.org/project/{package}/",
                            "age": "",
                        }
                except Exception as e:
                    print(f"Warning: Error getting info for {package}: {e!s}")
                    package_info[package] = {
                        "version": latest_version,
                        "url": f"https://pypi.org/project/{package}/",
                        "age": "",
                    }

        except subprocess.SubprocessError:
            print(f"Warning: Could not determine latest version for {package}.")

    return package_info


def _calculate_age(release_date: datetime | None) -> str:
    """Calculate human-readable age from release date."""
    if not release_date:
        return ""

    delta = datetime.now() - release_date
    days_ago = delta.days

    if days_ago == 0:
        hours_ago = delta.seconds // 3600
        if hours_ago == 0:
            minutes_ago = (delta.seconds % 3600) // 60
            return f"{minutes_ago} {'minute' if minutes_ago == 1 else 'minutes'}"
        return f"{hours_ago} {'hour' if hours_ago == 1 else 'hours'}"
    elif days_ago == 1:
        return "1 day"
    elif days_ago < 7:
        return f"{days_ago} days"
    elif days_ago < 31:
        weeks = days_ago // 7
        return f"{weeks} {'week' if weeks == 1 else 'weeks'}"
    elif days_ago < 365:
        months = days_ago // 30
        return f"{months} {'month' if months == 1 else 'months'}"
    else:
        years = days_ago // 365
        return f"{years} {'year' if years == 1 else 'years'}"


def update_requirements(requirements_path: str, config_path: str | None = None) -> None:
    """Update requirements.txt with the latest versions, except for excluded packages."""
    with open(requirements_path, newline="") as file:
        lines = file.readlines()

    excluded_packages: set[str] = read_excluded_packages(config_path) if config_path else set()

    pins: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = match_pin(line)
        if match and match.group("name") not in excluded_packages:
            pins.append((index, match))

    packages_to_update: list[str] = list(dict.fromkeys(match.group("name") for _, match in pins))
    latest_packages_info = get_latest_versions(packages_to_update)

    update_table: list[Any] = []

    for index, match in pins:
        package = match.group("name")
        package_info = latest_packages_info.get(package)
        if not package_info:
            continue

        latest_version = package_info["version"]
        current_version = match.group("version")
        if not latest_version or latest_version == current_version:
            continue

        line = lines[index]
        ending = line[len(line.rstrip("\r\n")) :]
        lines[index] = f"{match.group('head')}{latest_version}{match.group('tail')}{ending}"

        update_table.append(
            [
                package,
                current_version,
                latest_version,
                package_info.get("age", ""),
                package_info.get("url", ""),
            ]
        )

    if not update_table:
        print("All packages are already up to date!")
        return

    with open(requirements_path, "w", newline="") as file:
        file.writelines(lines)

    headers = ["NAME", "OLD", "NEW", "AGE", "INFO"]
    print(tabulate(update_table, headers=headers, tablefmt="simple"))
    print(
        f"\n requirements.txt updated with {len(update_table)} package{'s' if len(update_table) != 1 else ''}"
    )


def main() -> None:
    """Main function that is executed when the command is called."""
    cwd = os.getcwd()
    requirements_path = os.path.join(cwd, "requirements.txt")
    config_path = os.path.join(cwd, "cupdate.config.txt")

    if not os.path.exists(requirements_path):
        print(f"Error: {requirements_path} does not exist.")
        return

    config_exists = os.path.exists(config_path)
    if not config_exists:
        print(f"Note: {config_path} not found. All packages will be updated.")
    else:
        excluded = read_excluded_packages(config_path)
        if excluded:
            print(f"Note: {len(excluded)} package(s) excluded from update.")

    update_requirements(requirements_path, config_path if config_exists else None)


def cli_main() -> None:
    """CLI entry point."""
    main()


if __name__ == "__main__":
    main()
