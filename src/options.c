#include "ft_ls.h"
#include <stdio.h>
#include <string.h>

/* Store operands in their original order, including those before options.
 * A literal "--" ends option parsing. A lone "-" is an operand. */
int parse_options(int argc, char **argv, t_options *opts,
	char **paths, int *path_count)
{
	int i;
	size_t j;
	int end_options = 0;

	memset(opts, 0, sizeof(*opts));
	*path_count = 0;
	for (i = 1; i < argc; ++i)
	{
		if (!end_options && strcmp(argv[i], "--") == 0)
		{
			end_options = 1;
			continue;
		}
		if (!end_options && argv[i][0] == '-' && argv[i][1] != '\0')
		{
			for (j = 1; argv[i][j] != '\0'; ++j)
			{
				if (argv[i][j] == 'l') opts->long_listing = 1;
				else if (argv[i][j] == 'R') opts->recursive = 1;
				else if (argv[i][j] == 'a') opts->all = 1;
				else if (argv[i][j] == 'r') opts->reverse = 1;
				else if (argv[i][j] == 't') opts->time_sort = 1;
				else
				{
					fprintf(stderr, "ft_ls: invalid option -- '%c'\n", argv[i][j]);
					return -1;
				}
			}
		}
		else
			paths[(*path_count)++] = argv[i];
	}
	return 0;
}
