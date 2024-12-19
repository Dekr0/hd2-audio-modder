"""
async def dump_all_as_wav_async_v1(self, folder=""):
    if not os.path.exists(folder):
        folder = filedialog.askdirectory(title="Select folder to save files to")
    
    if not os.path.exists(folder):
        logger.warning("Invalid folder selected. Aborting dump.")
        return

    # progress = ProgressWindow(
    #         title="Dumping Files", 
    #         max_progress=len(self.file_reader.audio_sources))
    # progress.show()

    def on_done(task: asyncio.Task[tuple[str, int | None]]):
        path, rcode = task.result()
        if rcode != None and rcode != 0:
            logger.error(f"Failed to dump f{path}.wav: return code {rcode}")
        # progress.step()

    tasks: list[asyncio.Task[tuple[str, int | None]]] = []

    for bank in self.file_reader.wwise_banks.values():
        if bank.dep == None:
            raise RuntimeError(
                f"Wwise Soundbank {bank.get_id} in {self.file_reader.path}"
                 " is missing Wwise dependency")

        basename = os.path.basename(bank.dep.data.replace('\x00', ''))

        tmp_subfolder = os.path.join(CACHE_WEM, basename)
        try:
            if not os.path.exists(tmp_subfolder):
                os.mkdir(tmp_subfolder)
        except OSError as err:
            logger.error(f"Failed to create tmp stage area {tmp_subfolder}. "
                         f"Error: {err}")
        if not os.path.exists(tmp_subfolder):
            continue
            
        subfolder = os.path.join(folder, basename)
        try:
            if not os.path.exists(subfolder):
                os.mkdir(subfolder)
        except OSError as err:
            logger.error(f"Failed to create {subfolder}. Error: {err}")
        if not os.path.exists(subfolder):
            continue

        for audio in bank.get_content():
            source_id = str(audio.get_id())
            # progress.set_text(f"Dumping {source_id}.wav")

            task = asyncio.create_task(
                media_util.convert_wem_wav_buffer_async_v1(
                    f"{audio.get_id()}",
                    audio.get_data(),
                    subfolder,
                    tmp_subfolder,
                )
            )
            tasks.append(task)
            
            await task

            task.add_done_callback(on_done)

    block = asyncio.gather(*tasks)
    # block.add_done_callback(lambda _: progress.destroy())
    await block


def dump_all_as_wav_thread_v1(self, folder=""):
    if not os.path.exists(folder):
        folder = filedialog.askdirectory(title="Select folder to save files to")
    
    if not os.path.exists(folder):
        logger.warning("Invalid folder selected. Aborting dump.")
        return

    # progress = ProgressWindow(
    #         title="Dumping Files", 
    #         max_progress=len(self.file_reader.audio_sources))
    # progress.show()

    def on_convert_finished(rcode: int, source_id: str):
        if rcode != 0:
            logger.error(f"Failed to dump {source_id}.wav. vgmstream return"
                         f"none zero code: {rcode}")
        # progress.step()

    def on_convert_error(err: BaseException, source_id: str):
        logger.error(f"Failed to dump {source_id}.wav. Error: {err}")
        # progress.step()

    with pool.ThreadPool(processes=4) as p:
        for bank in self.file_reader.wwise_banks.values():

            if bank.dep == None:
                raise RuntimeError(
                    f"Wwise Soundbank {bank.get_id} in {self.file_reader.path}"
                     " is missing Wwise dependency")

            basename = os.path.basename(bank.dep.data.replace('\x00', ''))

            tmp_subfolder = os.path.join(CACHE_WEM, basename)
            try:
                if not os.path.exists(tmp_subfolder):
                    os.mkdir(tmp_subfolder)
            except OSError as err:
                logger.error(f"Failed to create tmp stage area {tmp_subfolder}. "
                             f"Error: {err}")
            if not os.path.exists(tmp_subfolder):
                continue
                
            subfolder = os.path.join(folder, basename)
            try:
                if not os.path.exists(subfolder):
                    os.mkdir(subfolder)
            except OSError as err:
                logger.error(f"Failed to create {subfolder}. Error: {err}")
            if not os.path.exists(subfolder):
                continue

            for audio in bank.get_content():
                source_id = audio.get_id()
                # progress.set_text(f"Dumping {source_id}.wav")
                p.apply_async(
                    media_util.convert_wem_wav_buffer_sync,
                    [source_id, audio.get_data(), subfolder, tmp_subfolder],
                    callback=lambda rcode: on_convert_finished(rcode, source_id),
                    error_callback=lambda err: on_convert_error(err, source_id)
                )
        p.close()
        p.join()

    # progress.destroy()
"""
