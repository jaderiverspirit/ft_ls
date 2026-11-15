# ft_ls

A C implementation of the mandatory subset of `ls`: `-l`, `-R`, `-a`, `-r`, and `-t`, including combined flags and multiple path arguments.

## Build

```sh
make
./ft_ls
./ft_ls -la
./ft_ls -lRat ./src
make clean
make fclean
make re
```

Compile flags: `-Wall -Wextra -Werror -std=c11 -D_DEFAULT_SOURCE`.
Tested on Linux / GNU `ls`, with `LC_ALL=C`. This implementation uses POSIX directory and file metadata APIs and Linux's `<sys/sysmacros.h>`, so macOS/BSD may require platform-specific changes for timestamps and device-number formatting.

## Run tests

```sh
python3 tests/test_ft_ls.py
```

The tests invoke `ls -1` to avoid column formatting, which the subject does not require. The comparison uses `LC_ALL=C` and normalizes whitespace in long listings (the subject allows small padding differences).

## Architecture

- `src/main.c`: operand handling, directory reading, recursion, error status.
- `src/options.c`: parse short option groups and `--`.
- `src/entries.c`: dynamically sized file-entry vectors, ownership, `lstat`, path joins.
- `src/sort.c`: lexical and modification-time ordering (nanosecond precision), reverse ordering.
- `src/display.c`: permissions, user/group names, sizes, timestamps, block totals, symlink targets.
- `src/ft_ls.h`: common types and function declarations.

Every successful `entry_add` owns separate allocations for its name and path; `vector_free` releases them. Recursion deliberately ignores `.` and `..` and does not follow symlinks discovered inside directories. Options are shared between recursion levels.

## Subject scope / limits

Mandatory: executable `ft_ls`, C implementation, Makefile with usual rules, five specified options, combined flags, recursive listing, errors, proper memory management, and long-format information.

Not implemented: columns, ACLs, extended attributes, color output, and other optional `ls` switches. Fancy filename quoting and terminal-dependent rendering are not implemented.

## Evaluation discussion points

1. Why `lstat` rather than `stat` for directory entries? (`lstat` exposes symlinks without following them.)
2. Why must recursion be anticipated in the design? (Paths and metadata are carried independently for each directory.)
3. What does `-r` mean with `-t`? (Reverse the combined time-and-name ordering.)
4. How are `.` and `..` treated with `-aR`? (They are listed but never traversed recursively.)
5. How is a read failure handled? (Diagnostic to standard error, nonzero exit status.)
6. Which allocations must be released after a directory is processed? (The vector and each entry's two strings.)
7. Why calculate field widths before printing `-l`? (Uniform display alignment.)
