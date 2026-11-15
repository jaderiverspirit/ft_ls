#include "ft_ls.h"
#include <stdlib.h>
#include <string.h>

static const t_options *g_sort_opts;

static int compare_entries(const void *aa, const void *bb)
{
	const t_entry *a = aa;
	const t_entry *b = bb;
	int c = 0;

	if (g_sort_opts->time_sort && a->stat_ok && b->stat_ok)
	{
		if (a->st.st_mtim.tv_sec > b->st.st_mtim.tv_sec) c = -1;
		else if (a->st.st_mtim.tv_sec < b->st.st_mtim.tv_sec) c = 1;
		else if (a->st.st_mtim.tv_nsec > b->st.st_mtim.tv_nsec) c = -1;
		else if (a->st.st_mtim.tv_nsec < b->st.st_mtim.tv_nsec) c = 1;
	}
	if (!c) c = strcmp(a->name, b->name);
	return g_sort_opts->reverse ? -c : c;
}

void sort_entries(t_vector *v, const t_options *opts)
{
	g_sort_opts = opts;
	qsort(v->items, v->len, sizeof(*v->items), compare_entries);
}
