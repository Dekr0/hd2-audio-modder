import subprocess

from backend.env import SYS_CLIPBOARD


def copy_to_clipboard(buffer: str):
    """
    @exception
    - CalledProcessError
    """
    subprocess.run(
            SYS_CLIPBOARD,
            universal_newlines=True,
            input=buffer).check_returncode()
