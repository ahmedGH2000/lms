"""Apply reviewed, version-specific fixes; refuse unknown or conflicting source."""
from pathlib import Path
import subprocess
import sys

TARGETS = (
    ("lms", "87168fc7b2f24559e474ea4702cf1aa63b0db4e8", "lms-nightjar-activity.patch"),
    ("frappe", "b0b5b99a1d9d2cb3d54b32293d3854bf2c15f4a4", "frappe-user-defaults.patch"),
    ("lms", "87168fc7b2f24559e474ea4702cf1aa63b0db4e8", "lms-member-feedback.patch"),
)


def apply(bench):
    patches = Path(__file__).with_name("patches")
    pending = []
    for name, revision, filename in TARGETS:
        repo = bench / "apps" / name
        actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise SystemExit(f"Refusing {filename}: {name} is not at its reviewed revision.")
        patch = str(patches / filename)
        command = ["git", "-C", str(repo), "apply"]
        if subprocess.run([*command, "--reverse", "--check", patch], capture_output=True).returncode == 0:
            continue
        if subprocess.run([*command, "--check", patch], capture_output=True).returncode:
            raise SystemExit(f"Cannot apply {filename}: source has conflicting changes. No reset was performed.")
        pending.append((command, patch))
    # Validate every patch before changing any repository.
    for command, patch in pending:
        subprocess.run([*command, patch], check=True)
        print(f"Applied {Path(patch).name}")


if __name__ == "__main__":
    apply(Path(sys.argv[1]).resolve())
