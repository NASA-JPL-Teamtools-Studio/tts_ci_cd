import sys
from datetime import datetime
import logging
import pdb
from pathlib import Path
from enum import IntEnum
#from atlassian import Confluence

from tts_data_utils.core.generic import GenericContainer

import tts_tower
from tts_tower import util
from tts_tower.tower import Tower
from tts_tower.inputs.input_manager import InputManager, input_get
from tts_tower.inputs.input_client import FailedClient
from tts_tower.checkers.util import load_checkers
from tts_tower.util import AccessEnum
from tts_tower.checkers.checker_manager import CheckerManager
from tts_tower.rule_results import (
    consolidate_rule_results,
    verify_rule_revisions,
    consolidate_rule_reports,
)


logger = logging.getLogger(f'tower.ats_review_tower_check')


PALETTE = {
    'green': {'background-color': '#9FC793', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'yellow': {'background-color': '#FFF0B5', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'orange': {'background-color': '#F5C692', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'red': {'background-color': '#E89392', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'white': {'background-color': '#FFFFFF', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'grey': {'background-color': 'lightgray', 'color': 'black', 'font-weight': 'bold', 'text-align': 'center'},
    'black': {'background-color': '#333333', 'color': '#FFFFFF', 'font-weight': 'bold', 'text-align': 'center'},
    }


class RULE_MATURITY(IntEnum, AccessEnum):
    """
    Defines all possible maturity states of a Rule
    """
    UNKNOWN = -1
    DRAFT = 0
    APPROVED = 1
    IMPLEMENTED = 2
    UNIT_TESTED = 3
    VERIFIED = 4
    DELETED = 6

    def __init__(self, value):
        sort_order = {
            'DELETED': 6,
            'RETIRED': 5,
            'VERIFIED': 4,
            'UNIT_TESTED': 3,
            'IMPLEMENTED': 2,
            'APPROVED': 1,
            'DRAFT': 0,
            'UNKNOWN': -1,
        }

        description = {
            'UNKNOWN': 'Rule is of unknown status. This is only used when TOWER ' + \
                'encounters a problem and cannot understand the rule as defined in the dictionary.',
            'DRAFT': 'Rule has been authored, but no formal review has been performed. ' + \
                'rules in DRAFT state are informational only, and operators reviewing them should use' + \
                'engineering judgement to determine how they should be interpreted.',
            'APPROVED': 'Rule has been authored and approved by the team at an MPST meeting, but there is not ' + \
                'a software implementation yet.',
            'IMPLEMENTED': 'Rule has been approved, and there is a software implementation. ' +
                'Implementation is not yet tested, so should not be blindly trusted.',
            'UNIT_TESTED': 'Rule has been approved, implemented, and unit tested ' +
                'but the implemetnation and/or tests have not gone through any formal review.',
            'VERIFIED': 'Rule is approved, implemented, and unit tested, and the code has been ' + \
                'peer reviewed',
            'DELETED': 'Rule has been deleted from the database, but is kept as a record that it was once here. ',
            'RETIRED': 'Similar to DELETED, but whereas rules are deleted when they are found not to be valid ' + \
                'globally, retired rules are no longer valid, but once were. Examples include rules that are only ' + \
                'valid in a phase that will never happen again (e.g. launch and comissioning) or rules that pertainging ' + \
                'to an instrument on the spacecraft that has been decomissioned. Functionally, the difference between ' + \
                'retired and deleted rules is that retired rules are useful to save for posterity (e.g. we may be ' + \
                'commissioning a similar spacecraft or may build a similar instrument some day, and keeping a record ' + \
                'of how we operated this one is useful).'
        }        

        style = {
            'UNKNOWN': PALETTE['red'],
            'DRAFT': PALETTE['red'],
            'APPROVED': PALETTE['orange'],
            'IMPLEMENTED': PALETTE['orange'],
            'UNIT_TESTED': PALETTE['orange'],
            'VERIFIED': PALETTE['green'],
            'DELETED': PALETTE['black'],
        }      
        self._value_ = value
        self.sort_order = sort_order[self.name]
        self.description = description[self.name]
        self.style = style[self.name]

class RULE_CRITICALITY(IntEnum, AccessEnum):
    """
    Defines all possible criticality states of a Rule
    """
    A = 2
    B = 1
    C = 0
    I = -1
    DELETED = -2

    def __init__(self, value):
        sort_order = {
            'A': 2,
            'B': 1,
            'C': 0,
            'I': -1,
            'DELETED': -2
        }
        style = {
            'A': PALETTE['red'],
            'B': PALETTE['orange'],
            'C': PALETTE['green'],
            'I': PALETTE['white'],
            'DELETED': PALETTE['black'],
        }  
        description = {
            'A': 'Potential Vehicle Damage',
            'B': 'Safing or significant, but recoverable loss of operability',
            'C': 'Science data loss or minor, but recoverable loss of operability',
            'I': 'No impact to vehicle or minor affect with no feasible way to mitigate',
            'DELETED': 'Rule has been deleted. No checks executed or needed'
        }        
        self._value_ = value
        self.sort_order = sort_order[self.name]
        self.description = description[self.name]
        self.style = style[self.name]

class RULE_STATUS(IntEnum, AccessEnum):
    """Defines all possible status states of a Rule, in ascending order
    The numerical order of these Enums intrinsically defines which states can "overwrite" others

    A state with a larger number can overwrite a smaller one. E.g. if a Rule has state PENDING (5), it can
    be overwritten with any other state.  But if it has state PASSED (4), it can only be overwritten by
    FLAGGED (6), VIOLATING (7), or ERROR (8).  A rule that has state MISMATCH (9) will never change its state
    """
    MISMATCH = 9
    ERROR = 8
    VIOLATING = 7
    FLAGGED = 6

    PASSED = 5
    INFO_ONLY = 4
    NA = 3
    RETIRED = 2
    PENDING = 1
    DELETED = 0

    # MISMATCH = 9
    # ERROR = 8
    # VIOLATING = 7
    # FLAGGED = 6
    # PENDING = 5
    # PASSED = 4
    # INFO_ONLY = 3

    def __init__(self, value):
        ### YES! THESE ARE BACKWARDS COMPARED TO THE ENUM VALUES AND THEY ARE SUPPOSED TO BE!!
        # I ended up chasing myself in circles here... the enum values control which 
        # status is used when a rule has dispositions with more than one status. Higher numbers win
        # The sort order is for the final report. Lower numbers are "lighter" and float to the top.
        sort_order = {
            'MISMATCH': 0,
            'ERROR': 1,
            'VIOLATING': 2,
            'FLAGGED': 3,
            'PENDING': 4,
            'PASSED': 5,
            'INFO_ONLY': 6,
            'NA': 7,
            'RETIRED': 8,
            'DELETED': 9
        }

        description = {
            'DELETED': 'Rule has been deleted and is not relevant to this planning cycle.',
            'RETIRED': 'Rule has been retired and is not relevant to this planning cycle.',
            'NA': 'Rule is not applicable to this planning cycle (currently only used by PIPE-001, which is ' + \
                'not a real rule.)',
            'PASSED': 'All dispositions related to this rule passed, and it needs no human intervention ' + \
                '(assuming it is marked as VERIFIED)',
            'PENDING': 'No checks have been performed on this rule, and it must be checked manually by a human.',
            'INFO_ONLY': 'This rule has no checks, but is provided for informational purposes only. No manual ' + \
                'check is needed.',
            'FLAGGED': 'At least one disposition belonging to this rule is FLAGGED, which means that the software ' +
                'check was performed, but it was not able to tell if the rule passes. Manual check by a human is ' + \
                'required. See disposition records in expanded row for evidence of what the rule was able to check ' +\
                'and for further breadcrumbs for what needs to be manuallychecked to complete it..',
            'VIOLATING': 'At least one disposition belonging to this rule shows that the rule is being violated. ' + \
                'Human must check to understand why the rule is being violated, and either justify to the team why it ' + \
                'is OK to violate or ensure that the planning products get regenerated such that the rule is no longer ' + \
                'violated.',
            'ERROR': 'The software checking this rule has thrown an exception that was caught by TOWER. User must ' + \
                'treat this rule as if it were PENDING and check it fully manually. Alternatively, user can fix the TOWER ' + \
                'check so it no longer raises the same exception or ask another team member to do so, and rerun TOWER.',
            'MISMATCH': 'The TOWER rule dictionary includes a git commit hash for each rule marking the last time the rule ' + \
                'definition was changed. In order to ensure that rule definitions do not change without an associated change ' + \
                'to their software implementations, TOWER checks this hash every time the code runs. If the runtime hash for ' + \
                'a rule and the hash in the dictionary do not match, it will be marked as MISMATCH, and the user must either' + \
                'check the rule manually, or inspect the rule change to decide whether the dispositions can be trusted.'
        }        

        style = {
            'DELETED': PALETTE['black'],
            'NA': PALETTE['grey'],
            'PASSED': PALETTE['green'],
            'PENDING': PALETTE['grey'],
            'RETIRED': PALETTE['grey'],
            'INFO_ONLY': PALETTE['white'],
            'FLAGGED': PALETTE['orange'],
            'VIOLATING': PALETTE['red'],
            'ERROR': PALETTE['red'],
            'MISMATCH': PALETTE['red']
        }
        self._value_ = value
        self.sort_order = sort_order[self.name]
        self.description = description[self.name]
        self.style = style[self.name]


class OCO2_Tower(Tower):
    RULE_MATURITY = RULE_MATURITY
    RULE_STATUS = RULE_STATUS
    RULE_CRITICALITY = RULE_CRITICALITY
    RUN_INFO_ORDER = []
    def build_rule_metadata(self, dictionary_record):
        if dictionary_record is None:
            raw_data = [{}]
        else:
            raw_data = [
                {' ': 'Functional Category', '': dictionary_record.functional_category},
                {' ': 'Description', '': dictionary_record.description},
                {' ': 'Violation of Impact', '': dictionary_record.violation_impact},
                {' ': 'Tower Implementation', '': dictionary_record.tower_link},
                {' ': 'Revision', 'Value': dictionary_record.rev},
            ]

        return GenericContainer(raw_data=raw_data)