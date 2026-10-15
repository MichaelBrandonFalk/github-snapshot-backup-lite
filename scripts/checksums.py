from hashlib import sha256
from pathlib import Path

for path in Path("downloads").iterdir():
    if path.suffix not in {".zip", ".deb"}:
        continue
    path.with_name(path.name + ".sha256").write_text(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.name}\n", encoding="ascii"
    )
