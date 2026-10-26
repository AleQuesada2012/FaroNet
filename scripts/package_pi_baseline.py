"""Optional offline review archive; existing Pi clones normally update via Git.

Never include the Worker, venvs or secrets, or extract over an existing clone.
"""

from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
target = root / "output/faronet-pi-baseline-2026-10-25.tar.gz"
files = []
for folder, suffix in (("python/src", ".py"), ("python/tests", ".py"), ("fixtures", ".json")):
    files.extend((root / folder).rglob(f"*{suffix}"))
for suffix in (".md", ".html", ".svg", ".json", ".pdf"):
    files.extend((root / "hardware/breadboard").rglob(f"*{suffix}"))
files.extend(root / name for name in (
    "python/pyproject.toml", "python/requirements.txt", "python/requirements-gpio.txt",
    "python/README.md", "docs/optical-bringup.md", "docs/development.md",
))
target.parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(target, "w:gz") as archive:
    for path in sorted(set(files)):
        archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
print(target)
