# Module import
from collections import deque
import os
import subprocess
from imgui_bundle import imgui

from backend.core import AudioSource
from backend.env import SYS_CLIPBOARD, get_data_path
from ui.ui_flags import *
from ui.ui_keys import *
from ui.view_data import *

from log import logger


def gui_bank_explorer(app_state: AppState, bank_state: BankViewerState):
    file_handler = bank_state.file_handler
    title = "Bank Explorer"
    if hasattr(file_handler.file_reader, "name"):
        title += f" ({file_handler.file_reader.name})"

    ok, p_open = imgui.begin(title, True, imgui.WindowFlags_.menu_bar.value)
    if not ok:
        imgui.end()
        return p_open

    gui_bank_explorer_menu(app_state, bank_state)

    archive_picker = bank_state.archive_picker
    file_handler = bank_state.file_handler

    gui_bank_explorer_table(app_state, bank_state)

    if archive_picker.is_ready():
        result = archive_picker.get_result()

        if len(result) == 1:
            try:
                file_handler.load_archive_file(archive_file=result[0])
                if bank_state.source_view:
                    create_bank_source_view(bank_state)
                else:
                    create_bank_hierarchy_view(bank_state)
            except OSError as e:
                # Show popup window or display on the logger
                logger.error(e)
            except Exception as e:
                # Show popup window or display on the logger
                logger.error(e)

        archive_picker.reset()

    imgui.end()

    return p_open


def gui_bank_explorer_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu_bar():
        return

    # gui_bank_explorer_view_menu(app_state, bank_state)
    gui_bank_explorer_load_menu(app_state, bank_state)

    imgui.end_menu_bar()


def gui_bank_explorer_load_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Load"):
        return

    gui_bank_explorer_load_archive_menu(app_state, bank_state)
    gui_bank_explorer_load_patch_menu(app_state, bank_state)

    imgui.end_menu()


def gui_bank_explorer_load_archive_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Archive"):
        return

    archive_picker = bank_state.archive_picker

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if os.path.exists(get_data_path()):
            try:
                archive_picker.schedule("Select An Archive", get_data_path())
            except AssertionError:
                app_state.warning_modals.append(
                    MessageModalState("Please finish the current archive selection.")
                )
        else:
            app_state.warning_modals.append(MessageModalState(
                f"The directory path for Helldivers 2 data folder in the setting "
                " is not correct. Please set the correct path in the Setting."
            ))

    if imgui.menu_item_simple("From File Explorer"):
        try:
            archive_picker.schedule("Select An Archive")
        except AssertionError:
            app_state.warning_modals.append(
                MessageModalState("Please finish the current archive selection.")
            )

    imgui.end_menu()


def gui_bank_explorer_load_patch_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Load"):
        return

    if imgui.begin_menu("Patch"):
        if imgui.menu_item_simple("Load"):
            pass
        if imgui.begin_menu("Write"):
            if imgui.menu_item_simple("Without Manifest"):
                pass
            if imgui.menu_item_simple("With Manifest"):
                pass
            imgui.end_menu()
        imgui.end_menu()
    imgui.end_menu()


"""
def gui_bank_explorer_view_menu(app_state: AppState, bank_viewer_state: BankViewerState):
    if not imgui.begin_menu("View"):
        return

    if imgui.menu_item_simple("Source View") and not bank_viewer_state.source_view:
        bank_viewer_state.source_view = True
        # Perform fine grain control to minimize recomputation
        create_bank_source_view(bank_viewer_state)
        bank_viewer_state.imgui_selection_store.clear()
    if imgui.menu_item_simple("Hierarchy View") and bank_viewer_state.source_view:
        bank_viewer_state.source_view = False
        # Perform fine grain control to minimize recomputation
        create_bank_hierarchy_view(bank_viewer_state)
        bank_viewer_state.imgui_selection_store.clear()

    imgui.end_menu()
"""


