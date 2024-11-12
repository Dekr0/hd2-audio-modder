#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "structio.h"


/** By ECE Department in University of Waterloo */
uint32_t const CAP_ARRAY[ARRAY_RESIZE_FACTOR_5 + 1][CAP_INDEX_MAX] =
{
	//                          _  k
	// The closest integer to \/2 2  for non-powers-of-two (every second).
	//   - 2.4 copies per insertion
	//   - 18% empty on average
	{
		4, 6,  // Initial capacity is 8; these are used for downsizing
		8, 11, 16, 23, 32, 45, 64, 91, 128, 181, 256, 362, 512, 724,
		1024, 1448, 2048, 2896, 4096, 5793, 8192, 11585, 16384, 23170,
		32768, 46341, 65536, 92682, 131072, 185364, 262144, 370728,
		524288, 741455, 1048576, 1482910, 2097152, 2965821, 4194304,
		5931642, 8388608, 11863283, 16777216, 23726566, 33554432,
		47453133, 67108864, 94906266, 134217728, 189812531, 268435456,
		379625062, 536870912, 759250125, 1073741824, 1518500250
	},

	// Using a factor of 1.5
	//   - 2 copies per insertion
	//   - 22% empty on average
	{
		3, 5,  // Initial capacity is 8; these are used for downsizing
		8, 12, 18, 27, 41, 62, 93, 140, 210, 315, 473, 710, 1065, 1598, 2397,
		3596, 5394, 8091, 12137, 18206, 27309, 40964, 61446, 92169, 138254,
		207381, 311072, 466608, 699912, 1049868, 1574802, 2362203, 3543305,
		5314958, 7972437, 11958656, 17937984, 26906976, 40360464, 60540696,
		90811044, 136216566, 204324849, 306487274, 459730911, 689596367,
		1034394551, 1551591827, 2327387741, 3491081612
	},

	//                         3_   2k + 1        3_  2k + 1
	// The closest integer to \/4  2       and 2 \/2 2       for non-odd-powers-of-two (every third).
	//   - 1.7 copies per insertion
	//   - 25% empty on average
	{
		5, 6,  // Initial capacity is 8; these are used for downsizing
		8, 13, 20, 32, 51, 81, 128, 203, 323, 512, 813, 1290, 2048,
		3251, 5161, 8192, 13004, 20643, 32768, 52016, 82570, 131072,
		208064, 330281, 524288, 832255, 1321123, 2097152, 3329021,
		5284492, 8388608, 13316085, 21137968, 33554432, 53264341,
		84551870, 134217728, 213057363, 338207482, 536870912,
		852229450, 1352829926
	},

	// Using a factor of 2
	//   - 1 copy per insertion
	//   - 39% empty on average
	{
		2, 4,  // Initial capacity is 8; these are used for downsizing
		8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768,
		65536, 131072, 262144, 524288, 1048576, 2097152, 4194304, 8388608,
		16777216, 33554432, 67108864, 134217728, 268435456, 536870912,
		1073741824
	},

	// Using a factor of infinity
	//    - 0 copies per insertion
	{
		0, 0,  // These two ensures that resizing never occurs
		1073741824
	}
};
/** End */


struct MemoryStream
{
    enum MemoryStreamMode  mode;
    enum ArrayResizeFactor K;
    size_t                 location; 
    size_t                 len;
    uint8_t                capIdx;
    size_t                 cap;
    uint8_t                *data;
};

static enum MemoryStreamErrorCode 
expandMemoryStream(struct MemoryStream *m, size_t newCap)
{
    assert(m != NULL);
    assert(m->data != NULL);
    assert(m->K >= ARRAY_RESIZE_FACTOR_1 && m->K <= ARRAY_RESIZE_FACTOR_4);
    assert(newCap > m->cap);

    if (m->K == ARRAY_RESIZE_FACTOR_5)
    {
        return MS_MAX_CAP_ERROR;
    }

    uint8_t testCapIdx = m->capIdx + 1;
    for (                                                                  ;
          testCapIdx < CAP_INDEX_MAX && CAP_ARRAY[m->K][testCapIdx] > 0;
          testCapIdx++)
    {
        assert(CAP_ARRAY[m->K][testCapIdx] >= m->cap);
        if (CAP_ARRAY[m->K][testCapIdx] > newCap)
        {
            break;
        }
    }

    if (testCapIdx == CAP_INDEX_MAX || CAP_ARRAY[m->K][testCapIdx] <= 0)
    {
        return MS_MAX_CAP_ERROR;
    }

    uint8_t *new = realloc(
            m->data, 
            CAP_ARRAY[m->K][testCapIdx] * sizeof(uint8_t)
            );
    if (new == NULL)
    {
        return MS_REALLOC_ERROR;
    }

    m->data = new;
    m->capIdx = testCapIdx;
    m->cap = CAP_ARRAY[m->K][m->capIdx];

    return MS_OK;
}

