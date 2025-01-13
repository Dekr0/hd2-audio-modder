# Module import
from imgui_bundle import imgui
from audio_modder import AudioSource
from backend.env import get_data_path
from ui.ui_flags import *
from ui.ui_keys import *
from ui.view_data import *

from log import logger


def gui_bank_explorer(bank_state: BankViewerState):
    file_handler = bank_state.file_handler
    title = "Bank Explorer"
    if hasattr(file_handler.file_reader, "name"):
        title += f" ({file_handler.file_reader.name})"

    imgui.push_id(str(hash(bank_state.file_handler)))
    ok, p_open = imgui.begin(title, True, imgui.WindowFlags_.menu_bar.value)
    if not ok:
        imgui.end()
        imgui.pop_id()
        return p_open

    gui_bank_explorer_menu(bank_state)

    file_picker = bank_state.file_picker
    file_handler = bank_state.file_handler

    gui_bank_explorer_table(bank_state)

    if file_picker.is_load_archive_file_ready():
        result = file_picker.archive_picker.result() # type: ignore

        if len(result) == 1:
            try:
                file_handler.load_archive_file(archive_file=result[0])
                if bank_state.source_view:
                    create_bank_source_view(bank_state)
                else:
                    create_bank_hierarchy_view(bank_state)
            except OSError as e:
                # Show popup window
                logger.error(e)
            except Exception as e:
                # Show popup window
                logger.error(e)

        file_picker.archive_picker = None

    imgui.end()
    imgui.pop_id()

    return p_open


def gui_bank_explorer_menu(bank_state: BankViewerState):
    if not imgui.begin_menu_bar():
        return

    if imgui.begin_menu("Load"):
        if imgui.begin_menu("Archive"):
            if imgui.menu_item_simple("From HD2 Data Folder"):
                bank_state.file_picker.schedule_load_archive_file(get_data_path())
            if imgui.menu_item_simple("Fromm File Explorer"):
                bank_state.file_picker.schedule_load_archive_file()
            imgui.end_menu()

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
    imgui.end_menu_bar()


