package main

import (
	"encoding/json"
	"log/slog"
	"os"
	"reflect"
	"testing"
)

var TestingToCs = []string{
    "2e24ba9dd702da5c",
    "68e80476c1c602f5",
}

func LoadExpectedToC() ([]ToCFile, error) { 
    ToCFiles := make([]ToCFile, len(TestingToCs))

    for i, t := range TestingToCs {
        b, err := os.ReadFile(t + "_ToC.json")
        if err != nil {
            return nil, err
        }
        err = json.Unmarshal(b, &ToCFiles[i])
        if err != nil {
            return nil, err
        }
    }

    return ToCFiles, nil
}

func TestParsingBasicHeader(t *testing.T) {
    ToCFiles, err := LoadExpectedToC()
    if err != nil {
        t.Fatal(err)
    }

    handler := slog.NewJSONHandler(
        os.Stdout,
        &slog.HandlerOptions{
            AddSource: true,
            Level: slog.LevelDebug.Level(),
        },
    )
    
    logger := getLogger()(handler)
    for i, testingToC := range TestingToCs {
        t.Log("Parsing " + testingToC)
        f, err := os.Open(testingToC)
        if err != nil {
           t.Fatal(err) 
        }
        ToCFile, err := ParseToC(f, logger)
        if err != nil {
            t.Log(ToCFiles[i])
            t.Fatal(err)
        }
        if !reflect.DeepEqual(*ToCFile, ToCFiles[i]) {
            t.Log(ToCFile)
            t.Log(ToCFiles[i])
            t.Fatal(err)
        }
    }
}
