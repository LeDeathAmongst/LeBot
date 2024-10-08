import os
import sys
import subprocess  # Ensure subprocess is imported
from pathlib import Path
import setuptools
from setuptools import find_namespace_packages, setup

ROOT_FOLDER = Path(__file__).parent.absolute()
REQUIREMENTS_FOLDER = ROOT_FOLDER / "requirements"

# Since we're importing `redbot` package, we have to ensure that it's in sys.path.
sys.path.insert(0, str(ROOT_FOLDER))

from redbot import VersionInfo

version, _ = VersionInfo._get_version(ignore_installed=True)

with open("README.md", mode="r") as f:
    long_description = f.read()

def get_requirements(fp):
    return [
        line.strip()
        for line in fp.read().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

def extras_combined(*extra_names):
    return list(
        {
            req
            for extra_name, extra_reqs in extras_require.items()
            if not extra_names or extra_name in extra_names
            for req in extra_reqs
        }
    )

with open(REQUIREMENTS_FOLDER / "base.txt", encoding="utf-8") as fp:
    install_requires = get_requirements(fp)

extras_require = {}
for file in REQUIREMENTS_FOLDER.glob("extra-*.txt"):
    with file.open(encoding="utf-8") as fp:
        extras_require[file.stem[len("extra-") :]] = get_requirements(fp)

extras_require["dev"] = extras_combined()
extras_require["all"] = extras_combined("postgres")

python_requires = ">=3.8.1"
if not os.getenv("TOX_RED", False) or sys.version_info < (3, 12):
    python_requires += ",<3.12"

# Check for pyproject.toml existence and extract metadata
if os.path.isfile("pyproject.toml"):
    print("pyproject.toml exists")
    # Test: Check for project metadata in pyproject.toml
    try:
        result = subprocess.run(
            ["grep", "-A", "10", r"\[project\]", "pyproject.toml"],
            check=True,
            text=True,
            capture_output=True
        )
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error occurred while running grep:", e)
else:
    print("pyproject.toml does not exist")

setuptools.setup(
    name="LeBot",
    version=version,
    author="Star",
    author_email="skylar.rae.val@proton.me",
    description="A Multi-Purpose Discord Bot",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/LeDeathAmongst/LeBot",
    packages=find_namespace_packages(include=["redbot", "redbot.*"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=python_requires,
    install_requires=install_requires,
    extras_require=extras_require
)
