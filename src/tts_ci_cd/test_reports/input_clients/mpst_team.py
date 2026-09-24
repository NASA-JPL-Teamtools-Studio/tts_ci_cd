import logging
from pathlib import Path
import pdb
import pandas as pd
from datetime import datetime
from copy import copy
import getpass

from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

class TeamMember():
    def __init__(self):
        self.username = None
        self.first_name = None
        self.last_name = None
        self.phone_number = None
        self.email = None
        self.default_time_label = None
        self.time_labels = []

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'

class MpstTeam(InputClient):
    def _impl_init(self):
        self.members = {}

    def _impl_populate(self):
        self.add_team_member('ramlee', 'Richard', 'Lee', '(626) 318-7099', 'Richard.A.Lee@jpl.nasa.gov')
        self.add_team_member('muszynsk', 'Matt', 'Muszynski', '(626) 318-2959', 'Matt.Muszynski@jpl.nasa.gov')
        self.add_team_member('wdula', 'Walker', 'Dula', '(626) 353-1801', 'Walker.L.Dula@jpl.nasa.gov')
        self.add_team_member('winner', 'Emily', 'Winner', '(626) 460-9689', 'Emily.S.Winner@jpl.nasa.gov')
        self.add_team_member('unknown', 'N/A', 'N/A', 'N/A', 'N/A')

    def add_team_member(self, username, first_name, last_name, phone_number, email):
        self.members[username] = TeamMember()
        self.members[username].username = username
        self.members[username].first_name = first_name
        self.members[username].last_name = last_name
        self.members[username].phone_number = phone_number
        self.members[username].email = email

    def current_user(self):
        if getpass.getuser() in self.members.keys():
	        return self.members[getpass.getuser()]
        else:
                return self.members['unknown']
