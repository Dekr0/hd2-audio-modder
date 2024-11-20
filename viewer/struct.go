package main

import "encoding/json"

const MAGIC = 4026531857

type ToCFile struct {
    Magic uint32 `json:"Magic"`
    NumTypes uint32 `json:"NumTypes"`
    NumFiles uint32 `json:"NumFiles"`
    Unknown uint32 `json:"Unknown"`
    Unk4Data [56]byte `json:"Unk4Data"`
    ToCEntries map[uint64]*ToCHeader `json:"ToCEntries,omitEmpty"`
}

type ToCHeader struct {
    FileID uint64 `json:"FileID"`
    TypeID uint64 `json:"TypeID"`
    ToCDataOffset uint64 `json:"ToCDataOffset"`
    StreamFileOffset uint64 `json:"StreamFileOffset"`
    GPUResourceOffset uint64 `json:"GPUResourceOffset"`
    Unknown1 uint64 `json:"Unknown1"`
    Unknown2 uint64 `json:"Unknown2"`
    ToCDataSize uint32 `json:"ToCDataSize"`
    StreamSize uint32 `json:"StreamSize"`
    GPUResourceSize uint32 `json:"GPUResourceSize"`
    Unknown3 uint32 `json:"Unknown3"`
    Unknown4 uint32 `json:"Unknown4"`
    EntryIndex uint32 `json:"EntryIndex"`
}

func (t *ToCFile) toJSON() (string, error) {
    b, err := json.Marshal(t)
    if err != nil {
        return "", err
    }
    return string(b), nil
}
