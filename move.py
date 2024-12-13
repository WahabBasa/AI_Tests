import os
from pathlib import Path

def create_css_files():
    root = Path.cwd()
    css_dir = root / "static" / "css"
    css_dir.mkdir(exist_ok=True)

    css_files = [
        "testproj_style.css",
        "Second_Page_style.css",
        "page3_style.css",
        "page4_style.css",
        "page5_style.css"
    ]

    for file in css_files:
        path = css_dir / file
        path.touch()
        print(f"Created: {path}")

if __name__ == "__main__":
    create_css_files()
    print("\nCSS files created!")