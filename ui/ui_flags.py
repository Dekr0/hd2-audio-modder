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

TABLE_FLAGS = imgui.TableFlags_.resizable.value   | \
              imgui.TableFlags_.reorderable.value | \
              imgui.TableFlags_.borders_h.value   | \
              imgui.TableFlags_.borders_v.value   | \
              imgui.TableFlags_.sizing_fixed_fit.value | \
              imgui.TableFlags_.no_host_extend_x.value

TABLE_COLUMN_FLAGS = imgui.TableColumnFlags_.indent_disable.value
TABLE_COLUMN_FLAGS_FIXED = TABLE_COLUMN_FLAGS | \
                           imgui.TableColumnFlags_.width_fixed.value

TREE_NODE_FLAGS  = imgui.TreeNodeFlags_.span_avail_width.value | \
                   imgui.TreeNodeFlags_.open_on_arrow.value | \
                   imgui.TreeNodeFlags_.open_on_double_click.value

