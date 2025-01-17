from collections import deque

from backend.util import copy_to_clipboard
from backend.core import AudioSource

from ui.view_data import BankViewerTableType, BankViewerState, HierarchyView


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
    hirc_views_linear = bank_viewer_state.hirc_views_linear
    selects = [hirc_view for hirc_view in hirc_views_linear 
                if imgui_selection_store.contains(hirc_view.view_id)]

    return selects


"""
Information Copying
"""
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
            if top.hirc_entry_type == BankViewerTableType.AUDIO_SOURCE:
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
