package main

import (
	"errors"
	"log/slog"
	"os"
)

func parseToCHeader(r *StingRayAssetReader) (*ToCHeader, error) {
    var err error

    header := &ToCHeader{}

    header.FileID, err = r.ReadUint64()
    if err != nil {
        return nil, err
    }
    header.TypeID, err = r.ReadUint64()
    if err != nil {
        return nil, err
    }
    header.ToCDataOffset, err = r.ReadUint64()
    if err != nil {
        return nil, err
    }
    header.StreamFileOffset, err = r.ReadUint64()
    if err != nil {
        return nil, err
    }
    header.GPUResourceOffset, err = r.ReadUint64()
    if err != nil {
        return nil, err
    }
    header.Unknown1, err = r.ReadUint64()
    if err != nil {
        return nil, err
    }
    header.Unknown2, err = r.ReadUint64()
    if err != nil {
        return nil, err
    }
    header.ToCDataSize, err = r.ReadUint32()
    if err != nil {
        return nil, err
    }
    header.StreamSize, err = r.ReadUint32()
    if err != nil {
        return nil, err
    }
    header.GPUResourceSize, err = r.ReadUint32()
    if err != nil {
        return nil, err
    }
    header.Unknown3, err = r.ReadUint32()
    if err != nil {
        return nil, err
    }
    header.Unknown4, err = r.ReadUint32()
    if err != nil {
        return nil, err
    }
    header.EntryIndex, err = r.ReadUint32()
    if err != nil {
        return nil, err
    }

    return header, nil
}

func ParseToC(f *os.File, logger *slog.Logger) (*ToCFile, error) {
    ToC := ToCFile{}

    reader := &StingRayAssetReader{ File: f }

    var err error = nil

    ToC.Magic, err = reader.ReadUint32()
    if err != nil {
        return nil, err
    }
    if ToC.Magic != MAGIC {
        return nil, errors.New("ToC file does not start with MAGIC number")
    }

    ToC.NumTypes, err = reader.ReadUint32()
    if err != nil {
        return nil, err
    }

    ToC.NumFiles, err = reader.ReadUint32()
    if err != nil {
        return nil, err
    }

    ToC.Unknown, err = reader.ReadUint32()
    if err != nil {
        return nil, err
    }

    err = reader.Read(ToC.Unk4Data[:])
    if err != nil {
        return nil, err
    }

    err = reader.RelativeSeek(int64(32 + ToC.NumTypes))
    ToCStart := reader.Head

    ToC.ToCEntries = make(map[uint64]*ToCHeader)

    for i := 0; i < int(ToC.NumFiles); i++ {
        if err = reader.AbsoluteSeek(ToCStart + int64(i) * 80); err != nil {
            return nil, err
        }
        header, err := parseToCHeader(reader)
        if err != nil {
            return nil, err
        }
        logger.Info("ToC Header File ID", "FileID", header.FileID)
        if _, in := ToC.ToCEntries[header.FileID]; in {
            logger.Warn("Duplicated ToC header File ID", "FileID", header.FileID)
            logger.Warn("Parsing context", 
                "File Position", i, 
                "Total File", ToC.NumFiles,
            )
            return nil, errors.New("ToC parsing error! ToC header with duplicate File ID")
        }
        ToC.ToCEntries[header.FileID] = header
    }
    return &ToC, err 
}
