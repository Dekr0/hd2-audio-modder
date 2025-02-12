from referencing.jsonschema import Schema

VERSION = 0

task: Schema = {
    "$id": "https://github.com/RaidingForPants/hd2-audio-modder/schemas/patch/task",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "archives": {
            "description": "An array of archive files you want to perform patch "
                           "automation",
            "type": "array",
            "items": {
                "type": "string"  
            },
            "minItems": 1
        },
        "data": {
            "description": "The file path of a directory for looking up archive "
                           "files. If this field is ignored, it will use the "
                           "file path stored in your configuration file, which "
                           "is the `data` folder for Helldivers 2 in the disk.",
            "type": "string"
        },
        "workspace": {
            "description": "The file path of a directory for looking up target "
                           "import automation manifest file.",
            "type": "string"
        },
        "includes": {
            "description": "An array of target import manifest files (relative "
                           "path or absolute path) you want to apply in the current "
                           "task. Each target import manifest will be applied on a freshly"
                           " open archive file.",
            "type": "array",
            "items": {
                "type": "string"
            },
            "minItems": 1
        },
        "merge": {
            "description": "Load all archive files into a single mod or load "
                           "each archive into individual mod.",
            "type": "boolean"
        },
    },
    "required": [ "archives", "workspace", "includes", "merge" ]
}

manifest_schema: Schema = {
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
        },
        "workers": {
            "description": "Number of worker processes that can process tasks"
                           " in parallel.",
            "type": "integer"
        }
    },
    "required": [ "version", "tasks" ]
}
