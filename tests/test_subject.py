#!/usr/bin/env python3
"""Independent ft_ls v4.0 mandatory-subject regression tests.

Place this file at tests/test_subject.py and run from the repository root:
    python3 tests/test_subject.py
    python3 tests/test_subject.py --build-checks --valgrind --stress

Requires Python 3 (standard library), a built ./ft_ls, and system `ls`.
GNU ls is used as the behavioral oracle. -1 is passed ONLY to GNU ls because
multi-column output is explicitly outside the subject's mandatory requirements.

Tests are not adapted to the ft_ls implementation. They can reveal failures.
No finite test suite proves equivalence for all possible filesystem states.
"""

import argparse
import difflib
import itertools
import os
from pathlib import Path
import random
import re
import stat
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "ft_ls"
FLAGS = "lRart"

# The subject explicitly does not require locale handling. Fix a consistent
# reference environment and suppress presentation settings not under test.
ENV = os.environ.copy()
for key in ("BLOCK_SIZE", "LS_BLOCK_SIZE", "POSIXLY_CORRECT", "LS_OPTIONS"):
    ENV.pop(key, None)
ENV.update({"LC_ALL": "C", "LANGUAGE": "C", "TZ": "UTC",
            "QUOTING_STYLE": "literal", "TIME_STYLE": "locale"})


class Suite:
    def __init__(self, verbose=False, max_failures=30):
        self.verbose = verbose
        self.max_failures = max_failures
        self.total = 0
        self.failed = 0
        self.padded = 0
        self.skipped = []
        self.groups = {}
        self.examples = []

    def result(self, group, label, ok, detail="", padded=False):
        self.total += 1
        stats = self.groups.setdefault(group, [0, 0])
        stats[0] += 1
        if padded:
            self.padded += 1
        if ok:
            if self.verbose:
                print("PASS", group, label, "(padding difference)" if padded else "")
        else:
            self.failed += 1
            stats[1] += 1
            if len(self.examples) < self.max_failures:
                self.examples.append((group, label, detail))
            if self.verbose:
                print("FAIL", group, label)

    def skip(self, label, reason):
        self.skipped.append((label, reason))
        if self.verbose:
            print("SKIP", label, reason)

    def summary(self):
        print("\n=== ft_ls subject v4.0: independent test results ===")
        for group, (count, failed) in self.groups.items():
            print("{:<30} {:>5} checks, {:>4} failed".format(group, count, failed))
        print("TOTAL: {} checks; {} passed; {} failed".format(
            self.total, self.total - self.failed, self.failed))
        if self.padded:
            print("NOTE: {} long-format output differences were only in column padding;".format(self.padded))
            print("      the subject permits minor alignment differences.")
        for label, why in self.skipped:
            print("SKIPPED: {} ({})".format(label, why))
        for group, label, detail in self.examples:
            print("\n--- FAIL: [{}] {} ---".format(group, label))
            print(detail[:3500])
        if self.failed:
            print("\nFAILURES FOUND: inspect each difference; do not change tests to hide it.")
        else:
            print("\nAll executed checks passed. This is NOT proof of exhaustive correctness.")
        return self.failed == 0


