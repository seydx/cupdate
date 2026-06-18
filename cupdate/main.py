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


def read_requirements(file_path: str) -> dict[str, str]:
    """Read requirements.txt and return a dictionary with package and version."""
    requirements: dict[str, str] = {}
    if not os.path.exists(file_path):
        return requirements

    with open(file_path) as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "==" in line:
                package, version = line.split("==", 1)
                requirements[package.strip()] = version.strip()
            elif ">=" in line:
                package, version = line.split(">=", 1)
                requirements[package.strip()] = f">={version.strip()}"
            elif "<=" in line:
                package, version = line.split("<=", 1)
                requirements[package.strip()] = f"<={version.strip()}"
            else:
                requirements[line.strip()] = ""

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

            version_match = re.search(r"Available versions: ([\d\.]+)", output)
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
    requirements = read_requirements(requirements_path)
    excluded_packages: set[str] = read_excluded_packages(config_path) if config_path else set()

    packages_to_update: list[str] = [pkg for pkg in requirements if pkg not in excluded_packages]
    latest_packages_info = get_latest_versions(packages_to_update)

    updated_requirements: dict[str, str] = {}
    update_table: list[Any] = []
    updates_count = 0

    for package, version in requirements.items():
        if package in latest_packages_info:
            package_info = latest_packages_info[package]
            latest_version = package_info["version"]

            if latest_version and latest_version != version.replace(">=", "").replace("<=", ""):
                updates_count += 1

                # Store new version (preserve operators)
                if version.startswith(">="):
                    updated_requirements[package] = f">={latest_version}"
                elif version.startswith("<="):
                    updated_requirements[package] = f"<={latest_version}"
                else:
                    updated_requirements[package] = latest_version

                update_table.append(
                    [
                        package,
                        version,
                        latest_version,
                        package_info.get("age", ""),
                        package_info.get("url", ""),
                    ]
                )
            else:
                updated_requirements[package] = version
        else:
            updated_requirements[package] = version

    # Write updated requirements
    with open(requirements_path, "w") as file:
        for package, version in updated_requirements.items():
            if version:
                if version.startswith(">=") or version.startswith("<="):
                    operator = version[:2]
                    version = version[2:]
                else:
                    operator = "=="
                file.write(f"{package}{operator}{version}\n")
            else:
                file.write(f"{package}\n")

    # Print update table
    if update_table:
        headers = ["NAME", "OLD", "NEW", "AGE", "INFO"]
        print(tabulate(update_table, headers=headers, tablefmt="simple"))
        print(f"\n requirements.txt updated with {updates_count} package{'s' if updates_count != 1 else ''}")
    else:
        print("All packages are already up to date!")


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
