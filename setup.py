from cx_Freeze import setup, Executable

build_exe_options = {
    "excludes": [
        "pyinstaller",
        "pyinstaller-hooks-contrib",
        "PyAudio"
        "tkinter",
        "tkinterdnd2",
        "unittest",
        "watchdog",
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
