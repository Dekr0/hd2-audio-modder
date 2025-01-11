# Guide: Automation in Audio Modding Tool

## Target Import Automation

### Target Import Automation Using CSV (Comma Separated Values) Files

#### Intro

- Using CSV to automate target import is simplest way to get into target import 
automation.
- However, it lacks a lot of controls on how target import behave and perform, and 
additional features in comparison to using manifest file to automate target import. 
- Once you're familiar with automating target import with CSV files, go ahead to 
take a look on next section of this guide on how to automate target import manifest
 file.

#### Rules & Syntax

- If you're unfamiliar with CSV file, google it. It's very simple, it's 
simplified way of writing spreadsheet file in plain text with some rules and 
syntax.
- When using CSV to automate target import, the CSV file you write must follow 
the rules and syntax describe below in order to be parsed and run correctly by 
the audio modding tool.
    - Each line / row of a CSV file, the column value must follow the following 
    rules:
        - The first column must be the absolute path or relative path (with 
        respect to the directory path of a CSV file you're using to automate 
        target import) for an audio file you want to import. Let say this file 
        path to be `P`.
            - You can ignore the file extension if an audio file you want to 
            import is wave file format.
        - The second column must be the number of audio source IDs you want to replace 
        with the provided audio file. Let say this number will be `N`.
        - Starting the third column to `N`th column (`N` is the number of audio 
        source specified in the second column).
            - Each column will only have a single audio source ID you want to 
            replace with audio source `P` (`P` is the file path specified in the
             first column).
            - The number of columns you provide after the first two column must 
            be equal `N`.

#### Example

- Given that you have following file structure
```
ar-19
|
---mag_in.wav
|
---mag_out.wav
|
---target_import.csv
```
- You're using `target_import.csv` to automate target import. In `target_import.csv`
 , you have the following:
```csv
mag_in,3,123,456,789
mag_out,3,321,654,987
```
- When the audio modding tool parse this, it will perform the following:
    - `ar-19/mag_in.wav` will replace audio sources with IDs `123`, `456`, and 
    `789`
    - `ar-19/mag_out.wav` will replace audio sources with IDs `321`, `654`, and 
    `987`.
- As you notice, let say in first row / first line, the number provided in the 
second column (after the first comma) is `3`. It matches up of number of audio 
source IDs provided in the next `3` columns.
- If you write `2` in the second column in the first row, the audio modding tool 
will only parse and replace audio source IDs `123` and `456`. `789` will be 
discarded during the parsing process, and won't be replaced with `ar-19/mag_in.wav`.
- If you write `4` in the second column in the first row instead, the audio 
modding tool will skip this row because the number of audio source IDs provided 
doesn't match the number specified in the second column.
- The audio modding tool will show warn message either in the form of pop up 
window, or inside the console if there's something wrong with the provided CSV 
file.

#### Tips For Writing CSV File Easier

- In the audio modding tool, you can select some number of entries in the tree 
view. Then, you will see an option that allow you generate a target import csv 
file (based off you selection) and put it into your clipboard after you right 
click.
- You can use Google Sheet or Excel to edit your target import csv file as it 
provide more visual pleasing experience, and you automate further with functions 
and macros in Excel or Google Sheet.

### Target Import Automation Using Manifest Files

#### Intro

- This is a little bit more advance way to automate target import in comparison 
to using CSV file since it allows you to:
    - revert all audio source back to its original state before or after a 
    target import **task** is run,
    - generate a patch (comes with `manifest.json` template) in a specified 
    destination in your disk,
    - specify your target import as a file structure tree, 
    - run multiple target import automation in batch (e.g., you can run 6 target 
    import automation in a batch, and each of them generate a patch with different 
     audio contents)
- The target import manifest file for target import automation uses the same file
format as the `manifest.json` used by Helldivers 2 Mod Manager. It's JSON format.
- The JSON syntax of writing the target import manifest file will be same as how 
you write your `manifest.json` file for your mod.
- The only thing difference is the schema / the structure.
- Here I assume most people who use target import automation aren't very familiar 
with JSON format and how to work with them. So I will explain this through an 
example.
- If you're familiar with JSON format and how to work with them, check the schema 
provided later in this section.

#### Example (Basic)

