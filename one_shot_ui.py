"""
This is a proposal to provide a list of one shot UI API calls to factor out the 
UI logic from backend logic. Only use this if backend logic has to make sort of 
UI call because message passing is difficult to implement in some specific cases.
(for example, async or multi-threading)
"""

def show_warning(title: str, msg: str):
    """
    # Example
    tkinter.messagebox.showwarning(title=title, message=msg)
    """
    pass

def show_error(title: str, msg: str):
    """
    # Example
    tkinter.messagebox.showwarning(title=title, message=msg)
    """
    pass
