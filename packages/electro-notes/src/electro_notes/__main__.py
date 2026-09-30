"""``python -m electro_notes check|upgrade|strip FILE…``

check    — read each file (migrating if needed) and say what is in it, or what is wrong
upgrade  — rewrite files in the current format version
strip    — drop outputs and results (the document alone, e.g. for version control)
"""

import sys

from .format import load
from .issues import FormatError


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("check", "upgrade", "strip"):
        print(__doc__.strip())
        return 2
    command, paths = argv[0], argv[1:]
    failed = 0
    for path in paths:
        try:
            nb = load(path)
        except (FormatError, OSError) as err:
            print(f"{path}: {err!r}")
            failed += 1
            continue
        if command == "upgrade":
            nb.save(path)
        elif command == "strip":
            nb.strip_outputs().save(path)
        print(f"{path}: {nb!r}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