def command(program, args, cwd, timeout=8):
    try:
        return subprocess.run([str(program), *args], cwd=str(cwd), env=ENV,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        return exc


def padding_canonical(data):
    """Allow only spacing *between* long-format columns, not missing columns.

    Preserve the filename remainder (including internal whitespace). The source
    has explicitly allowed small padding differences. Control-character name
    cases are compared STRICTLY, because line-oriented parsing is ambiguous.
    """
    out = []
    for line in data.splitlines(keepends=True):
        raw = line.rstrip(b"\n")
        if raw.startswith(b"total "):
            out.append((b"total", raw.split()[1:]))
        elif re.match(rb"^[-bcdlps][-rwxStTs]{9}[+.@]?\s+\d+\s", raw):
            parts = raw.split(None, 8)
            if len(parts) != 9:
                return None
            out.append((b"entry", tuple(parts)))
        else:
            out.append((b"literal", raw))
    return out


def to_text(data):
    return data.decode("utf-8", errors="backslashreplace")


def mismatch_summary(expected, actual, args):
    if isinstance(actual, subprocess.TimeoutExpired):
        return "ft_ls TIMED OUT for args={!r} after {}s".format(args, actual.timeout)
    if isinstance(expected, subprocess.TimeoutExpired):
        return "system ls timed out; invalid benchmark case: {!r}".format(args)
    lines = ["args: {!r}".format(args),
             "return code: system={}  ft_ls={}".format(expected.returncode, actual.returncode),
             "system stderr: {!r}".format(to_text(expected.stderr[:500])),
             "ft_ls stderr:  {!r}".format(to_text(actual.stderr[:500]))]
    a = to_text(expected.stdout).splitlines(keepends=True)
    b = to_text(actual.stdout).splitlines(keepends=True)
    delta = "".join(itertools.islice(difflib.unified_diff(a, b,
                               fromfile="system ls stdout", tofile="ft_ls stdout"), 60))
    lines.append(delta[:2200] if delta else "stdout matches")
    return "\n".join(lines)


def compare(suite, group, label, args, cwd, allow_padding=True,
            expected_error=False, require_stderr=None, timeout=8):
    """Compare stdout and exit code; independently inspect error diagnostics.

    Exact stderr messages (including GNU's branding and quoting) are not
    required, but errors must be nonzero and identify the problem.
    """
    expected = command("ls", ["-1", *args], cwd, timeout)
    actual = command(BINARY, args, cwd, timeout)
    if isinstance(expected, subprocess.TimeoutExpired):
        suite.skip(label, "system ls timed out; oracle unavailable")
        return
    if isinstance(actual, subprocess.TimeoutExpired):
        suite.result(group, label, False, mismatch_summary(expected, actual, args))
        return
    ok = expected.returncode == actual.returncode
    if expected_error:
        ok = ok and expected.returncode != 0 and actual.returncode != 0
    if require_stderr is not None:
        ok = ok and require_stderr.encode("utf-8") in actual.stderr
    stdout_equal = expected.stdout == actual.stdout
    padded = False
    # Only ordinary long-format names may receive a spacing tolerance.
    before_separator = args[:args.index("--")] if "--" in args else args
    long_requested = any(arg.startswith("-") and "l" in arg[1:]
                         for arg in before_separator)
    if not stdout_equal and allow_padding and long_requested:
        e = padding_canonical(expected.stdout)
        a = padding_canonical(actual.stdout)
        if e is not None and e == a:
            stdout_equal = True
            padded = True
    ok = ok and stdout_equal
    suite.result(group, label, ok, mismatch_summary(expected, actual, args) if not ok else "", padded)


def make_fixtures(root):
    """Self-contained test data: never modifies files outside its temp folder."""
    for d in ("dir", "dir/sub", "dir/sub/deep", "dir/.hidden_dir",
              "adir", "zdir", "empty", "permissions", "times",
              "dir with spaces", "dir:colon", "many"):
        (root / d).mkdir(parents=True, exist_ok=True)

    files = {
        "afile": b"hello", "zfile": b"world", "zero": b"",
        ".hidden": b"hidden", "..double_dot": b"double",
        "-l": b"looks like an option", "-a": b"also an option",
        "-": b"single dash", "name with spaces": b"spaces",
        " leading": b"leading space", "trailing ": b"trailing space",
        "tabs\tinside": b"tab", "line\nbreak": b"newline",
        "semi;colon": b"shell syntax", "dollar$sign": b"shell syntax",
        "square[brackets]": b"shell syntax", "quote'and\"double": b"quote",
        "back\\slash": b"backslash", "utf8_\N{GREEK SMALL LETTER PI}": b"unicode",
        "dir/visible": b"visible", "dir/.invisible": b"hidden in dir",
        "dir/sub/child": b"child", "dir/sub/deep/grandchild": b"grandchild",
        "dir/.hidden_dir/secret": b"secret",
        "dir with spaces/file name": b"nested spaces",
        "dir:colon/colon_file": b"colon",
        "permissions/read_only": b"read only",
        "permissions/executable": b"run",
        "permissions/no_perms": b"no permissions",
        "permissions/setuid": b"set uid",
        "permissions/setgid": b"set gid",
        "permissions/sticky": b"sticky",
        "times/old": b"old", "times/new": b"new",
        "times/same_a": b"a", "times/same_b": b"b",
        "times/nano_1": b"nanosecond", "times/nano_2": b"nanosecond",
        "times/future": b"future", "times/ancient": b"ancient",
        "long_" + "a" * 190: b"long filename",
    }
    for name, contents in files.items():
        (root / name).write_bytes(contents)
    (root / "huge_sparse").open("wb").close()
    with (root / "huge_sparse").open("r+b") as f:
        f.truncate(5_000_000_000)  # Sparse file, only metadata storage required.

    (root / "hardlink").hardlink_to(root / "afile")
    (root / "link_file").symlink_to("afile")
    (root / "link_dir").symlink_to("dir", target_is_directory=True)
    (root / "link_chain").symlink_to("link_dir", target_is_directory=True)
    (root / "dangling").symlink_to("missing-target")
    (root / "self_loop").symlink_to("self_loop")
    (root / "dir/sub/back_to_parent").symlink_to("..", target_is_directory=True)
    (root / "dir/link_to_file").symlink_to("../afile")
    (root / "dir/link_to_dir").symlink_to("sub", target_is_directory=True)
    os.mkfifo(root / "named_pipe")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(str(root / "unix_socket"))
    finally:
        sock.close()

    modes = {"read_only": 0o400, "executable": 0o751,
             "no_perms": 0o000, "setuid": 0o4751,
             "setgid": 0o2751, "sticky": 0o1755}
    for name, mode in modes.items():
        os.chmod(root / "permissions" / name, mode)

    # UTC seconds chosen far apart plus identical and ns-only timestamps.
    times = {"ancient": (946684800, 0), "old": (1500000000, 0),
             "same_a": (1700000000, 0), "same_b": (1700000000, 0),
             "nano_1": (1700000001, 1), "nano_2": (1700000001, 900000000),
             "new": (1800000000, 0), "future": (2200000000, 0)}
    for name, (sec, nanos) in times.items():
        stamp = sec * 10**9 + nanos
        os.utime(root / "times" / name, ns=(stamp, stamp))
    # Ensure directory operands themselves have distinct timestamps.
    for name, sec in (("adir", 1600000000), ("zdir", 1700000000),
                      ("empty", 1800000000)):
        os.utime(root / name, ns=(sec * 10**9, sec * 10**9))
    return root


def static_matrix(suite, root):
    # All 2^5 mandatory flag sets; deliberately vary flag order and arguments.
    scenarios = [
        [], ["."], ["dir"], ["dir/sub"], ["empty"], ["afile"],
        ["link_file"], ["dangling"], ["link_dir"], ["link_chain"],
        ["permissions"], ["times"], ["adir", "zdir"],
        ["zdir", "link_dir", "adir"], ["link_dir", "dir", "zdir"],
        ["zfile", "afile"], ["afile", "dir"],
        ["afile", "dir", "zfile", "empty", "dangling"],
        ["dir", "dir", "afile"], ["named_pipe", "unix_socket", "link_file"],
        ["missing", "afile", "dir"],
        ["dir with spaces", "dir:colon", "dir/sub"],
        ["huge_sparse", "hardlink", "zero"],
    ]
    idx = 0
    for n in range(len(FLAGS) + 1):
        for combo in itertools.combinations(FLAGS, n):
            flags = "-" + "".join(combo) if combo else None
            for operands in scenarios:
                args = ([flags] if flags else []) + operands
                compare(suite, "32 flag sets x scenarios", str(idx) + " " + repr(args),
                        args, root, allow_padding=True)
                idx += 1


def special_cases(suite, root):
    cases = [
        ("file before option", ["dir", "-l"]),
        ("multiple options interspersed", ["dir", "-R", "adir", "-a", "-t"]),
        ("combined flags after file", ["afile", "-lRat", "dir"]),
        ("repeated options", ["-llll", "-aaRRtt", "dir"]),
        ("both flag orderings", ["-Rltar", "dir"]),
        ("option before separator", ["-l", "--", "-a"]),
        ("option-looking filename after --", ["--", "-l", "-a"]),
        ("-- after operand", ["dir", "--", "-l"]),
        ("literal minus operand", ["-"]),
        ("double -- literal", ["--", "--"]),
        ("empty directory", ["empty"]),
        ("empty long directory", ["-l", "empty"]),
        ("trailing slash directory", ["dir/"]),
        ("trailing slash symlink directory", ["link_dir/"]),
        ("trailing slash ordinary file", ["afile/"]),
        ("trailing slash file symlink", ["link_file/"]),
        ("self symlink loop", ["self_loop"]),
        ("symlink loop with -l", ["-l", "self_loop"]),
        ("symlink -l first vs dereference", ["-l", "link_dir", "dir"]),
        ("symlink recursive", ["-R", "link_dir"]),
        ("recursive nested symlink cycle", ["-Ra", "dir"]),
        ("recursive reverse time", ["-Rrat", "dir", "times"]),
        ("current directory path", ["."]),
        ("parent directory relative path", ["dir/sub/.."]),
        ("multiple missing plus existing", ["missing1", "afile", "missing2", "dir"]),
        ("duplicate directory arguments", ["dir", "dir"]),
        ("duplicate file arguments", ["afile", "afile"]),
        ("special permission bits", ["-l", "permissions"]),
        ("special file type", ["-l", "named_pipe", "unix_socket"]),
        ("nanosecond sort and tied timestamps", ["-lt", "times"]),
        ("reverse of timestamp ties", ["-ltr", "times"]),
        ("old/future timestamp display", ["-l", "times"]),
        ("sparse large file formatting", ["-l", "huge_sparse"]),
        ("spaces in filename", ["--", "name with spaces", " leading", "trailing "]),
        ("spaces in filename long", ["-l", "--", "name with spaces"]),
        ("spaces in directory", ["-lRa", "dir with spaces"]),
        ("hidden nested recursion", ["-Ra", "dir/.hidden_dir"]),
        ("links count and total blocks", ["-la", "."]),
        ("special mode formatting", ["-l", "permissions/setuid", "permissions/setgid", "permissions/sticky"]),
        ("mixed symlink files and dirs under reverse time", ["-ltrR", "link_dir", "link_file", "times", "adir"]),
        ("missing operand amid reverse-time directories", ["adir", "-ltrR", "missing", "unix_socket", "times", "dangling"]),
        ("UTF-8 name under C locale", ["-a", "--", "utf8_\N{GREEK SMALL LETTER PI}"]),
        ("leading dash filename", ["-l", "--", "-l"]),
        ("long file name", ["-l", "long_" + "a" * 190]),
    ]
    for label, args in cases:
        # Test strict output for special filenames to prevent lost whitespace.
        strict_names = any("\n" in item or item in (" leading", "trailing ") for item in args)
        compare(suite, "special behavior", label, args, root,
                allow_padding=not strict_names)

    # Literal separators and unusual names: compare bytes, never normalize.
    for name in ("line\nbreak", "tabs\tinside", " leading", "trailing ",
                 "semi;colon", "dollar$sign", "square[brackets]",
                 "quote'and\"double", "back\\slash"):
        for option in ([], ["-l"]):
            args = [*option, "--", name]
            compare(suite, "unusual filenames", repr(args), args, root,
                    allow_padding=False)

    errors = [
        ("unknown flag -z", ["-z"], "invalid option"),
        ("unknown flag combined", ["-laz", "dir"], "invalid option"),
        ("unknown flag after operand", ["dir", "-z"], "invalid option"),
        ("missing file", ["missing_xyz"], "missing_xyz"),
        ("missing alongside valid", ["missing_xyz", "afile"], "missing_xyz"),
        ("non-directory component", ["afile/child"], "afile/child"),
    ]
    for label, args, stderr_piece in errors:
        compare(suite, "errors and status", label, args, root, expected_error=True,
                require_stderr=stderr_piece)


def device_cases(suite, root):
    """Use existing read-only /dev device nodes if this is a Linux machine."""
    nodes = [name for name in ("/dev/null", "/dev/zero", "/dev/random")
             if os.path.exists(name) and stat.S_ISCHR(os.stat(name).st_mode)]
    if not nodes:
        suite.skip("character devices", "no suitable character devices")
        return
    for node in nodes:
        compare(suite, "character devices", "long " + node,
                ["-l", node], root)
    if len(nodes) > 1:
        compare(suite, "character devices", "multiple devices",
                ["-lt", *nodes], root)


def output_error_case(suite, root):
    """Use /dev/full to verify write errors are not silently accepted."""
    if not os.path.exists("/dev/full"):
        suite.skip("write failure", "/dev/full not available")
        return
    try:
        with open("/dev/full", "wb") as sink:
            system = subprocess.run(["ls", "-1", "dir"], cwd=root, env=ENV,
                                    stdout=sink, stderr=subprocess.PIPE, timeout=8)
        with open("/dev/full", "wb") as sink:
            actual = subprocess.run([str(BINARY), "dir"], cwd=root, env=ENV,
                                    stdout=sink, stderr=subprocess.PIPE, timeout=8)
        ok = system.returncode != 0 and actual.returncode != 0
        suite.result("write failures", "/dev/full output write failure", ok,
                     "system status={} ft_ls status={}\nft_ls stderr={!r}".format(
                         system.returncode, actual.returncode, actual.stderr[:200]))
    except (OSError, subprocess.TimeoutExpired) as exc:
        suite.skip("write failure", str(exc))


def directed_assertions(suite, root):
    """Assertions not dependent solely on GNU ls output equivalence."""
    def run(args):
        return command(BINARY, args, root)

    noall = run(["dir"])
    allfiles = run(["-a", "dir"])
    if isinstance(noall, subprocess.TimeoutExpired) or isinstance(allfiles, subprocess.TimeoutExpired):
        suite.result("independent invariants", "hidden visibility", False,
                     "Timed out")
    else:
        names = noall.stdout.splitlines()
        allnames = allfiles.stdout.splitlines()
        ok = (b".invisible" not in names and b".hidden_dir" not in names
              and b"." in allnames and b".." in allnames
              and b".invisible" in allnames and b".hidden_dir" in allnames)
        suite.result("independent invariants", "-a includes ., .. and hidden entries", ok,
                     "default={!r}\n-a={!r}".format(names, allnames))
    forward = run(["times"])
    reverse = run(["-r", "times"])
    if isinstance(forward, subprocess.TimeoutExpired) or isinstance(reverse, subprocess.TimeoutExpired):
        suite.result("independent invariants", "reverse order", False, "Timed out")
    else:
        suite.result("independent invariants", "-r reverses alphabetically sorted names",
                     reverse.stdout.splitlines() == list(reversed(forward.stdout.splitlines())),
                     "forward={!r}\nreverse={!r}".format(forward.stdout, reverse.stdout))
    r = run(["-Ra", "dir"])
    if isinstance(r, subprocess.TimeoutExpired):
        suite.result("independent invariants", "symlink recursion terminates", False, "Timed out")
    else:
        suite.result("independent invariants", "-R never traverses nested directory symlink",
                     r.returncode == 0 and b"dir/sub/back_to_parent:" not in r.stdout,
                     "rc={} output={!r}".format(r.returncode, r.stdout[:600]))


def fuzz_cases(suite, root, count):
    """Reproducible random argument permutations; no implementation assumptions."""
    rng = random.Random(42042)
    operands = ["dir", "dir/sub", "adir", "zdir", "empty", "times",
                "permissions", "afile", "zfile", "link_dir", "link_file",
                "dangling", "self_loop", "missing", "named_pipe", "unix_socket",
                "hardlink", "dir with spaces", "huge_sparse"]
    for i in range(count):
        flags = "".join(rng.sample(FLAGS, rng.randrange(len(FLAGS) + 1)))
        values = [rng.choice(operands) for _ in range(rng.randint(1, 5))]
        if flags:
            pos = rng.randrange(len(values) + 1)
            values.insert(pos, "-" + flags)
        if rng.randrange(6) == 0:
            values.insert(0, "-a")
        compare(suite, "deterministic fuzz", "seed=42042 case=" + str(i),
                values, root)


def permission_errors(suite, root):
    folder = root / "private_dir"
    folder.mkdir()
    (folder / "secret").write_text("secret")
    os.chmod(folder, 0)
    try:
        # Root/privileged sessions can still read it, so no useful denial test.
        try:
            with os.scandir(folder):
                pass
        except PermissionError:
            for label, args in [
                ("unreadable directory", ["private_dir"]),
                ("unreadable recursive directory", ["-R", "private_dir"]),
                ("unreadable amidst others", ["adir", "private_dir", "afile"]),
            ]:
                compare(suite, "permissions errors", label, args, root,
                        expected_error=True, require_stderr="private_dir")
        else:
            suite.skip("permission-denied directory", "current user can still read mode-000 directory")
    finally:
        os.chmod(folder, 0o700)


def stress_tests(suite, root):
    # Large directory and moderately deep hierarchy. Optional because of time.
    for i in range(1600):
        (root / "many" / "item_{:05d}".format(i)).write_bytes(b"x")
    for depth in range(22):
        p = root / "deep_tree" / ("sub/" * depth)
        p.mkdir(parents=True, exist_ok=True)
        (p / "leaf").write_bytes(b"x")
    for label, args in [
        ("1600 entries plain", ["many"]),
        ("1600 entries reversed", ["-r", "many"]),
        ("1600 entries long", ["-l", "many"]),
        ("1600 entries time", ["-t", "many"]),
        ("22 directory levels", ["-R", "deep_tree"]),
        ("22 levels all long", ["-lRa", "deep_tree"]),
    ]:
        compare(suite, "optional stress", label, args, root, timeout=25)


def makefile_checks(suite):
    make = shutil.which("make")
    if not make:
        suite.skip("Makefile", "make not installed")
        return
    if not (ROOT / "Makefile").is_file():
        suite.result("optional Makefile", "Makefile exists", False, "Missing Makefile")
        return
    # Isolated copy: do not clean or modify the user's repository.
    with tempfile.TemporaryDirectory(prefix="ft_ls_make_") as tmp:
        temp = Path(tmp)
        shutil.copy2(ROOT / "Makefile", temp / "Makefile")
        shutil.copytree(ROOT / "src", temp / "src", ignore=shutil.ignore_patterns("*.o"))

        def mk(*args):
            return subprocess.run([make, *args], cwd=temp, env=ENV,
                                  capture_output=True, text=True, timeout=40)

        try:
            first = mk()
            suite.result("optional Makefile", "make builds ft_ls",
                         first.returncode == 0 and (temp / "ft_ls").is_file(),
                         "stdout={}\nstderr={}".format(first.stdout, first.stderr))
            if first.returncode != 0:
                return
            second = mk("-n")
            suite.result("optional Makefile", "second make recompiles nothing",
                         second.returncode == 0 and (not second.stdout.strip() or
                             "Nothing to be done" in second.stdout or
                             "is up to date" in second.stdout),
                         "make -n stdout={!r}".format(second.stdout))
            header = temp / "src" / "ft_ls.h"
            now = time.time() + 5
            os.utime(header, (now, now))
            third = mk("-n")
            suite.result("optional Makefile", "header change triggers rebuild",
                         third.returncode == 0 and "-c" in third.stdout,
                         "make -n stdout={!r}".format(third.stdout[:600]))
            # Restore source timestamp to avoid future-dated file warnings.
            os.utime(header, None)
            clean = mk("clean")
            objs = list((temp / "src").glob("*.o"))
            suite.result("optional Makefile", "make clean keeps executable",
                         clean.returncode == 0 and not objs and (temp / "ft_ls").is_file(),
                         "rc={} remaining objects={!r}".format(clean.returncode, objs))
            fclean = mk("fclean")
            suite.result("optional Makefile", "make fclean removes executable",
                         fclean.returncode == 0 and not (temp / "ft_ls").exists(),
                         "rc={}".format(fclean.returncode))
            rebuild = mk("re")
            suite.result("optional Makefile", "make re rebuilds",
                         rebuild.returncode == 0 and (temp / "ft_ls").is_file(),
                         "stderr={!r}".format(rebuild.stderr[:600]))
        except subprocess.TimeoutExpired:
            suite.result("optional Makefile", "make timeout", False,
                         "build/check exceeded 40s")


def valgrind_checks(suite, root):
    vg = shutil.which("valgrind")
    if not vg:
        suite.skip("Valgrind", "valgrind not installed")
        return
    cases = [("recursive long all", ["-lRa", "dir"]),
             ("mixed paths", ["-tr", "zdir", "afile", "link_dir"]),
             ("missing path", ["missing"]),
             ("invalid option", ["-z"])]
    for label, args in cases:
        cmd = [vg, "--leak-check=full", "--show-leak-kinds=definite,possible",
               "--errors-for-leak-kinds=definite,possible", "--error-exitcode=97",
               str(BINARY), *args]
        try:
            res = subprocess.run(cmd, cwd=root, env=ENV,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=35)
        except subprocess.TimeoutExpired:
            suite.result("optional Valgrind", label, False, "Valgrind timed out")
            continue
        # Valgrind forwards the command's own nonzero exit status for errors.
        ok = (res.returncode != 97 and
              re.search(rb"ERROR SUMMARY:\s+0 errors", res.stderr) is not None and
              b"All heap blocks were freed" in res.stderr)
        suite.result("optional Valgrind", label, ok,
                     "rc={}\n{}".format(res.returncode, to_text(res.stderr[-1600:])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-checks", action="store_true", help="test Makefile in an isolated copy")
    parser.add_argument("--all", action="store_true", help="enable Makefile, Valgrind and stress checks")
    parser.add_argument("--valgrind", action="store_true", help="check memory on four execution paths")
    parser.add_argument("--stress", action="store_true", help="test 1600 files and deep recursive trees")
    parser.add_argument("--fuzz", type=int, default=150, help="deterministic random argument tests (default 150)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--max-failures", type=int, default=15)
    args = parser.parse_args()
    if not BINARY.is_file() or not os.access(BINARY, os.X_OK):
        parser.error("missing executable ./ft_ls; run 'make' from the project root first")
    if not shutil.which("ls"):
        parser.error("system 'ls' not found")
    if args.fuzz < 0:
        parser.error("--fuzz must be nonnegative")
    if args.all:
        args.build_checks = args.valgrind = args.stress = True
    suite = Suite(args.verbose, args.max_failures)
    with tempfile.TemporaryDirectory(prefix="ft_ls_subject_") as tmp:
        root = make_fixtures(Path(tmp))
        static_matrix(suite, root)
        special_cases(suite, root)
        device_cases(suite, root)
        output_error_case(suite, root)
        directed_assertions(suite, root)
        fuzz_cases(suite, root, args.fuzz)
        permission_errors(suite, root)
        if args.stress:
            stress_tests(suite, root)
        if args.valgrind:
            valgrind_checks(suite, root)
    if args.build_checks:
        makefile_checks(suite)
    success = suite.summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
