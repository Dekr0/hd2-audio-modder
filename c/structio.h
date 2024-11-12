#ifndef __AUDIO_MODDER_STRUCTIO_H__
#define __AUDIO_MODDER_STRUCTIO_H__

#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>

#define CAP_INDEX_MAX 60
#define DEFAULT_CAP_INDEX 2

typedef enum MemoryStreamMode
{
    MS_MODE_READ = 'r',
    MS_MODE_WRITE = 'w'
} MemoryStreamMode;

typedef enum MemoryStreamErrorCode
{
    MS_OK,
    MS_CALLOC_ERROR,
    MS_REALLOC_ERROR,
    MS_NULL_STRUCT_ERROR,
    MS_NULL_DATA_ERROR,
    MS_MAX_CAP_ERROR,
    MS_SEEK_OUT_OF_BOUND_ERROR,
    MS_READ_OUT_OF_BOUND_ERROR,
    MS_NEGATIVE_SEEK_ERROR
} MemoryStreamErrorCode;

typedef enum ArrayResizeFactor
{
    ARRAY_RESIZE_FACTOR_1 = 0,
    ARRAY_RESIZE_FACTOR_2 = 1,
    ARRAY_RESIZE_FACTOR_3 = 2,
    ARRAY_RESIZE_FACTOR_4 = 3,
    ARRAY_RESIZE_FACTOR_5 = 4,
} ArrayResizeFactor;

struct MemoryStream;

static enum MemoryStreamErrorCode 
expandMemoryStream(struct MemoryStream *m, size_t newCap);

enum MemoryStreamErrorCode
Append(struct MemoryStream *m, size_t n, const uint8_t *src);

enum MemoryStreamErrorCode
NewMemoryStream(
        enum MemoryStreamMode mode,
        enum ArrayResizeFactor K, 
        uint8_t *data, 
        size_t len,
        struct MemoryStream **dest
        );

enum MemoryStreamErrorCode
NewMemoryStreamPreAllocate(
        enum MemoryStreamMode mode,
        enum ArrayResizeFactor K,
        uint8_t *data,
        size_t len,
        struct MemoryStream **dest
        );

enum MemoryStreamErrorCode
Insert(struct MemoryStream *m, size_t n, uint8_t *src);

/**
 * This is the original write function
 * */
enum MemoryStreamErrorCode
Overwrite(struct MemoryStream *m, size_t n, const uint8_t *src);

enum MemoryStreamErrorCode
Read(struct MemoryStream *m, size_t n, uint8_t **dest);

enum MemoryStreamErrorCode ReadUint8(struct MemoryStream *m, uint8_t *dest);

enum MemoryStreamErrorCode ReadInt8(struct MemoryStream *m, int8_t *dest);

enum MemoryStreamErrorCode ReadUint16(struct MemoryStream *m, uint16_t *dest);

enum MemoryStreamErrorCode ReadInt16(struct MemoryStream *m, int16_t *dest);

enum MemoryStreamErrorCode ReadUint32(struct MemoryStream *m, uint32_t *dest);

enum MemoryStreamErrorCode ReadInt32(struct MemoryStream *m, int32_t *dest);

enum MemoryStreamErrorCode ReadUint64(struct MemoryStream *m, uint64_t *dest);

enum MemoryStreamErrorCode ReadInt64(struct MemoryStream *m, int64_t *dest);

enum MemoryStreamErrorCode Seek(struct MemoryStream *m, size_t location);

enum MemoryStreamMode GetMode(const struct MemoryStream *m);

size_t Cap(const struct MemoryStream *m);

size_t Len(const struct MemoryStream *m);

size_t Tell(const struct MemoryStream *m);

uint8_t IsRead(const struct MemoryStream *m);

uint8_t IsWrite(const struct MemoryStream *m);

void FreeMemoryStream(struct MemoryStream *m);

void SetReadMode(struct MemoryStream *m);

void SetWriteMode(struct MemoryStream *m);

#endif
