from imgui_bundle import imgui


DOCKSPACE_FLAGS = imgui.DockNodeFlags_.none.value | \
                  imgui.DockNodeFlags_.passthru_central_node.value

DOCKING_WINDOW_FLAGS = imgui.WindowFlags_.menu_bar.value     | \
                       imgui.WindowFlags_.no_docking.value   | \
                       imgui.WindowFlags_.no_title_bar.value | \
                       imgui.WindowFlags_.no_collapse.value  | \
                       imgui.WindowFlags_.no_resize.value    | \
                       imgui.WindowFlags_.no_move.value      | \
                       imgui.WindowFlags_.no_background.value

DOCKING_WINDOW_FLAGS |= imgui.WindowFlags_.no_bring_to_front_on_focus.value | \
                        imgui.WindowFlags_.no_nav_focus.value

MULTI_SELECT_FLAGS = imgui.MultiSelectFlags_.clear_on_escape.value

TABLE_FLAGS = imgui.TableFlags_.resizable.value        | \
              imgui.TableFlags_.reorderable.value      | \
              imgui.TableFlags_.row_bg.value           | \
              imgui.TableFlags_.borders_h.value        | \
              imgui.TableFlags_.borders_v.value        | \
              imgui.TableFlags_.sizing_fixed_fit.value | \
              imgui.TableFlags_.no_host_extend_x.value | \
              imgui.TableFlags_.scroll_y.value

TABLE_COLUMN_FLAGS_INDENT = imgui.TableColumnFlags_.indent_enable.value
TABLE_COLUMN_FLAGS_FIXED = imgui.TableColumnFlags_.indent_disable.value | \
                           imgui.TableColumnFlags_.width_fixed.value

TREE_NODE_FLAGS  = imgui.TreeNodeFlags_.span_avail_width.value | \
                   imgui.TreeNodeFlags_.open_on_arrow.value | \
                   imgui.TreeNodeFlags_.open_on_double_click.value

TabBarFlags = imgui.TabBarFlags_.reorderable.value | \
              imgui.TabBarFlags_.auto_select_new_tabs.value | \
              imgui.TabBarFlags_.tab_list_popup_button.value | \
              imgui.TabBarFlags_.fitting_policy_scroll.value
