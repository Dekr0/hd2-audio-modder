# Introduction

- This branch contains the upcoming new UI for the audio and text modding tool 
for Helldivers 2. For the original README.md, please refer to [here](https://github.com/RaidingForPants/hd2-audio-modder).

## Installation

- Download the latest release in [here](https://github.com/Dekr0/hd2-audio-modder/releases/tag/v0.0.0-exp).
- Unzip the compressed files. Please do not make the uncompressed files around.

## Expectation

- This version of the tool misses some features from the latest one. This is expected.
- Treat this version of the tool as a more efficient way of exploring different 
game archives and sound banks and exporting metadata.
- The missing features will be ported to this version of the tool. However, 
features that are focus on exploration and metadata export will have a higher 
priority.

## Report Bugs

- This version of the tool is actively under development. Please report bugs as 
there's one.

## For Contributors

### Development Environment Setup

- If you're in Windows, source the setup scripts by typing the following in the 
terminal `. configure.ps1`
- If you're in Linux / MacOS, source the setup scripts by typing the following 
in the terminal `source configure.sh`
- Once you source the setup scripts, type in the following `Setup` in the terminal.
This will download all the necessary dependencies for development.
- If you want to build a release, simply type in the following `Build` in the 
terminal.
    - The `Build` command function is partially finished for Linux / MacOS 
    currently. It lacks the logic of compressing the build result.
- The current build is target toward Windows only due to Wwise platform availability.
