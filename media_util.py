import asyncio
import os
import subprocess

from const_global import VGMSTREAM

"""
@param name - name of the file (without extension)
@param buffer
@param (optional) tmp_path - temporary folder of the wem file
"""
def write_wem_sync(name: str, buffer: bytearray | bytes, tmp_path: str = ""):
    path = f"{name}.wem"
    if tmp_path != "":
        path = os.path.join(tmp_path, path)
    with open(path, "wb") as f:
        f.write(buffer)
    return path

"""
@param name - name of the file (without extension)
@param buffer
@param (optional) tmp_path - temporary folder of the wem file
"""
async def write_wem_async(
        name: str, 
        buffer: bytearray | bytes, 
        tmp_path: str = ""):
    path = f"{name}.wem"
    if tmp_path != "":
        path = os.path.join(tmp_path, path)
    with open(path, "wb") as f:
        f.write(buffer)
    return path

def convert_wem_wav_buffer_sync(
    name: str,
    buffer: bytes | bytearray,
    dest_path: str = "",
    tmp_path: str = "",
):
    wem = write_wem_sync(name, buffer, tmp_path)

    wav = f"{name}.wav"
    if dest_path != "":
        wav = os.path.join(dest_path, wav)

    return convert_wem_wav_file_sync(wem, wav)

def convert_wem_wav_file_sync(
    source_path: str,
    dest_path: str
):
   process = subprocess.run([VGMSTREAM, "-o", dest_path, source_path],
                            stdout=subprocess.DEVNULL)
   return process.returncode

"""
@param name - name of the file (without extension)
@param buffer
@param (optional) dest_path - destination folder of the wav file
@param (optional) tmp_path - temporary folder of the wem file
"""
async def convert_wem_wav_buffer_async_v1(
    name: str,
    buffer: bytes | bytearray,
    dest_path: str = "",
    tmp_path: str = "" 
):
    wem = await write_wem_async(name, buffer, tmp_path=tmp_path)

    wav = f"{name}.wav"
    if dest_path != "":
        wav = os.path.join(dest_path, wav)

    process = await asyncio.create_subprocess_exec(
        VGMSTREAM,
        *["-o", f"{wav}", f"{wem}"], 
        stdout=asyncio.subprocess.DEVNULL
    )

    return (name, process.returncode)

"""
@param name - name of the file (without extension)
@param buffer
@param (optional) dest_path - destination folder of the wav file
@param (optional) tmp_path - temporary folder of the wem file
"""
async def convert_wem_wav_buffer_async_v2(
    name: str,
    buffer: bytes | bytearray,
    dest_path: str = "", 
    tmp_path: str = "",
):
    # wem = write_wem_sync(name, buffer, tmp_path=tmp_path)
    wem = await write_wem_async(name, buffer, tmp_path=tmp_path)

    wav = f"{name}.wav"
    if dest_path != "":
        wav = os.path.join(dest_path, wav)

    process = await asyncio.create_subprocess_exec(
        VGMSTREAM,
        *["-o", f"{wav}", f"{wem}"], 
        stdout=asyncio.subprocess.DEVNULL,
    )

    return process.returncode
