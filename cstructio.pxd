from libc.stdint cimport uint8_t, int8_t, uint16_t, int16_t, uint32_t, int32_t, int64_t, uint64_t

cdef extern from "c/structio.h":

    cdef struct MemoryStream:
        pass

    ctypedef enum ArrayResizeFactor:
        ARRAY_RESIZE_FACTOR_1 = 0,
        ARRAY_RESIZE_FACTOR_2 = 1,
        ARRAY_RESIZE_FACTOR_3 = 2,
        ARRAY_RESIZE_FACTOR_4 = 3,
        ARRAY_RESIZE_FACTOR_5 = 4

    ctypedef enum MemoryStreamErrorCode:
        MS_OK,
        MS_CALLOC_ERROR,
        MS_REALLOC_ERROR,
        MS_NULL_STRUCT_ERROR,
        MS_NULL_DATA_ERROR,
        MS_MAX_CAP_ERROR,
        MS_SEEK_OUT_OF_BOUND_ERROR,
        MS_READ_OUT_OF_BOUND_ERROR,
        MS_NEGATIVE_SEEK_ERROR

    ctypedef enum MemoryStreamMode:
        MS_MODE_READ = 114,
        MS_MODE_WRITE = 119 

    MemoryStreamErrorCode Append(MemoryStream *m, size_t n, const uint8_t *src)
    
    MemoryStreamErrorCode NewMemoryStream(
            MemoryStreamMode mode,
            ArrayResizeFactor K, 
            uint8_t *data, 
            size_t len,
            MemoryStream **dest
            )

    MemoryStreamErrorCode NewMemoryStreamPreAllocate(
            MemoryStreamMode mode,
            ArrayResizeFactor K,
            uint8_t *data,
            size_t len,
            MemoryStream **dest
            )
    
    MemoryStreamErrorCode Overwrite(MemoryStream *m, size_t n, const uint8_t *src)
    
    MemoryStreamErrorCode Read(MemoryStream *m, size_t n, uint8_t **dest)
    
    MemoryStreamErrorCode ReadUint8(MemoryStream *m, uint8_t *dest)
    
    MemoryStreamErrorCode ReadInt8(MemoryStream *m, int8_t *dest)
    
    MemoryStreamErrorCode ReadUint16(MemoryStream *m, uint16_t *dest)
    
    MemoryStreamErrorCode ReadInt16(MemoryStream *m, int16_t *dest)
    
    MemoryStreamErrorCode ReadUint32(MemoryStream *m, uint32_t *dest)
    
    MemoryStreamErrorCode ReadInt32(MemoryStream *m, int32_t *dest)
    
    MemoryStreamErrorCode ReadUint64(MemoryStream *m, uint64_t *dest)
    
    MemoryStreamErrorCode ReadInt64(MemoryStream *m, int64_t *dest)
    
    MemoryStreamErrorCode Seek(MemoryStream *m, size_t location)
    
    MemoryStreamMode GetMode(const MemoryStream *m)
    
    size_t Cap(const MemoryStream *m)
    
    size_t Len(const MemoryStream *m)
    
    size_t Tell(const MemoryStream *m)
    
    uint8_t IsRead(const MemoryStream *m)
    
    uint8_t IsWrite(const MemoryStream *m)
    
    void FreeMemoryStream(MemoryStream *m)
    
    void SetReadMode(MemoryStream *m)
    
    void SetWriteMode(MemoryStream *m)
