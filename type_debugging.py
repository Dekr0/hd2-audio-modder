from backend.core import ModHandler

ModHandler.create_instance()
handler: ModHandler | None = ModHandler.get_instance()
if handler == None:
    raise AssertionError()
handler.create_new_mod("M1")
mod = handler.get_active_mod()

mod.load_archive_file("D:/sfx/MG/patch/hmg/squad_dshk/0bdf199f7ac14f43.patch_0")
mod.load_archive_file("D:/sfx/MG/patch/hmg/squad_dshk/68e80476c1c602f5.patch_0")
mod.load_archive_file("D:/sfx/MG/patch/hmg/squad_dshk/902c54afb4ed396f.patch_0")