def gui_bank_explorer_table(app_state: AppState, bank_viewer_state: BankViewerState):
    if len(bank_viewer_state.file_handler.get_wwise_banks()) == 0:
        return

    bsid = bank_viewer_state.id
    imgui.push_id(bsid + "source_view")
    if imgui.button("\ue8fe") and not bank_viewer_state.source_view:
        bank_viewer_state.source_view = True
        create_bank_source_view(bank_viewer_state)
        bank_viewer_state.imgui_selection_store.clear()
    imgui.pop_id()

    imgui.push_id(bsid + "hirc_view")
    imgui.same_line()
    if imgui.button("\ue97a") and bank_viewer_state.source_view:
        bank_viewer_state.source_view = False
        create_bank_hierarchy_view(bank_viewer_state)
        bank_viewer_state.imgui_selection_store.clear()
    imgui.pop_id()

    if not imgui.begin_table(WidgetKey.BANK_HIERARCHY_TABLE, 6, TABLE_FLAGS):
        return

    tree = bank_viewer_state.source_view_root \
                      if bank_viewer_state.source_view \
                      else bank_viewer_state.hirc_view_root

    linear_mapping = bank_viewer_state.source_views_linear \
                      if bank_viewer_state.source_view \
                      else bank_viewer_state.hirc_views_linear
    imgui_selection_store = bank_viewer_state.imgui_selection_store

    bank_hirc_views = tree.children

    # [Table Column Setup]
    imgui.table_setup_scroll_freeze(0, 1)
    imgui.table_setup_column(BankExplorerTableHeader.FAV.value, 
                             TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column("", TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column(BankExplorerTableHeader.PLAY.value, 
                             TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column(BankExplorerTableHeader.DEFAULT_LABEL.value, 
                             TABLE_COLUMN_FLAGS_INDENT)
    imgui.table_setup_column(BankExplorerTableHeader.USER_DEFINED_LABEL)
    imgui.table_setup_column(BankExplorerTableHeader.HIRC_ENTRY_TYPE)
    imgui.table_headers_row()
    # [End]

    ms_io = imgui.begin_multi_select(MULTI_SELECT_FLAGS, imgui_selection_store.size, len(linear_mapping))
    apply_selection_reqs(ms_io, linear_mapping, imgui_selection_store)

    for bank_hirc_view in bank_hirc_views:
        gui_bank_explorer_table_row(app_state, bank_viewer_state, bank_hirc_view)

    ms_io = imgui.end_multi_select()
    apply_selection_reqs(ms_io, linear_mapping, imgui_selection_store)

    imgui.end_table()


def gui_bank_explorer_table_row(
        app_state: AppState,
        bank_viewer_state: BankViewerState,
        hirc_view: HierarchyView):
    selection: imgui.SelectionBasicStorage = bank_viewer_state.imgui_selection_store

    bsid = bank_viewer_state.id
    hvid = hirc_view.view_id
    flags = TREE_NODE_FLAGS

    imgui.table_next_row()

    # [Column 0: Favorite]
    imgui.table_next_column()
    imgui.push_id(f"{bsid}_favorite_{hvid}")
    imgui.button("\ue838")
    imgui.pop_id()
    # [End]

    # [Column 1: Select]
    selected = selection.contains(hvid)
    if selected:
        flags |= imgui.TreeNodeFlags_.selected.value
    imgui.set_next_item_storage_id(hvid)
    imgui.set_next_item_selection_user_data(hvid)

    imgui.table_next_column()
    imgui.push_id(f"{bsid}_select_{hvid}")
    imgui.checkbox("", selected)
    imgui.pop_id()
    # [End]

    # [Column 2: Play]
    imgui.table_next_column()
    if hirc_view.hirc_entry_type == BankExplorerTableType.AUDIO_SOURCE:
        if imgui.arrow_button(f"{bsid}_play_{hvid}", imgui.Dir.right):
            audio = hirc_view.data
            if not isinstance(audio, AudioSource):
                raise AssertionError("Entry is marked as type audio source but "
                                     "binding data is not an instance of Audio "
                                     f"Source ({type(audio)}).")
            bank_viewer_state.sound_handler.play_audio(audio.get_short_id(), audio.get_data())
    else:
        imgui.text_disabled("--")
    # [End]

    # [Column 3: Default Label]
    imgui.table_next_column()
    imgui.push_id(f"{bsid}_default_label_{hvid}")
    if len(hirc_view.children) <= 0:
        flags |= imgui.TreeNodeFlags_.leaf.value
    expand = imgui.tree_node_ex(hirc_view.default_label, flags)
    gui_bank_table_item_ctx_menu(hirc_view, bank_viewer_state)
    imgui.pop_id()
    # [End]

    # [Column 4: User Defined Label]
    imgui.table_next_column()
    imgui.text(hirc_view.user_defined_label)
    # [End]

    # [Column 5: Hirc. Type]
    imgui.table_next_column()
    imgui.text(hirc_view.hirc_entry_type.value)
    # [End]

    if not expand:
        return

    for c_hirc_view in hirc_view.children:
        gui_bank_explorer_table_row(app_state, bank_viewer_state, c_hirc_view)

    imgui.tree_pop()


def gui_bank_table_item_ctx_menu(hirc_view: HierarchyView, 
                                 bank_viewer_state: BankViewerState):
    if not imgui.begin_popup_context_item():
        return
    
    if imgui.begin_menu("Copy"):
        if imgui.menu_item_simple("As .CSV"):
            pass
        if imgui.begin_menu("As Plain Text"):
            if imgui.menu_item_simple("Audio Source Only"):
                copy_audio_entry(hirc_view, bank_viewer_state, True)
            if imgui.menu_item_simple("Audio Source Only (ID only)"):
                copy_audio_entry(hirc_view, bank_viewer_state)
            if imgui.menu_item_simple("Tree Structure With Descendant"):
                pass
            if imgui.menu_item_simple("Tree Structure With No Descendant"):
                pass
            imgui.end_menu()
        imgui.end_menu()

    if imgui.begin_menu("Export"):
        if imgui.begin_menu("As .wav"):
            if imgui.begin_menu("With Sound"):
                if imgui.menu_item_simple("Without Sequence Suffix"):
                    pass
                if imgui.menu_item_simple("With Sequence Suffix"):
                    pass
                imgui.end_menu()
            if imgui.begin_menu("Slient"):
                if imgui.menu_item_simple("Without Sequence Suffix"):
                    pass
                if imgui.menu_item_simple("With Sequence Suffix"):
                    pass
                imgui.end_menu()
            imgui.end_menu()
        imgui.end_menu()

    imgui.end_popup()


"""
Below implementation are directly one-to-one from ImGui Manual. ImGui does not
have an implementation that support multi selection for tree view. This 
implementation emulate the basic selection in Tkinter.
"""
def tree_node_get_open(node: HierarchyView):
    return imgui.get_state_storage().get_bool(node.view_id)


def tree_node_set_open(node: HierarchyView, open: bool):
    return imgui.get_state_storage().set_bool(node.view_id, open)


def tree_close_and_unselected_child_nodes(
    node: HierarchyView,
    selection: imgui.SelectionBasicStorage,
    depth: int
    ):
    """
    When closing a node:
    1. close and unselect all children
    2. select parent if any child was selected
    """
    unselected_count = 1 if selection.contains(node.view_id) else 0
    if depth == 0 or tree_node_get_open(node):
        for c in node.children:
            unselected_count += tree_close_and_unselected_child_nodes(
                    c, selection, depth + 1)
            tree_node_set_open(node, False)

    # Select root node if any of its child was selected, otherwise unselect
    selection.set_item_selected(node.view_id, depth == 0 and unselected_count > 0)
    return unselected_count


def apply_selection_reqs(
        ms_io: imgui.MultiSelectIO,
        linear_mapping: list[HierarchyView],
        imgui_selection_store: imgui.SelectionBasicStorage):
    for req in ms_io.requests:
        if req.type == imgui.SelectionRequestType.set_all:
            """
            Trigger right before a selection happen to clear the selection.
            Trigger when `Ctrl-A` is pressed
            """
            if req.selected:
                for i in range(len(linear_mapping)):
                    imgui_selection_store.set_item_selected(linear_mapping[i].view_id, req.selected)
            else:
                imgui_selection_store.clear()
        elif req.type == imgui.SelectionRequestType.set_range:
            head = req.range_first_item
            tail = req.range_last_item
            for i in range(head, tail + 1):
                if linear_mapping[i].view_id == TREE_ROOT_VIEW_ID:
                    raise AssertionError(f"Invisible root node is inside the "
                                         "selection scheme")
                imgui_selection_store.set_item_selected(
                    linear_mapping[i].view_id, req.selected)

"""
End of Tree view selection
"""

"""
Below section need to move to somewhere else
"""
def unfold_selection(selects: list[HierarchyView]):
    fold_select_set: set[int] = set([select.view_id for select in selects])
    unfold_select_set: set[int] = set()
    unfold_select_list: list[HierarchyView] = []
    for select in selects:
        parent_vid = select.parent_view_id
        if parent_vid not in fold_select_set:
            unfold_select_set.add(select.view_id)
            unfold_select_list.append(select)
    return unfold_select_list


def get_selection_binding(bank_viewer_state: BankViewerState):
    selects: list[HierarchyView] = []
    imgui_selection_store = bank_viewer_state.imgui_selection_store
    if bank_viewer_state.source_view:
        source_views_linear = bank_viewer_state.source_views_linear
        selects = [source_view
                   for source_view in source_views_linear 
                   if imgui_selection_store.contains(source_view.view_id)]
    else:
        hirc_views_linear = bank_viewer_state.hirc_views_linear
        selects = [hirc_view for hirc_view in hirc_views_linear 
                   if imgui_selection_store.contains(hirc_view.view_id)]

    return selects


def copy_audio_entry(
        hirc_view: HierarchyView,
        bank_viewer_state: BankViewerState,
        label: bool = False):
    selects = get_selection_binding(bank_viewer_state)
    if len(selects) == 0:
        selects = [hirc_view]
    audio_source_vid_set: set[int] = set()
    queue: deque[HierarchyView] = deque()
    content = "" 
    for select in selects:
        if len(queue) > 0:
            raise AssertionError()
        queue.append(select)
        while len(queue) > 0:
            top = queue.popleft()
            if top.hirc_entry_type == BankExplorerTableType.AUDIO_SOURCE:
                if not isinstance(top.data, AudioSource):
                    raise AssertionError()

                if top.view_id in audio_source_vid_set:
                    continue

                source_id = top.data.get_short_id()
                user_defined_label = top.user_defined_label
                audio_source_vid_set.add(top.view_id)
                if label:
                    content += f"{source_id}: \"{user_defined_label}\"\n"
                else:
                    content += f"{source_id}\n"
                continue

            for c_binding in top.children:
                queue.append(c_binding)

    copy_to_clipboard(content)


def copy_hirc_entry_unfold(hirc_view: HierarchyView, bank_viewer_state: BankViewerState):
    pass


def copy_hirc_entry_fold(hirc_view: HierarchyView, bank_viewer_state: BankViewerState):
    pass


def copy_to_clipboard(buffer: str):
    """
    @exception
    - CalledProcessError
    """
    subprocess.run(
            SYS_CLIPBOARD,
            universal_newlines=True,
            input=buffer).check_returncode()
