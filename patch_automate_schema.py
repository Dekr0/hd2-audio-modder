from referencing.jsonschema import Schema

VERSION = 0

task: Schema = {
    "$id": "https://github.com/RaidingForPants/hd2-audio-modder/schemas/patch/task",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "archive_files": {
            "description": "An array of archive files you want to perform patch "
                           "automation",
            "type": "array",
            "items": {
                "type": "string"  
            },
            "minItems": 1
        },
        "using": {
            "description": "An array of target import manifest files (relative "
                           "path or absolute path) you want to apply in the current "
                           "task. The order of which manifest files are layout "
                           "will be the order of how manifest files being applied",
            "type": "array",
            "items": {
                "type": "string"
            },
            "minItems": 1
        }
    },
    "required": [ "archive_files", "using" ]
}

manifest: Schema = {
    "$id": "https://github.com/RaidingForPants/hd2-audio-modder/schemas/patch/manifest",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "version": {
            "description": "Version of patch manifest",
            "const": VERSION,
        },
        "tasks": {
            "description": "An array of patch automation task you want to run",
            "type": "array",
            "items": task,
            "minItems": 1
        }
    },
    "required": [ "version", "tasks" ]
}
