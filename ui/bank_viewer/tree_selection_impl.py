from imgui_bundle import imgui

from ui.view_data import BankViewerTableType, TREE_ROOT_VIEW_ID
from ui.view_data import BankViewerState, HierarchyView

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
        bank_viewer_state: BankViewerState):

    source_view_selectable = [
        BankViewerTableType.AUDIO_SOURCE,
        BankViewerTableType.AUDIO_SOURCE_MUSIC,
        BankViewerTableType.SOUNDBANK,
    ]

    linear_mapping = bank_viewer_state.hirc_views_linear
    imgui_selection_store = bank_viewer_state.imgui_selection_store
    source_view = bank_viewer_state.source_view

    for req in ms_io.requests:
        if req.type == imgui.SelectionRequestType.set_all:
            """
            Trigger right before a selection happen to clear the selection.
            Trigger when `Ctrl-A` is pressed
            """
            if req.selected:
                for i in range(len(linear_mapping)):
                    if source_view:
                        if linear_mapping[i].hirc_entry_type in source_view_selectable:
                            imgui_selection_store.set_item_selected(
                                linear_mapping[i].view_id, req.selected)
                    else:
                        imgui_selection_store.set_item_selected(
                                linear_mapping[i].view_id, req.selected)
            else:
                imgui_selection_store.clear()
        elif req.type == imgui.SelectionRequestType.set_range:
            head = req.range_first_item
            tail = req.range_last_item
            for i in range(head, tail + 1):
                if linear_mapping[i].view_id == TREE_ROOT_VIEW_ID:
                    raise AssertionError(f"Invisible root node is inside the "
                                         "selection scheme")
                if source_view:
                    if linear_mapping[i].hirc_entry_type in source_view_selectable:
                        imgui_selection_store.set_item_selected(
                            linear_mapping[i].view_id, req.selected)
                else:
                    imgui_selection_store.set_item_selected(
                        linear_mapping[i].view_id, req.selected)

"""
End of Tree view selection
"""
