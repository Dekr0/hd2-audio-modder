from cx_Freeze import setup, Executable

build_exe_options = {
    "excludes": ["tkinter", "unittest"],
    "includes": ["OpenGL"],
    "packages": ["OpenGL"],
    "include_files": [
        "fonts",
        "vgmstream-win64",
        "database"
    ]
}

setup(
    name = "Shovel",
    version = "0.0",
    options = {
        "build_exe": build_exe_options,
    },
    executables = [
        Executable("main.py", target_name="shovel.exe")
    ]
)
