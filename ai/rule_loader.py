from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RULES_DIR = BASE_DIR / "ai" / "rules"


def load_rules(files):
    contents = []

    for filename in files:
        path = RULES_DIR / filename

        if path.exists():
            contents.append(
                f"===== {filename} =====\n"
                f"{path.read_text(encoding='utf-8')}"
            )

    return "\n\n".join(contents)