- Given you have following file structure
```
manifest.json
audio
  |
  ---mag_in_01.wav
  |
  ---mag_in_02.wav
  |
  ---mag_in_03.wav
  |
  ---mag_out_01.wav
  |
  ---mag_out_02.wav
  |
  ---mag_out_03.wav
```

- Inside of `manifest.json`, you have the following:

```json
{
    "version": 3,
    "tasks": [
        {
            "revert_all": {
                "before": false,
                "after": true
            },
            "write_patch_to": "patch",
            "target_imports": [
                {
                    "workspace": "audio",
                    "folders": [],
                    "pairs": [
                        { "from": "mag_in_01", "to": [ 123 ] },
                        { "from": "mag_in_02", "to": [ 456, 789 ] },
                        
                        { "from": "mag_out_01", "to": [ 100 ] },
                        { "from": "mag_out_02", "to": [ 200, 300 ] }
                    ]
                }
            ]
        }
    ]
}
```

- You can use the above example as a template for target import manifest.
- The only thing you really care about for basic usage is the following:
    - field `revert_all` 
    - field `write_patch_to`
    - an array of listing in field `pairs`:
- Field `revert_all` specifies whether if you want to revert all audio sources 
back to original state before doing a target import or after doing a target import 
 **and** generating a patch.
- Field `write_patch_to` specifies the location your patch will be generated. 
    - It can an absolute path (e.g. `C:/Program Files/steam/...`) or relative path
    (the directory path the target import manifest is at).
    - You can put an empty string (e.g., `"write_patch_to": ""`) to tell the 
    audio modding tool not to generate a patch.
- Field `workspace` specifies an absolute path or relative path (the directory 
path the target import manifest is at) for looking up all audio files you want 
to import.
- Field `pairs` include a target import **pair** listing. This listing contain 
a list of target import **pair**. Each target import pair must follow the following
rules and syntax:
    - Must resemble `{ "from": "...", "to": [ ..., ..., ... ] }`. `...` is the 
    value you want to replace.
    - Field `from` specifies the audio file you want to import.
        - If you don't provide a path for field `workspace`, you should provide 
        an absolute path. Otherwise, use relative path.
    - Field `to` specifies a list of audio source IDs you want to replace with 
    the audio file specified by field `from`.
        - It cannot be an empty listing of audio source IDs.
        - Every audio source ID must be an integer.
        - All audio source ID must be enclosed by a pair of square bracket `[]`.
        (e.g., `"to": [123, 456]`)
        - Each audio source ID must be separated by a comma `,`. Trailing comma 
        is not allowed (e.g. `"to": [123,]` and`"to": [123,456,]` will result 
        a parsing error.)
- Let go back to the example. Base on the content in the `manifest.json`,

```json
{
    "version": 3,
    "tasks": [
        {
            "revert_all": {
                "before": false,
                "after": true
            },
            "write_patch_to": "patch",
            "target_imports": [
                {
                    "workspace": "audio",
                    "folders": [],
                    "pairs": [
                        { "from": "mag_in_01", "to": [ 123 ] },
                        { "from": "mag_in_02", "to": [ 456, 789 ] },
                        
                        { "from": "mag_out_01", "to": [ 100 ] },
                        { "from": "mag_out_02", "to": [ 200, 300 ] }
                    ]
                }
            ]
        }
    ]
}

```

- The audio modding tool will do the following,
    1. Perform target import 
        - `audio/mag_in_01.wav` will replace audio source with ID `123`,
        - `audio/mag_in_02.wav` will replace audio source with IDs `456` and `789`,
        - `audio/mag_out_01.wav` will replace audio source with ID `100`,
        - `audio/mag_out_02.wav` will replace audio source with IDs `200` and `300`
    3. Generate a new patch in path `patch`
    4. Revert all audio source back to original state.

- Let change this a little bit. If change field `before` to true, and change field
`after` to false, the audio modding tool will:
    - Revert all audio source back to original state before perform target import
    - It will not revert all audio source back to original state after generating 
    a new patch.

#### Example (Advanced Usage: Multiple Target Imports)

- This section is under construction. 

#### Example (Advanced Usage: Nested Target Import)

- This section is under construction

#### Example (Advanced Usage: Multiple Target Import Tasks)

- This section is under construction

#### Target Import Manifest Schema

- The full schema for target import is in here.
