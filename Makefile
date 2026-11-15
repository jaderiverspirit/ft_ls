NAME = ft_ls
CC = cc
CFLAGS = -Wall -Wextra -Werror -std=c11 -D_DEFAULT_SOURCE
SOURCES = src/main.c src/options.c src/entries.c src/sort.c src/display.c
OBJECTS = $(SOURCES:.c=.o)

all: $(NAME)

$(NAME): $(OBJECTS)
	$(CC) $(CFLAGS) $(OBJECTS) -o $(NAME)

src/%.o: src/%.c src/ft_ls.h
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS)

fclean: clean
	rm -f $(NAME)

re: fclean all

.PHONY: all clean fclean re
