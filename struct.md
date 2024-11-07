- The following specification is usual case. There will be exception

## Game Archive

- Each game archive starts with the following structure **in sequence**:

```C
struct GameArchiveBasicHeader {
    uint32_t MagicNumber; /** 4026531857 */
    uint32_t NumTypes;
    uint32_t NumFiles;
} gameArchivebasicHeader;

uint8_t unknownData[60];

uint8_t skippedData[gameArchivebasicHeader.numTypes * 32];
```

## ToC Header

- Each archive file contains a table of contents (aka. ToC).
- A ToC is constructed by ToC headers.
- A ToC contains metadata about all game resources in that archive file.
- Each `ToCHeader` describes a single game resource.

```C
struct ToCHeader {
    uint64_t FileId; /** Or Resource Id */
    uint64_t TypeId;

    /** 
     * For locating data of a single game resource in the ToC file, the 
     * `.stream` file, and `.gpu_resource` file, respectively.
     * */
    uint64_t ToCDataOffset; /** Bytes offset @ 0x0 in ToC file */
    uint64_t StreamFileOffset; /** Bytes offset @ 0x0 in `.stream` file */
    uint64_t GPUResourceOffset; /** Bytes offset @ 0x0 in `.gpu_resource` file */

    uint64_t Unknown1;
    uint64_t Unknown2;

    /**
     * The size of data for a single game resource in the ToC file, the `.stream`
     *  file, and `.gpu_resource` file, respectively.
     * */
    uint32_t ToCDataSize;
    uint32_t StreamSize;
    uint32_t GPUResourceSize;

    uint32_t Unknown3;
    uint32_t Unknown4;

    uint32_t EntryIndex;
};

sizeof(struct ToCHeader); /** 80 bytes in total */
```

## Game Resource

- To locate one of the game resource in one of three types of files, it need to 
use the corresponding offset (starting @ 0x0) value provided in the `ToCHeader`.
    - data in ToC file <- `ToCDataOffset`
    - data in `.stream` file <- `StreamFileOffset`
    - data in `.gpu_resource` file <- `GPUResourceOffset`
- The size of data for a single game resource in one of three types of files is 
specified using the corresponding value provided in the `ToCHeader`.
    - data size in ToC file <- `ToCDataSize`
    - data size in `.stream` file <- `StreamSize`
    - data size in `.gpu_resource` file <- `GPUResourceSize`

### Wwise Stream

- The (All) data of each Wwise stream is located in the `.stream` file.
- Each Wwise stream is equivalent to a `.wem` file.
- Each Wwise stream is encapuslated by an abstraction layer called ***Audio 
Source***.
- Each Wwise stream has no other metadata attached.

- To locate a Wwise stream in `.stream` file, use `(struct ToCHeader).StreamFileOffset` 
(starting @ 0x0) to seek to the first byte associative to that Wwise stream.

- The data of size of a Wwise stream is specified by `(struct ToCHeader).StreamSize`.

#### Audio Source

- This is an abstraction layer that sits on top of the raw audio files.

### Wwise Soundbank

- A Wwise Soundbank has four sections.
    - The **bank header** section (BKHD)
    - The **data index** section (DIDX)
    - The **data** section (DATA)
    - The **Wwise Soundbank Hirearchy** section (HIRC)

- The structure of a Wwise Soundbank needs a separate article section to explain 
since it's fairly complex.

### Wwise Dependency

- A Wwise Dependency contains the human-friendly name of a given Wwise Soundbank.

- The (All) data of a Wwise Dependency is in the ToC file.

- There maybe something else?

### String Entry

- Not important for now

## Wwise Soundbank

- A Wwise project is typically compiled into one or **multiple** `.bnk` Wwise 
Soundbanks.

- All `.wav` files are converted to `.wem` files (stored inside banks, or 
streamed from a directory).

- A game must load `.bnk` and set a call to a ID associative an Wwise object, 
when something mus happen.