enum MemoryStreamErrorCode
Append(struct MemoryStream *m, size_t n, const uint8_t *src)
{
    assert(m != NULL);
    assert(src != NULL);

    if (m->len + n > m->cap)
    {
        enum MemoryStreamErrorCode code = expandMemoryStream(m, m->len + n);
        if (code != MS_OK)
        {
            return code;
        }
    }

    memcpy(m->data + m->len, src, n);

    m->len += n;

    assert(m->len <= m->cap);

    return MS_OK;
}

enum MemoryStreamErrorCode
Insert(struct MemoryStream *m, size_t n, uint8_t *src)
{
    assert(m != NULL);
    assert(src != NULL);

    if (m->location == m->len)
    {
        return Append(m, n, src);
    }

    if (m->len + n > m->cap)
    {
        enum MemoryStreamErrorCode code = expandMemoryStream(m, m->len + n);
        if (code != MS_OK)
        {
            return code;
        }
    }

    size_t cpyLength = m->len - m->location;
    uint8_t *tmp = calloc(cpyLength, sizeof(uint8_t));
    if (tmp == NULL)
    {
        return MS_REALLOC_ERROR;
    }

    memcpy(tmp, m->data + m->location, cpyLength);
    memcpy(m->data + m->location, src, n);
    memcpy(m->data + m->location + n, tmp, cpyLength);
    
    m->len += n;

    free(tmp);
    
    return MS_OK;
}

/** Using the memory already allocated in Python */
enum MemoryStreamErrorCode
NewMemoryStreamPreAllocate(
        enum MemoryStreamMode mode,
        enum ArrayResizeFactor K,
        uint8_t *data,
        size_t len,
        struct MemoryStream **dest
        )
{
    assert(mode == MS_MODE_READ || mode == MS_MODE_WRITE);
    assert(mode == MS_MODE_READ || mode == MS_MODE_WRITE);
    assert(K >= ARRAY_RESIZE_FACTOR_1 && K <= ARRAY_RESIZE_FACTOR_5);
    assert(data != NULL);
    assert(len >= 0);
    assert(dest != NULL);

    *dest = calloc(1, sizeof(struct MemoryStream));
    if (*dest == NULL)
    {
        return MS_CALLOC_ERROR;
    }

    struct MemoryStream *m = *dest;

    m->mode = mode;
    m->K = K;
    
    if (K == ARRAY_RESIZE_FACTOR_5)
    {
        if (len > CAP_ARRAY[K][DEFAULT_CAP_INDEX])
        {
            return MS_MAX_CAP_ERROR;
        }

        m->K = K;
        m->len = len;

        m->capIdx = DEFAULT_CAP_INDEX;

        assert(m->capIdx >= 0 && m->capIdx < CAP_INDEX_MAX);

        if (CAP_ARRAY[m->K][m->capIdx] == len)
        {
            return MS_OK;
        }

        m->cap = CAP_ARRAY[m->K][m->capIdx];

        if ((m->data = realloc(data, m->cap * sizeof(uint8_t))) == NULL)
        {
            FreeMemoryStream(m);

            return MS_CALLOC_ERROR;
        }

        m->len = len;
        m->mode = mode;

        return MS_OK;
    }

    for (
            size_t capIdx = DEFAULT_CAP_INDEX; 
            capIdx < CAP_INDEX_MAX && CAP_ARRAY[K][capIdx] > 0;
            capIdx++
            ) 
    {
        if (CAP_ARRAY[K][capIdx] > len)
        {
            m->K = K;
            m->len = len;

            m->capIdx = capIdx;

            /** Sanity check */
            assert(m->capIdx >= 0 && m->capIdx < CAP_INDEX_MAX);

            m->cap = CAP_ARRAY[m->K][m->capIdx];

            if ((m->data = realloc(data, m->cap * sizeof(uint8_t))) == NULL)
            {
                FreeMemoryStream(m);

                return MS_CALLOC_ERROR;
            }
            
            m->len = len;

            return MS_OK;
        }
        continue;
    }

    return MS_MAX_CAP_ERROR;
}

