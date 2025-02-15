from cx_Freeze import setup, Executable

build_exe_options = {
    "excludes": [
        "tkinter",
        "unittest",
        "watchdog",
        "pyinstaller",
        "pyinstaller-hooks-contrib",
        "tkinterdnd2",
        "PyAudio"
    ],
    "include_files": [
        "AudioConversionProject"
    ]
}

setup(
    name = "hat",
    version = "0.0",
    options = {
        "build_exe": build_exe_options,
    },
    executables = [
        Executable("cli.py", target_name="hat.exe")
    ]
)
