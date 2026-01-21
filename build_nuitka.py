#!/usr/bin/env python3
import argparse
import importlib.util
import os
import platform
import shutil
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build Sound Transport with Nuitka (app mode)."
    )
    parser.add_argument(
        "--entry",
        default="app.py",
        help="Entry point (default: app.py)",
    )
    parser.add_argument(
        "--name",
        default="SoundTransport",
        help="Output name (default: SoundTransport)",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Output directory (default: dist)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the output directory before building",
    )
    return parser.parse_args()


def using_apple_python(executable):
    path = os.path.realpath(executable)
    markers = (
        "Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework",
        "CommandLineTools/Library/Frameworks/Python3.framework",
    )
    return any(marker in path for marker in markers)


def module_available(name):
    return importlib.util.find_spec(name) is not None


def main() -> int:
    args = parse_args()
    if platform.system() == "Darwin" and using_apple_python(sys.executable):
        print(
            "Apple Python detected. Nuitka standalone builds require a "
            "python.org or Homebrew CPython install.",
            file=sys.stderr,
        )
        print(
            "Install CPython, create a new venv with it, then rerun this script.",
            file=sys.stderr,
        )
        return 2
    if not module_available("nuitka"):
        print(
            "Nuitka is not installed in this Python environment.",
            file=sys.stderr,
        )
        print(
            f"Run: {sys.executable} -m pip install nuitka",
            file=sys.stderr,
        )
        return 2
    entry = os.path.abspath(args.entry)
    if not os.path.exists(entry):
        print(f"Entry not found: {entry}", file=sys.stderr)
        return 2

    output_dir = os.path.abspath(args.output_dir)
    if args.clean and os.path.isdir(output_dir):
        shutil.rmtree(output_dir)

    system = platform.system()
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=app",
        f"--output-dir={output_dir}",
        f"--output-filename={args.name}",
        "--include-package=sounddevice",
    ]

    if system == "Darwin":
        cmd.extend(
            [
                "--include-module=AppKit",
                "--include-module=Foundation",
                "--include-module=WebKit",
                "--include-module=objc",
                "--include-package=PyObjCTools",
            ]
        )
    if system == "Windows":
        cmd.append("--windows-console-mode=disable")

    cmd.append(entry)

    print("Running:")
    print(" ".join(cmd))
    subprocess.check_call(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