/** This version will cause memory duplication */
enum MemoryStreamErrorCode
NewMemoryStream(
        enum MemoryStreamMode mode,
        enum ArrayResizeFactor K, 
        uint8_t *data, 
        size_t len,
        struct MemoryStream **dest
        )
{
    assert(mode == MS_MODE_READ || mode == MS_MODE_WRITE);
    assert(K >= ARRAY_RESIZE_FACTOR_1 && K <= ARRAY_RESIZE_FACTOR_5);
    assert(data != NULL);
    assert(len >= 0);
    assert(dest != NULL);

    *dest = calloc(1, sizeof(struct MemoryStream));
    if (*dest == NULL)
    {
        return MS_CALLOC_ERROR;
    }

    struct MemoryStream *m = *dest;

    m->mode = mode;
    m->K = K;

    /** Never re-size */
    if (K == ARRAY_RESIZE_FACTOR_5)
    {
        if (len > CAP_ARRAY[K][DEFAULT_CAP_INDEX])
        {
            return MS_MAX_CAP_ERROR;
        }

        m->K = K;
        m->len = len;

        m->capIdx = DEFAULT_CAP_INDEX;

        assert(m->capIdx >= 0 && m->capIdx < CAP_INDEX_MAX);

        m->cap = CAP_ARRAY[m->K][m->capIdx];

        if ((m->data = calloc(m->cap, sizeof(uint8_t))) == NULL)
        {
            FreeMemoryStream(m);

            return MS_CALLOC_ERROR;
        }

        memcpy(m->data, data, len);

        m->len = len;
        m->mode = 'r';

        return MS_OK;
    }

    for (
            size_t capIdx = DEFAULT_CAP_INDEX; 
            capIdx < CAP_INDEX_MAX && CAP_ARRAY[K][capIdx] > 0;
            capIdx++
            ) 
    {
        if (CAP_ARRAY[K][capIdx] > len)
        {
            m->K = K;
            m->len = len;

            m->capIdx = capIdx;

            /** Sanity check */
            assert(m->capIdx >= 0 && m->capIdx < CAP_INDEX_MAX);

            m->cap = CAP_ARRAY[m->K][m->capIdx];

            if ((m->data = calloc(m->cap, sizeof(uint8_t))) == NULL)
            {
                FreeMemoryStream(m);

                return MS_CALLOC_ERROR;
            }

            memcpy(m->data, data, len);
            
            m->len = len;

            return MS_OK;
        }
        continue;
    }

    return MS_MAX_CAP_ERROR;
}

enum MemoryStreamErrorCode
Overwrite(struct MemoryStream *m, size_t n, const uint8_t *src)
{
    assert(m != NULL);
    assert(src != NULL);

    if (m->location + n > m->cap)
    {
        enum MemoryStreamErrorCode code = expandMemoryStream(m, m->len + n);
        if (code != MS_OK)
        {
            return code;
        }
    }

    memcpy(m->data + m->location, src, n);

    m->location += n;

    if (m->location > m->len)
    {
        m->len = m->location;
    }

    return MS_OK;
}


enum MemoryStreamErrorCode
Read(struct MemoryStream *m, size_t n, uint8_t **dest)
{
    assert(m != NULL);
    assert(m->data != NULL);
    assert(n >= 0);

    if (m->location + n > m->len)
    {
        return MS_READ_OUT_OF_BOUND_ERROR;
    }

    *dest = calloc(n, sizeof(uint8_t));
    if (*dest == NULL)
    {
        return MS_CALLOC_ERROR;
    }

    memcpy(*dest, m->data + m->location, n);

    m->location += n;

    return MS_OK;
}

enum MemoryStreamErrorCode
ReadUint8(struct MemoryStream *m, uint8_t *dest)
{
   assert(m != NULL);
   assert(m->data != NULL);
   assert(dest != NULL);

   if (m->location + 1 > m->len)
   {
       return MS_READ_OUT_OF_BOUND_ERROR;
   }

   *dest = m->data[m->location++];

   return MS_OK;
}

enum MemoryStreamErrorCode
ReadInt8(struct MemoryStream *m, int8_t *dest)
{
   assert(m != NULL);
   assert(m->data != NULL);
   assert(dest != NULL);

   if (m->location + 1 > m->len)
   {
       return MS_READ_OUT_OF_BOUND_ERROR;
   }

   *dest = m->data[m->location++];

   return MS_OK;
}

enum MemoryStreamErrorCode
ReadUint16(struct MemoryStream *m, uint16_t *dest)
{
    assert(m != NULL);
    assert(m->data != NULL);
    assert(dest != NULL);

    if (m->location + 2 > m->len)
    {
        return MS_READ_OUT_OF_BOUND_ERROR;
    }

    *dest = m->data[m->location];
    *dest |= ((uint16_t) m->data[m->location + 1]) << 8;

    m->location += 2;

    return MS_OK;
}

enum MemoryStreamErrorCode
ReadInt16(struct MemoryStream *m, int16_t *dest)
{
    assert(m != NULL);
    assert(m->data != NULL);
    assert(dest != NULL);

    if (m->location + 2 > m->len)
    {
        return MS_READ_OUT_OF_BOUND_ERROR;
    }

    *dest = m->data[m->location];
    *dest |= ((int16_t) m->data[m->location + 1]) << 8;

    m->location += 2;

    return MS_OK;
}

