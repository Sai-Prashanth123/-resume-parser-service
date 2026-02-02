import os, sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    path = os.path.join(PROJECT_ROOT, "tests", "test_parsers_synthetic.py")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # Print the relevant lines from the failing test
    for i in range(214, 226):
        print(f"{i+1}: {lines[i].rstrip()}")
    # Find and print codepoints for the "Product Designer ..." line
    target = None
    for ln in lines:
        if "Product Designer" in ln:
            target = ln.rstrip("\n")
            break
    print("product line repr:", repr(target))
    if target:
        for ch in target:
            if ch.strip() and ch not in set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.'()-_/"):
                print("char", repr(ch), "ord", ord(ch))

    target2 = None
    for ln in lines:
        if "UX/UI Designer" in ln:
            target2 = ln.rstrip("\n")
            break
    print("uxui line repr:", repr(target2))
    if target2:
        for ch in target2:
            if ch.strip() and ch not in set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.'()-_/"):
                print("char", repr(ch), "ord", ord(ch))

    bullet_line = None
    for ln in lines:
        if "Designed complete UI/UX" in ln:
            bullet_line = ln.rstrip("\n")
            break
    print("bullet line repr:", repr(bullet_line))
    if bullet_line:
        stripped = bullet_line.lstrip()
        if stripped:
            print("bullet first char ord:", ord(stripped[0]))

    date_line = None
    for ln in lines:
        if "Aug 2024" in ln:
            date_line = ln.rstrip("\n")
            break
    print("date line repr:", repr(date_line))
    if date_line:
        for ch in date_line:
            if ch in {"-", "–", "—", "‑"}:
                print("dash char", repr(ch), "ord", ord(ch))


if __name__ == "__main__":
    main()

