"""Fetch pinned build tools and apply the checked-in integration patch."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts/mc-atlas/toolchain.json"


def run(*args: str, cwd: Path, env: dict | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def checkout(url: str, revision: str, dest: Path) -> None:
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        run("git", "init", str(dest), cwd=ROOT)
        run("git", "-C", str(dest), "remote", "add", "origin", url, cwd=ROOT)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True)
    if head.stdout.strip() != revision:
        run("git", "fetch", "--depth=1", "origin", revision, cwd=dest)
        run("git", "checkout", "--detach", "--force", revision, cwd=dest)
        shutil.rmtree(dest / "tooling/target", ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    lock = json.loads(CONFIG.read_text())
    generator = output / "generator"
    checkout("https://github.com/Aerhhh/MinecraftImageGenerator.git", lock["generator"], generator)
    # Compiled classes must never survive a toolchain or integration change.
    shutil.rmtree(generator / "tooling/target", ignore_errors=True)
    # These are disposable build checkouts, never the user's source checkout.
    run("git", "restore", "--source=HEAD", "--worktree", "tooling", cwd=generator)
    run("git", "apply", str(ROOT / "scripts/mc-atlas/tooling.patch"), cwd=generator)
    env = os.environ.copy()
    env["MAVEN_USER_HOME"] = str(output / "maven-home")
    wrapper = ["cmd", "/c", "mvnw.cmd"] if os.name == "nt" else ["sh", "./mvnw"]
    run(*wrapper, "-B", "-ntp", "-pl", "tooling", "-am", "compile", "dependency:build-classpath",
        f"-Dmaven.repo.local={output / 'maven-cache'}", "-Dmdep.outputFile=target/classpath.txt",
        cwd=generator, env=env)
    dependencies = (generator / "tooling/target/classpath.txt").read_text().strip()
    classpath = os.pathsep.join([str(generator / "tooling/target/classes"), dependencies])
    (output / "classpath.txt").write_text(classpath)
    (output / "toolchain.json").write_text(json.dumps(lock, indent=2) + "\n")


if __name__ == "__main__":
    main()
