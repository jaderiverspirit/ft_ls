#include "ft_ls.h"
#include <sys/sysmacros.h>
#include <pwd.h>
#include <grp.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <inttypes.h>
#include <unistd.h>
	
static char type_char(mode_t m)
{
	if (S_ISDIR(m)) return 'd';
	if (S_ISLNK(m)) return 'l';
	if (S_ISCHR(m)) return 'c';
	if (S_ISBLK(m)) return 'b';
	if (S_ISFIFO(m)) return 'p';
	if (S_ISSOCK(m)) return 's';
	return '-';
}

static void permissions(mode_t m, char out[11])
{
	const mode_t bit[9] = {S_IRUSR, S_IWUSR, S_IXUSR,
		S_IRGRP, S_IWGRP, S_IXGRP, S_IROTH, S_IWOTH, S_IXOTH};
	int i;

	out[0] = type_char(m);
	for (i = 0; i < 9; ++i)
		out[i + 1] = (m & bit[i]) ? "rwx"[i % 3] : '-';
	if (m & S_ISUID) out[3] = (m & S_IXUSR) ? 's' : 'S';
	if (m & S_ISGID) out[6] = (m & S_IXGRP) ? 's' : 'S';
	if (m & S_ISVTX) out[9] = (m & S_IXOTH) ? 't' : 'T';
	out[10] = '\0';
}

static const char *user_name(uid_t id, char *fallback, size_t n)
{
	struct passwd *p = getpwuid(id);
	if (p && p->pw_name) return p->pw_name;
	snprintf(fallback, n, "%ju", (uintmax_t)id);
	return fallback;
}

static const char *group_name(gid_t id, char *fallback, size_t n)
{
	struct group *g = getgrgid(id);
	if (g && g->gr_name) return g->gr_name;
	snprintf(fallback, n, "%ju", (uintmax_t)id);
	return fallback;
}

static int count_digits(uintmax_t n)
{
	int i = 1;
	while (n >= 10) { n /= 10; ++i; }
	return i;
}

typedef struct s_widths
{
	int links;
	int user;
	int group;
	int size;
	int major;
	int minor;
	int has_device;
} t_widths;

static void update_widths(t_widths *w, const t_entry *e)
{
	char ubuf[32], gbuf[32];
	int n;
	const char *u = user_name(e->st.st_uid, ubuf, sizeof(ubuf));
	const char *g = group_name(e->st.st_gid, gbuf, sizeof(gbuf));

	n = count_digits((uintmax_t)e->st.st_nlink);
	if (n > w->links) w->links = n;
	n = (int)strlen(u);
	if (n > w->user) w->user = n;
	n = (int)strlen(g);
	if (n > w->group) w->group = n;
	if (S_ISCHR(e->st.st_mode) || S_ISBLK(e->st.st_mode))
	{
		w->has_device = 1;
		n = count_digits((uintmax_t)major(e->st.st_rdev));
		if (n > w->major) w->major = n;
		n = count_digits((uintmax_t)minor(e->st.st_rdev));
		if (n > w->minor) w->minor = n;
	}
	else
	{
		n = count_digits((uintmax_t)e->st.st_size);
		if (n > w->size) w->size = n;
	}
}

static void format_time(time_t modified, char buf[64])
{
	time_t now = time(NULL);
	struct tm tm;
	/* Match common ls convention: distant/future dates show the year. */
	int recent = modified <= now + 3600
		&& (double)modified >= (double)now - 31556952.0 / 2;

	if (!localtime_r(&modified, &tm))
	{
		strcpy(buf, "??? ?? ??:??");
		return;
	}
	strftime(buf, 64, recent ? "%b %e %H:%M" : "%b %e  %Y", &tm);
}

static void print_symlink_target(const t_entry *e)
{
	size_t cap = e->st.st_size > 0 ? (size_t)e->st.st_size + 2 : 128;
	char *buf;
	ssize_t size;

	while (cap && cap < (size_t)-1 / 2)
	{
		buf = malloc(cap);
		if (!buf) return;
		size = readlink(e->path, buf, cap - 1);
		if (size < 0) { free(buf); return; }
		if ((size_t)size < cap - 1)
		{
			buf[size] = '\0';
			printf(" -> %s", buf);
			free(buf);
			return;
		}
		free(buf);
		cap *= 2;
	}
}

static void print_long(const t_entry *e, const t_widths *w)
{
	char perm[11], timebuf[64], ubuf[32], gbuf[32];
	const char *u, *g;
	int sizewidth = w->size;

	if (!e->stat_ok) { printf("%s\n", e->name); return; }
	permissions(e->st.st_mode, perm);
	u = user_name(e->st.st_uid, ubuf, sizeof(ubuf));
	g = group_name(e->st.st_gid, gbuf, sizeof(gbuf));
	format_time(e->st.st_mtime, timebuf);
	if (w->has_device && w->major + w->minor + 2 > sizewidth)
		sizewidth = w->major + w->minor + 2;
	printf("%s %*ju %-*s %-*s ", perm, w->links,
		(uintmax_t)e->st.st_nlink, w->user, u, w->group, g);
	if (S_ISCHR(e->st.st_mode) || S_ISBLK(e->st.st_mode))
		printf("%*ju, %*ju", w->major, (uintmax_t)major(e->st.st_rdev),
			w->minor, (uintmax_t)minor(e->st.st_rdev));
	else
		printf("%*jd", sizewidth, (intmax_t)e->st.st_size);
	printf(" %s %s", timebuf, e->name);
	if (S_ISLNK(e->st.st_mode)) print_symlink_target(e);
	putchar('\n');
}

void print_entries(const t_vector *v, const t_options *opts, int total)
{
	size_t i;
	t_widths widths = {0};
	uintmax_t blocks = 0;

	if (opts->long_listing)
	{
		for (i = 0; i < v->len; ++i)
		{
			if (!v->items[i].stat_ok) continue;
			update_widths(&widths, &v->items[i]);
			blocks += (uintmax_t)v->items[i].st.st_blocks;
		}
		if (total) printf("total %ju\n", (blocks + 1) / 2);
	}
	for (i = 0; i < v->len; ++i)
	{
		if (opts->long_listing) print_long(&v->items[i], &widths);
		else printf("%s\n", v->items[i].name);
	}
}
