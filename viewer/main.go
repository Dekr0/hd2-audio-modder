package main

import (
	"flag"
	"log/slog"
	"os"
)

func main() {
    handler := slog.NewJSONHandler(
        os.Stdout,
        &slog.HandlerOptions{
            AddSource: true,
            Level: slog.LevelDebug.Level(),
        },
    )
    
    logger := getLogger()(handler)

    gameArchiveID := flag.String(
        "game-archive-id",
        "",
        "Extract all information in Wwise Soundbank",
    )

    flag.Parse()

    if gameArchiveID == nil {
        logger.Error("Variable is nil")
        os.Exit(1)
    }

    _, err := os.Stat(*gameArchiveID); 
    if err != nil {
        if os.IsNotExist(err) {
            logger.Error("Game archive ID " + *gameArchiveID + " does not exist") 
            os.Exit(1)
        } else {
            logger.Error("OS error", "error", err)
            os.Exit(1)
        }
    }
    if !os.IsExist(err) {
        logger.Error("Conflicting OS validation", "error", err)
        os.Exit(1)
    }

    f, err := os.Open(*gameArchiveID)
    if err != nil {
        logger.Error("File open error", "error", err)
        f.Close()
        os.Exit(1)
    }
    defer f.Close()

    _, err = ParseToC(f, logger)
    if err != nil {
        logger.Error("Failed to parse ToC File", "error", err)
        f.Close()
        os.Exit(1)
    }
}