enum MemoryStreamErrorCode
ReadUint32(struct MemoryStream *m, uint32_t *dest)
{
    assert(m != NULL);
    assert(m->data != NULL);
    assert(dest != NULL);

    if (m->location + 4 > m->len)
    {
        return MS_READ_OUT_OF_BOUND_ERROR;
    }

    *dest = m->data[m->location];
    *dest |= ((uint32_t) m->data[m->location + 1]) << 8;
    *dest |= ((uint32_t) m->data[m->location + 2]) << 16;
    *dest |= ((uint32_t) m->data[m->location + 3]) << 24;

    m->location += 4;

    return MS_OK;
}

enum MemoryStreamErrorCode
ReadInt32(struct MemoryStream *m, int32_t *dest)
{
    assert(m != NULL);
    assert(m->data != NULL);
    assert(dest != NULL);

    if (m->location + 4 > m->len)
    {
        return MS_READ_OUT_OF_BOUND_ERROR;
    }

    *dest = m->data[m->location];
    *dest |= ((int32_t) m->data[m->location + 1]) << 8;
    *dest |= ((int32_t) m->data[m->location + 2]) << 16;
    *dest |= ((int32_t) m->data[m->location + 3]) << 24;

    m->location += 4;

    return MS_OK;
}

enum MemoryStreamErrorCode
ReadUint64(struct MemoryStream *m, uint64_t *dest)
{
    assert(m != NULL);
    assert(m->data != NULL);
    assert(dest != NULL);

    if (m->location + 8 > m->len)
    {
        return MS_READ_OUT_OF_BOUND_ERROR;
    }

    *dest = m->data[m->location];
    *dest |= ((uint64_t) m->data[m->location + 1]) << 8;
    *dest |= ((uint64_t) m->data[m->location + 2]) << 16;
    *dest |= ((uint64_t) m->data[m->location + 3]) << 24;
    *dest |= ((uint64_t) m->data[m->location + 4]) << 32;
    *dest |= ((uint64_t) m->data[m->location + 5]) << 40;
    *dest |= ((uint64_t) m->data[m->location + 6]) << 48;
    *dest |= ((uint64_t) m->data[m->location + 7]) << 56;

    m->location += 8;

    return MS_OK;
}

enum MemoryStreamErrorCode
ReadInt64(struct MemoryStream *m, int64_t *dest)
{
    assert(m != NULL);
    assert(m->data != NULL);
    assert(dest != NULL);

    if (m->location + 8 > m->len)
    {
        return MS_READ_OUT_OF_BOUND_ERROR;
    }

    *dest = m->data[m->location];
    *dest |= ((int64_t) m->data[m->location + 1]) << 8;
    *dest |= ((int64_t) m->data[m->location + 2]) << 16;
    *dest |= ((int64_t) m->data[m->location + 3]) << 24;
    *dest |= ((int64_t) m->data[m->location + 4]) << 32;
    *dest |= ((int64_t) m->data[m->location + 5]) << 40;
    *dest |= ((int64_t) m->data[m->location + 6]) << 48;
    *dest |= ((int64_t) m->data[m->location + 7]) << 56;

    m->location += 8;

    return MS_OK;
}

enum MemoryStreamErrorCode
Seek(struct MemoryStream *m, size_t location)
{
    assert(m != NULL);
    assert(location >= 0);

    if (location > m->len)
    {
        if (location == 0)
        {
            return MS_OK;
        }

        return MS_SEEK_OUT_OF_BOUND_ERROR;
    }

    m->location = location;

    return MS_OK;
}

enum MemoryStreamMode
GetMode(const struct MemoryStream *m)
{
    return m->mode;
}

size_t
Cap(const struct MemoryStream *m)
{
    assert(m != NULL);
    return m->cap;
}

size_t
Len(const struct MemoryStream *m)
{
    assert(m != NULL);
    return m->len;
}

size_t
Tell(const struct MemoryStream *m)
{
    assert(m != NULL);
    return m->location;
}

uint8_t
IsRead(const struct MemoryStream *m)
{
    assert(m != NULL);
    return m->mode == MS_MODE_READ;
}

uint8_t 
IsWrite(const struct MemoryStream *m)
{
    assert(m != NULL);
    return m->mode == MS_MODE_WRITE;
}

void 
FreeMemoryStream(struct MemoryStream *m)
{
    if (m == NULL)
    {
        return;
    }

    if (m->data != NULL)
    {
        free(m->data);
    }

    free(m);
}

void
SetReadMode(struct MemoryStream *m)
{
    assert(m != NULL);
    m->mode = MS_MODE_READ;
}

void
SetWriteMode(struct MemoryStream *m)
{
    assert(m != NULL);
    m->mode = MS_MODE_WRITE;
}
