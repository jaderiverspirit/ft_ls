#include "ft_ls.h"
#include <stdio.h>
#include <string.h>

int parse_options(int argc, char **argv, t_options *opts, int *first)
{
	int i;
	size_t j;

	memset(opts, 0, sizeof(*opts));
	i = 1;
	while (i < argc && argv[i][0] == '-' && argv[i][1] != '\0')
	{
		if (strcmp(argv[i], "--") == 0)
		{
			++i;
			break;
		}
		j = 1;
		while (argv[i][j] != '\0')
		{
			if (argv[i][j] == 'l') opts->long_listing = 1;
			else if (argv[i][j] == 'R') opts->recursive = 1;
			else if (argv[i][j] == 'a') opts->all = 1;
			else if (argv[i][j] == 'r') opts->reverse = 1;
			else if (argv[i][j] == 't') opts->time_sort = 1;
			else
			{
				fprintf(stderr, "ft_ls: invalid option -- '%c'\n", argv[i][j]);
				fprintf(stderr, "Try 'ls --help' for supported ls options.\n");
				return -1;
			}
			++j;
		}
		++i;
	}
	*first = i;
	return 0;
}