def gui_bank_explorer_table(bank_viewer_state: BankViewerState):
    if len(bank_viewer_state.file_handler.get_wwise_banks()) == 0:
        return
    
    if imgui.button("\ue8fe") and not bank_viewer_state.source_view:
        bank_viewer_state.source_view = True
        create_bank_source_view(bank_viewer_state)
        bank_viewer_state.soundbank_imgui_selection.clear()
    imgui.same_line()
    if imgui.button("\ue97a") and bank_viewer_state.source_view:
        bank_viewer_state.source_view = False
        create_bank_hierarchy_view(bank_viewer_state)
        bank_viewer_state.soundbank_imgui_selection.clear()

    if not imgui.begin_table(WidgetKey.BANK_HIERARCHY_TABLE, 6, TABLE_FLAGS):
        return

    tree = bank_viewer_state.soundbank_source_view_root \
                      if bank_viewer_state.source_view \
                      else bank_viewer_state.soundbank_hirc_view_root

    linear_mapping = bank_viewer_state.soundbank_source_views_linear \
                      if bank_viewer_state.source_view \
                      else bank_viewer_state.soundbank_hirc_views_linear
    selection = bank_viewer_state.soundbank_imgui_selection

    bank_hirc_views = tree.children

    # [Table Column Setup]
    imgui.table_setup_column(BankExplorerTableHeader.FAV.value, 
                             TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column("", TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column(BankExplorerTableHeader.PLAY.value, 
                             TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column(BankExplorerTableHeader.DEFAULT_LABEL.value, 
                             TABLE_COLUMN_FLAGS)
    imgui.table_setup_column(BankExplorerTableHeader.USER_DEFINED_LABEL)
    imgui.table_setup_column(BankExplorerTableHeader.HIRC_ENTRY_TYPE)
    imgui.table_headers_row()
    # [End]

    ms_io = imgui.begin_multi_select(MULTI_SELECT_FLAGS, selection.size, len(linear_mapping))
    apply_selection_reqs(ms_io, linear_mapping, selection)

    for bank_hirc_view in bank_hirc_views:
        gui_bank_explorer_table_row(bank_viewer_state, bank_hirc_view)

    ms_io = imgui.end_multi_select()
    apply_selection_reqs(ms_io, linear_mapping, selection)

    imgui.end_table()


def gui_view_menu(bank_viewer_state: BankViewerState):
    if not imgui.begin_menu("View"):
        return

    if imgui.menu_item_simple("Source View") and not bank_viewer_state.source_view:
        bank_viewer_state.source_view = True
        # Perform fine grain control to minimize recomputation
        create_bank_source_view(bank_viewer_state)
        bank_viewer_state.soundbank_imgui_selection.clear()
    if imgui.menu_item_simple("Hierarchy View") and bank_viewer_state.source_view:
        bank_viewer_state.source_view = False
        # Perform fine grain control to minimize recomputation
        create_bank_hierarchy_view(bank_viewer_state)
        bank_viewer_state.soundbank_imgui_selection.clear()

    imgui.end_menu()


def gui_bank_explorer_table_row(
        bank_viewer_state: BankViewerState,
        hirc_view: SoundbankHierarchyBinding):
    selection: imgui.SelectionBasicStorage = bank_viewer_state.soundbank_imgui_selection

    hvid = hirc_view.view_id
    flags = TREE_NODE_FLAGS

    imgui.table_next_row()

    # [Column 0: Favorite]
    imgui.table_next_column()
    imgui.push_id(f"favorite_{hvid}")
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
    imgui.push_id(f"select_{hvid}")
    imgui.checkbox("", selected)
    imgui.pop_id()
    # [End]

    # [Column 2: Play]
    imgui.table_next_column()
    if hirc_view.hirc_entry_type == BankExplorerTableType.AUDIO_SOURCE:
        if imgui.arrow_button(f"play_{hvid}", imgui.Dir.right):
            audio = hirc_view.hierarchy_entry
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
    imgui.push_id(f"default_label_{hvid}")
    if len(hirc_view.children) <= 0:
        flags |= imgui.TreeNodeFlags_.leaf.value
    expand = imgui.tree_node_ex(hirc_view.default_label, flags)
    gui_bank_table_item_ctx_menu(bank_viewer_state)
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
        gui_bank_explorer_table_row(bank_viewer_state, c_hirc_view)

    imgui.tree_pop()

def gui_bank_table_item_ctx_menu(bank_viewer_state: BankViewerState):
    if not imgui.begin_popup_context_item():
        return

    if imgui.button("Copy Id"):
        imgui.close_current_popup()

    if imgui.begin_menu("Export"):
        if imgui.button("As .wem"):
            imgui.close_current_popup()
        if imgui.button("As .wav (Unordered)"):
            imgui.close_current_popup()
        if imgui.button("As .wav (Ordered)"):
            imgui.close_current_popup()
        if imgui.button("As .wav (Unordered) (0.1 sec Muted)"):
            imgui.close_current_popup()
        if imgui.button("As .wav (Ordered) (0.1 sec Muted)"):
            imgui.close_current_popup()
        imgui.end_menu()

    imgui.end_popup()


"""
Below implementation are directly one-to-one from ImGui Manual. ImGui does not
have an implementation that support multi selection for tree view. This 
implementation emulate the basic selection in Tkinter.
"""
def tree_node_get_open(node: SoundbankHierarchyBinding):
    return imgui.get_state_storage().get_bool(node.view_id)


def tree_node_set_open(node: SoundbankHierarchyBinding, open: bool):
    return imgui.get_state_storage().set_bool(node.view_id, open)


def tree_close_and_unselected_child_nodes(
    node: SoundbankHierarchyBinding,
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
        linear_mapping: list[SoundbankHierarchyBinding],
        selection: imgui.SelectionBasicStorage):
    for req in ms_io.requests:
        if req.type == imgui.SelectionRequestType.set_all:
            """
            Trigger right before a selection happen to clear the selection.
            Trigger when `Ctrl-A` is pressed
            """
            if req.selected:
                for i in range(len(linear_mapping)):
                    selection.set_item_selected(linear_mapping[i].view_id, req.selected)
            else:
                selection.clear()
        elif req.type == imgui.SelectionRequestType.set_range:
            head = req.range_first_item
            tail = req.range_last_item
            print(head, tail)
            for i in range(head, tail + 1):
                if linear_mapping[i].view_id == TREE_ROOT_VIEW_ID:
                    raise AssertionError(f"Invisible root node is inside the "
                                         "selection scheme")
                selection.set_item_selected(linear_mapping[i].view_id, req.selected)
