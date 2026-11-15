#ifndef FT_LS_H
# define FT_LS_H

# include <sys/types.h>
# include <sys/stat.h>
# include <stddef.h>

typedef struct s_options
{
	int long_listing;
	int recursive;
	int all;
	int reverse;
	int time_sort;
}   t_options;

typedef struct s_entry
{
	char		*name;
	char		*path;
	struct stat st;
	int		 stat_ok;
}   t_entry;

typedef struct s_vector
{
	t_entry *items;
	size_t  len;
	size_t  cap;
}   t_vector;

int parse_options(int argc, char **argv, t_options *opts, char **paths, int *path_count);
int	 entry_add(t_vector *v, const char *name, const char *path);
void	vector_free(t_vector *v);
char	*join_path(const char *dir, const char *name);
void	sort_entries(t_vector *v, const t_options *opts);
int print_entries(const t_vector *v, const t_options *opts, int total);
int	 list_directory(const char *path, const t_options *opts,
			int heading, int *printed);
void	report_error(const char *path);
void    report_directory_error(const char *path);

#endif
