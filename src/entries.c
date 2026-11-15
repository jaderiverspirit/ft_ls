#include "ft_ls.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void report_error(const char *path)
{
    int saved = errno;
    fprintf(stderr, "ft_ls: cannot access '%s': %s\n", path, strerror(saved));
}

void report_directory_error(const char *path)
{
    int saved = errno;
    fprintf(stderr, "ft_ls: cannot open directory '%s': %s\n", path, strerror(saved));
}

char *join_path(const char *dir, const char *name)
{
    size_t a = strlen(dir);
    size_t b = strlen(name);
    int slash = a > 0 && dir[a - 1] != '/';
    char *out;


    if (a > (size_t)-1 - b - (size_t)slash - 1)
    {
        errno = ENOMEM;
        return NULL;
    }
    out = malloc(a + b + (size_t)slash + 1);
    if (!out) return NULL;
    memcpy(out, dir, a);
    if (slash) out[a++] = '/';
    memcpy(out + a, name, b + 1);
    return out;
}

int entry_add(t_vector *v, const char *name, const char *path)
{
    t_entry e;
    t_entry *bigger;
    size_t cap;

    memset(&e, 0, sizeof(e));
    e.name = strdup(name);
    e.path = strdup(path);
    if (!e.name || !e.path)
    {
        free(e.name);
        free(e.path);
        return -1;
    }
    if (lstat(e.path, &e.st) == 0) e.stat_ok = 1;
    else report_error(e.path);
    if (v->len == v->cap)
    {
        cap = v->cap ? v->cap * 2 : 32;
        if (cap < v->cap || cap > (size_t)-1 / sizeof(*bigger))
        {
            free(e.name);
            free(e.path);
            errno = ENOMEM;
            return -1;
        }
        bigger = realloc(v->items, cap * sizeof(*bigger));
        if (!bigger)
        {
            free(e.name);
            free(e.path);
            return -1;
        }
        v->items = bigger;
        v->cap = cap;
    }
    v->items[v->len++] = e;
    return 0;
}

void vector_free(t_vector *v)
{
    size_t i;

    for (i = 0; i < v->len; ++i)
    {
        free(v->items[i].name);
        free(v->items[i].path);
    }
    free(v->items);
    memset(v, 0, sizeof(*v));
}
