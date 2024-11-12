#include <stdio.h>

#include "structio.h"

void testOverwrite()
{
    struct MemoryStream *m = NULL;

    uint8_t data[] = {',', '.', '|', 'm', 's', ')'};

    NewMemoryStream(MS_MODE_READ, ARRAY_RESIZE_FACTOR_2, data, 6, &m);

    uint8_t new_data[] = {'a', 'b', 'c', 'd', 'e', 'f', 'h', 'i', 'j', 'k', 'l'};

    Seek(m, 4);

    uint8_t *c = 0;

    Read(m, 1, &c);

    printf("%c\n", *c);

    printf("%zd\n", Tell(m));

    Seek(m, 4);

    Overwrite(m, 11, new_data);

    printf("%zd\n", Tell(m));
    printf("%zd\n", Len(m));
    
    Seek(m, 4);

    free(c);

    Read(m, 11, &c);
    printf("%s\n", c);

    printf("%zd\n", Tell(m));

    Seek(m, Tell(m) - 1);

    free(c);

    Read(m, 1, &c);

    printf("%c\n", *c);

    free(c);

    FreeMemoryStream(m);
}

void testInsert()
{
    struct MemoryStream *m = NULL;

    char data[] = "123";

    NewMemoryStream(MS_MODE_READ, ARRAY_RESIZE_FACTOR_2, (uint8_t *) data, 3, &m);

    Seek(m, 3);

    char new_data[] = "abc";

    Insert(m, 3, (uint8_t *) new_data);

    FreeMemoryStream(m);
}

int
main()
{
    testInsert();
}
