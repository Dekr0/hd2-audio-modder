import asyncio
import os
import shutil
import time

from const_global import CACHE, CACHE_WEM
from ui_controller_file import FileHandler

handler = FileHandler()
handler.load_archive_file()
os.system("cls")

c = 16

if not os.path.exists(CACHE):
    os.mkdir(CACHE)

CACHE_WAV = os.path.join(CACHE, "wav")

def timing_async(callback, oc: int | None = None):
    total = 0
    for i in range(oc if oc != None and oc > 0 else c):
        if not os.path.exists(CACHE_WEM):
            os.mkdir(CACHE_WEM)
        if not os.path.exists(CACHE_WAV):
            os.mkdir(CACHE_WAV)
        start = time.perf_counter_ns()
        asyncio.run(callback(folder=CACHE_WAV), debug=False)
        delta = time.perf_counter_ns() - start 
        total += delta
        # print(f"Attempt {i}: {delta} ns")
        time.sleep(1)
        shutil.rmtree(CACHE_WEM)
        shutil.rmtree(CACHE_WAV)
    print("")
    return total // (oc if oc != None and oc > 0 else c)

def timing(callback, oc: int | None = None):
    total = 0
    for i in range(oc if oc != None and oc > 0 else c):
        if not os.path.exists(CACHE_WEM):
            os.mkdir(CACHE_WEM)
        if not os.path.exists(CACHE_WAV):
            os.mkdir(CACHE_WAV)
        start = time.perf_counter_ns()
        callback(folder=CACHE_WAV)
        delta = time.perf_counter_ns() - start 
        total += delta
        # print(f"Attempt {i}: {delta} ns")
        time.sleep(1)
        shutil.rmtree(CACHE_WEM)
        shutil.rmtree(CACHE_WAV)
    print("")
    return total // (oc if oc != None and oc > 0 else c)

# serial = timing(handler.dump_all_as_wav, oc = 1)
# async_v1 = timing_async(handler.dump_all_as_wav_async_v1)
# async_v2 = timing_async(handler.dump_all_as_wav_async_v2)
# thread_v1 = timing(handler.dump_all_as_wav_thread)
thread_v2 = timing(handler._dump_all_as_wav_thread)

# print(f"Reference: f{serial} ns")
# print(f"Time delta average ({c} times)")
# print(f"async_v1 version: {async_v1} ns")
# print(f"thread_v1 version: {thread_v1} ns")
# print(f"asyncio   version: {async_v2} ns")
print(f"thread_v2 version: {thread_v2} ns")
