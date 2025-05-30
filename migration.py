from tests.mockup.py.AC8 import automate as ac8_automate
from tests.mockup.py.AMR import automate as amr_automate
from tests.mockup.py.ART import automate as art_automate
from tests.mockup.py.AR23 import automate as ar23_automate
from tests.mockup.py.AR61 import automate as ar61_automate
from tests.mockup.py.AXAR import automate as axar_automate
from tests.mockup.py.BR14 import automate as br14_automate
from tests.mockup.py.CAS import automate as cas_automate
from tests.mockup.py.EAT import automate as eat_automate
from tests.mockup.py.GL21 import automate as gl21_automate
from tests.mockup.py.GR8 import automate as gr8_automate
from tests.mockup.py.P4 import automate as p4_automate
from tests.mockup.py.RL77 import automate as rl_77_automate
from tests.mockup.py.M105 import automate as m105_automate
from tests.mockup.py.M206 import automate as m206_automate
from tests.mockup.py.MG43 import automate as mg43_automate
from tests.mockup.py.R63 import automate as r63_automate
from tests.mockup.py.RS422 import automate as rs422_automate


sfx_path = "D:/sfx_spec"

automations = [
    # ac8_automate,
    # ar61_automate, # unfinished, unchecked
    # ar23_automate,
    # amr_automate,
    # axar_automate,
    art_automate, # 380mm is missing whistle
    # br14_automate,
    # gl21_automate,
    # cas_automate,
    eat_automate, # seems to be quieter, mixing change slightly
    gr8_automate, # seems to be quieter, mixing change slightly
    m105_automate, # overhaul squad m249 tail
    # m206_automate,
    mg43_automate, # overhaul squad pkm and squad m240
    # p4_automate,
    # r63_automate, # mixing change slightly
    rl_77_automate, # seems to be quieter?
    # rs422_automate
]

for automate in automations:
    automate()
