"""
All fields in the schema is required so that dict to dataclass is easier to 
handle.
"""

from referencing.jsonschema import Schema


VERSION = 3


revert_schema: Schema = {
    "$id": "https://github.com/RaidingForPants/hd2-audio-modder/schemas/target_import/revert",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "description": "An object indicate whether if the audio modding tool will "
                   "revert all audio source to default before / after doing "
                   "target import.",
    "type": "object",
    "properties": {
        "before": {
            "description": "An true or false flag to indicate whether if the audio"
                           " modding tool will revert all audio source to default"
                           " before doing target import.",
            "type": "boolean"
        },
        "after": {
            "description": "An true or false flag to indicate whether the audio"
                           " modding tool will revert all audio source to default"
                           " audio source after doing target import **and** "
                           " generating a new patch.",
            "type": "boolean"
        }
    },
    "required": [
        "before", "after",
    ]
}

target_import_pair_schema: Schema = {
    "$id": "https://github.com/RaidingForPants/hd2-audio-modder/schemas/target_import/target_import_pair",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "description": "A target import pair",
    "type": "object",
    "properties": {
        "from": {
            "description": "A relative file path of an audio file under the file "
                           "path specified by `workspace`.",
            "type": "string",
        },
        "to": {
            "description": "A list of audio source ID in the active / loaded "
                           "archive that will be replaced by the audio file "
                           "specified by field `from`",
            "type": "array",
            "items": {
                "type": "integer"
            },
            "minItems": 1
        }
    },
    "required": [
        "from",
        "to"
    ]
}

target_import_schema: Schema = {
    "$id": "https://github.com/RaidingForPants/hd2-audio-modder/schemas/target_import/target_import",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "description": "`target_import` provide file path of all the audio source "
                   "you want to import",
    "type": "object",
    "properties": {
        "workspace": {
            "description": "A file path that contains all audio files you want "
                           "to import in this section of target import",
            "type": "string"
        },
        "folders": {
            "description": "An array of target import section. Make it as an "
                           "empty array to skip this step.",
            "type": "array",
            "items": { "$ref": "#" },
            "minItems": 0
        },
        "pairs": {
            "description": "An array of target import pairs that will be performed"
                           "in this section of target import.",
            "type": "array",
            "items": target_import_pair_schema,
            "minItems": 1
        }
    },
    "required": [ "workspace", "folders", "pairs" ]
}

task_schema: Schema = {
    "$id": "https://github.com/RaidingForPants/hd2-audio-modder/target_import/schemas/task",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "description": "A task repesents a list of steps being done in a target import"
                   " for the active / loaded archive.",
    "type": "object",
    "properties": {
        "revert_all": revert_schema,
        "write_patch_to": {
            "description": "A file path for generate a new patch after finishing"
                           " target import all the prov$ided audio source and before "
                           "reverting all audio source back to default. Put an "
                           " empty path to skip this step",
            "type": "string",
        },
        "target_imports": {
            "description": "An array of target import the current target import "
                           "task will perform.",
            "type": "array",
            "items": target_import_schema,
            "minItems": 1
        }
    },
    "required": [
        "revert_all",
        "target_imports",
        "write_patch_to",
    ]
}

manifest_schema: Schema = {
    "$id": "https://github.com/RaidingForPants/hd2-audio-modder/schemas/target_import/manifest",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "version": { 
            "description": "Version of target import manifest",
            "const": VERSION
        },
        "tasks": {
            "description": "An array of target import tasks that will be run on "
                           "the current acitve / loaded archive. The order of  "
                           "of task execution will be in the order they "
                           "are declared.",
            "type": "array",
            "items": task_schema,
            "minItems": 1
        }
    },
    "required": [ "version", "tasks" ],
}
