# distutils: sources = c/structio.c
# distutils: include_dirs = c/

cimport cstructio 

from libc.stdint cimport uint8_t, int8_t, uint16_t, int16_t, uint32_t, int32_t, int64_t, uint64_t
from libc.stdlib cimport free

from cstructio cimport ArrayResizeFactor, MemoryStreamMode, MemoryStreamErrorCode


cdef class MemoryStream:
    
    cdef cstructio.MemoryStream *_memory_stream

    def __cinit__(self, char *data):
        cdef MemoryStreamErrorCode err = cstructio.NewMemoryStreamPreAllocate(
                MemoryStreamMode.MS_MODE_READ,
                ArrayResizeFactor.ARRAY_RESIZE_FACTOR_2,
                <uint8_t *>data,
                len(data),
                &self._memory_stream
                )

        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

    def append(self, bytes b):
        cdef MemoryStreamErrorCode err = cstructio.Append(
                self._memory_stream,
                len(b),
                <uint8_t *>b
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

    def write(self, bytes b):
        cdef MemoryStreamErrorCode err = cstructio.Overwrite(
                self._memory_stream,
                len(b),
                <uint8_t *>b
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

    def read(self, size_t n) -> bytearray:
        cdef uint8_t *dest = NULL
        cdef MemoryStreamErrorCode err = cstructio.Read(
                self._memory_stream,
                n,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        result = bytearray(dest[:n])

        free(dest)

        return result

    def read_uint8(self):
        cdef uint8_t dest = 0
        cdef MemoryStreamErrorCode err = cstructio.ReadUint8(
                self._memory_stream,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        return dest

    def read_int8(self):
        cdef int8_t dest = 0
        cdef MemoryStreamErrorCode err = cstructio.ReadInt8(
                self._memory_stream,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        return dest

    def read_uint16(self):
        cdef uint16_t dest = 0
        cdef MemoryStreamErrorCode err = cstructio.ReadUint16(
                self._memory_stream,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        return dest

    def read_int16(self):
        cdef int16_t dest = 0
        cdef MemoryStreamErrorCode err = cstructio.ReadInt16(
                self._memory_stream,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        return dest

    def read_uint32(self):
        cdef uint32_t dest = 0
        cdef MemoryStreamErrorCode err = cstructio.ReadUint32(
                self._memory_stream,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        return dest

    def read_int32(self):
        cdef int32_t dest = 0
        cdef MemoryStreamErrorCode err = cstructio.ReadInt32(
                self._memory_stream,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        return dest

    def read_uint64(self):
        cdef uint64_t dest = 0
        cdef MemoryStreamErrorCode err = cstructio.ReadUint64(
                self._memory_stream,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        return dest

    def read_int64(self):
        cdef int64_t dest = 0
        cdef MemoryStreamErrorCode err = cstructio.ReadInt64(
                self._memory_stream,
                &dest
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

        return dest

    def seek(self, size_t location):
        cdef MemoryStreamErrorCode err = cstructio.Seek(
                self._memory_stream, 
                location
                )
        if err != MemoryStreamErrorCode.MS_OK:
            raise RuntimeError(f"Error code {err}")

    def get_mode(self):
        return cstructio.GetMode(self._memory_stream)

    def is_read(self):
        return <bint>cstructio.IsRead(self._memory_stream)

    def is_write(self):
        return <bint>cstructio.IsWrite(self._memory_stream)

    def cap(self):
        return cstructio.Cap(self._memory_stream)

    def len(self):
        return cstructio.Len(self._memory_stream)

    def tell(self):
        return cstructio.Tell(self._memory_stream)

    def __dealloc__(self):
        if self._memory_stream != NULL:
            cstructio.FreeMemoryStream(self._memory_stream)
