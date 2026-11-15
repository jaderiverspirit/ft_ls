#include "ft_ls.h"
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int g_errors = 0;

static int load_directory(const char *path, const t_options *opts, t_vector *v)
{
    DIR *dir;
    struct dirent *ent;
    char *joined;
    int saved;

    dir = opendir(path);
    if (!dir) { report_directory_error(path); g_errors = 1; return -1; }
    errno = 0;
    while ((ent = readdir(dir)))
    {
        if (!opts->all && ent->d_name[0] == '.') { errno = 0; continue; }
        joined = join_path(path, ent->d_name);
        if (!joined || entry_add(v, ent->d_name, joined) < 0)
        {
            free(joined);
            fprintf(stderr, "ft_ls: memory allocation failed\n");
            g_errors = 1;
            closedir(dir);
            return -1;
        }
        if (!v->items[v->len - 1].stat_ok) g_errors = 1;
        free(joined);
        errno = 0;
    }
    saved = errno;
    if (closedir(dir) < 0 && !saved) saved = errno;
    if (saved)
    {
        errno = saved;
        report_error(path);
        g_errors = 1;
    }
    return saved ? -1 : 0;
}

int list_directory(const char *path, const t_options *opts,
    int heading, int *printed)
{
    t_vector entries = {0};
    size_t i;

    if (load_directory(path, opts, &entries) < 0)
    {
        vector_free(&entries);
        return -1;
    }
    sort_entries(&entries, opts);
    if (heading)
    {
        if (*printed) putchar('\n');
        printf("%s:\n", path);
    }
    if (print_entries(&entries, opts, 1) < 0) g_errors = 1;
    *printed = 1;
    if (opts->recursive)
    {
        for (i = 0; i < entries.len; ++i)
        {
            t_entry *e = &entries.items[i];
            if (e->stat_ok && S_ISDIR(e->st.st_mode)
                && strcmp(e->name, ".") && strcmp(e->name, ".."))
                list_directory(e->path, opts, 1, printed);
        }
    }
    vector_free(&entries);
    return 0;
}

int main(int argc, char **argv)
{
    t_options opts;
    t_vector operands = {0}, files = {0};
    int path_count = 0, printed = 0, headings, explicit_operands;
    char **paths;
    int j;
    size_t i, count_dirs = 0;
    struct stat st;

    paths = calloc((size_t)argc + 1, sizeof(*paths));
    if (!paths) goto allocation_error;
    if (parse_options(argc, argv, &opts, paths, &path_count) < 0)
    {
        free(paths);
        return 2;
    }
    explicit_operands = path_count > 0;
    if (!explicit_operands && entry_add(&operands, ".", ".") < 0)
    {
        free(paths);
        goto allocation_error;
    }
    for (j = 0; j < path_count; ++j)
    {
        if (entry_add(&operands, paths[j], paths[j]) < 0)
        {
            free(paths);
            goto allocation_error;
        }
    }
    free(paths);
    /* Resolve explicit directory symlinks before sorting them. GNU ls treats
     * them as directories without -l, and as symlinks with -l. */
    for (i = 0; i < operands.len; ++i)
    {
        t_entry *e = &operands.items[i];

        if (!e->stat_ok || !S_ISLNK(e->st.st_mode) || opts.long_listing)
            continue;

        if (stat(e->path, &st) == 0)
        {
            if (S_ISDIR(st.st_mode))
                e->st = st;
        }
        else if (errno == ELOOP)
        {
            report_error(e->path);
            e->stat_ok = 0;
            g_errors = 1;
        }
    }
    /* One ordering for all operands; print files first without disturbing
     * the relative sort order of the remaining directory operands. */
    sort_entries(&operands, &opts);
    for (i = 0; i < operands.len; ++i)
    {
        t_entry *e = &operands.items[i];
        if (!e->stat_ok) { g_errors = 1; continue; }
        if (S_ISDIR(e->st.st_mode)) ++count_dirs;
        else
        {
            if (entry_add(&files, e->name, e->path) < 0)
                goto allocation_error;
            if (!files.items[files.len - 1].stat_ok) g_errors = 1;
        }
    }
    /* File operands retain their sorted order after filtering directories. */
    if (files.len)
    {
        if (print_entries(&files, &opts, 0) < 0) g_errors = 1;
        printed = 1;
    }
    headings = explicit_operands && (count_dirs > 1 || files.len > 0 || g_errors);
    for (i = 0; i < operands.len; ++i)
    {
        if (operands.items[i].stat_ok && S_ISDIR(operands.items[i].st.st_mode))
            list_directory(operands.items[i].path, &opts,
                headings || opts.recursive, &printed);
    }
    vector_free(&files);
    vector_free(&operands);
    if (fflush(stdout) == EOF) g_errors = 1;
    return g_errors ? 2 : 0;
allocation_error:
    fprintf(stderr, "ft_ls: memory allocation failed\n");
    vector_free(&files);
    vector_free(&operands);
    return 2;
}
