from abc import ABC, abstractmethod
import re
from datetime import datetime
import logging
import operator
from pathlib import Path
import pdb
import pandas as pd
import git
import json
from enum import IntEnum
from tts_tower.util import AccessEnum


from input_clients.oco_input_client import Oco2InputClient
from tts_html_utils.core.components.text import Paragraph as P
from tts_html_utils.core.components.text import Strong
from tts_html_utils.core.components.misc import Link

log = logging.getLogger(__name__)

TOWER_GITHUB_BASE_URL = Path('https://github.jpl.nasa.gov/muszynsk/OCO2_Tower/tree/main/tower')
TOWER_GITHUB_CHECKER_URL = TOWER_GITHUB_BASE_URL.joinpath('checkers')
ART_BASE_PATH = Path('/groups/calibration/released/Inflight_Calibration_Tools/ATS_Tools/')

MATURITY_DEFINITIONS = {
    'Draft': (
        'Rule has been entered to the database but has not been reviewed in any way.',
        'Use rule at your own risk.',
        'Use implementation at your own risk (if it even exists).'
        ),
    'Approved': (
        'Rule has been reviewed by MPST team and is valid, but has no automatic check.',
        'Rule is safe to use.',
        'Use implementation at your own risk (if it even exists).'
        ),

    'Implemented': (
        'Rule is being checked automatically, but that check has not been unit tested or reviewed.',
        'Rule is safe to use.',
        'Use implementation at your own risk.'
        ),
    'Unit Tested': (
        'Rule is being checked automatically, and that implementation is unit tested, but has yet to get a review by a second MPST team member.',
        'Rule is safe to use.',
        'Use implementation at your own risk.'
        ),
    'Verified': (
        'Rule is being checked automatically, but that check has not been unit tested or reviewed.',
        'Rule is safe to use.',
        'Use implementation at your own risk.'
        ),
    'Unknown': (
        'Something has gone wrong with TOWER or its underlying metadata.',
        'Use at your own risk.',
        'Use at your own risk (if it even exists).'
        ),
    'DELETED': (
        'This rule has been deleted.',
        'It is here for information only.',
        'Nothing to see here.'
        )
    }


# ===================================================================
# :: Rule
# ===================================================================
class RuleRecord(ABC):
    def __init__(self):
        return

    def validate_record(self):
        #TO DO: This is where we can put some code
        #to make sure that all the expected attributes
        #are here and are set correctly.
        missing_attrs = []
        required_attrs = [
            'id', 
            'title',
            'maturity',
            'description',
            'violation_impact',
            'crit',
            'rev'
            ]
        for required_attr in required_attrs:
            if required_attr not in self.__dict__.keys():
                missing_attrs.append(required_attr) 

        if len(missing_attrs):
            try:
                rule_id = self.id
            except AttributeError:
                rule_id = 'UNKNOWN Rule'
            raise Exception(f'{missing_attrs} attributes required on all rules. ' + \
                '{rule_id} does not have all required attributes. {missing_attrs} are absent')
        

    @abstractmethod
    def make_breakout(self):
        return


class OCO2Rule(RuleRecord):
    def __init__(self, rule_row, latest_hashes):
        super().__init__()
        # Initialize some source-specific fields that may be filled in by more specific initialization methods
        self.source = None
        self.url = ''

        # The basic format of a rule is CSV, with a row passed in here
        self.row = rule_row

        # Get the rule ID and split into the category, criticality (level), and #
        self.functional_category = self.row['Functional Category']
        self.id = self.row['Rule ID']
        self.title = self.row['Title']
        self.maturity = self.row['Maturity']
        self.description = self.row['Description'].replace('\n','<br />')
        self.violation_impact = self.row['Violation Impact']
        self.crit = self.row['Criticality']
        self.level = self.row['Criticality']
        self.tower_implementation = self.row['TOWER Implementation']
        self.tower_url = TOWER_GITHUB_CHECKER_URL.joinpath(self.tower_implementation)
        self.tower_link = Link(self.tower_url)
        try:
            self.rev = latest_hashes[self.id]
        except KeyError:
            self.rev = 'UNKNOWN'

        if len(self.row['Rule ID'].split('-')) == 2:
            self.opscat, self.number = self.row['Rule ID'].split('-')
        else:
            _, self.opscat, self.number = self.row['Rule ID'].split('-')
            self.opscat = f'OCO-{self.opscat}'

        self.validate_record()

    def make_breakout(self):

        html_out = []

        for label, data in {
            'Title': self.title,
            'Description': self.description,
            'Functional Category': self.functional_category,
            'Rule ID': self.id,
            'Impact of Violation': self.violation_impact,
            'Criticality': self.crit,
            'TOWER Implementation': self.tower_link,
            'ART Implementation': self.art_path,
            'Lessons Learned': self.lessons_learned_link,
            'Latest Vetted Rule Hash': self.rev,
            'Maturity': self.maturity,
            'Maturity Information': MATURITY_DEFINITIONS[self.maturity][0],
            'Rule Validity': MATURITY_DEFINITIONS[self.maturity][1],
            'Implementation Validity': MATURITY_DEFINITIONS[self.maturity][2],
        }.items():

            html_out.append(P([Strong(f'{label}: '), data]))

        return P(html_out).render()


class RuleDictionaryClient(Oco2InputClient):
    def __init__(self):
        super().__init__()
        self.filepath
        self.latest_hash_path
        self.repo_path

    def populate_rules_from_helix(self, helix_url):
        return

    def populate_rules_from_helix_xml(self, rulehub_xml):
        return

    def populate_rules_from_rulehub(self, rulehub_url):
        return

    def populate_rules_from_git_csv(self, rule_class):
        '''
        Requires rules to be in a CSV in git where the first
        column is the rule ID. This is used for understanding
        which lines go together in a rule because of the way
        git blame is formatted. If the CSV has line breaks in any
        cell, they will be reflected in the raw text version that
        git reads. Because of this, each individual line can have
        a different hash, and we have to check them all to find
        the newest for each rule.
        '''
        try:
            repo = git.Repo(self.repo_path)
            blame_output = repo.git.blame(self.filepath)
            columns = self.filepath.open('r').read().split('\n')[0].split(',')
            pattern = r"^([0-9a-f]{8})[^(]*\((\D*)\s*(\S*)\s*(\S*)\s*(\S*)\s*([^)]+)\)\s*(.*)"
            #            HASH            USER    DATE    TIME    TZ      LINE        CONTENTS
            rows = []
            for git_blame_line in blame_output.split('\n'):
                match = re.match(pattern, git_blame_line)
                if match:
                    rows.append({
                        'Hash': match.group(1),
                        'Author': match.group(2).strip(),
                        'Time': f'{match.group(3)} {match.group(4)} {match.group(5)}',
                        'Line': match.group(6),
                        'Rule ID': match.group(7).split(',')[0],
                        'Contents': match.group(7),
                        'Raw CSV Line': git_blame_line,
                        'Match': match
                        })                    
                else:
                    raise Exception('Bad regex!')
                
            # for row in rows:
            df = pd.DataFrame(rows)
            df['Time'] = pd.to_datetime(df['Time'], utc=True)
            last_rule_id = None
            rule_ids = []
            for rule_id in df['Rule ID']:
                match1 = re.match(r'\S*-\d*', rule_id)
                match2 = re.match(r'\S*-\S*-\d*', rule_id)
                if match1 is not None or match2 is not None:
                    last_rule_id = rule_id
                    rule_ids.append(rule_id)
                else:
                    rule_ids.append(last_rule_id)
            df['Rule ID'] = rule_ids

            latest_hashes = {}
            for rule_id in pd.unique(df['Rule ID']):
                if rule_id is None or pd.isna(rule_id): continue
                rows_this_rule = df[df['Rule ID'] == rule_id]
                latest_hashes[rule_id] = rows_this_rule[rows_this_rule['Time'] == max(rows_this_rule['Time'])].iloc[0]['Hash']
            try:
                json.dump(latest_hashes, open(self.latest_hash_path,'w'))
            except PermissionError:
                log.warning('Not writing rule hash. If you are running this in production, this is fine. TBD how to best make this warning go away.')
        except git.exc.InvalidGitRepositoryError:
            latest_hashes = json.load(open(self.latest_hash_path,'r'))

        self.records = pd.read_csv(self.filepath).fillna('').to_dict('records')
        self.rules = {r['Rule ID']: rule_class(r, latest_hashes) for r in self.records if r['Rule ID'] != ''}        

class RuleDictionaryClient(RuleDictionaryClient):
    # ===================================================================
    # :: Client Implementation
    # ===================================================================
    def _impl_init(self):
        self.filepath = Path(__file__).parent.parent.joinpath('support_files/rule_dictionary.csv')
        self.latest_hash_path = Path(__file__).parent.parent.joinpath('support_files/latest_rule_hashes.json')
        self.repo_path = Path(__file__).parent.parent.parent.parent
        self.defalt_time_label = None
        self.time_labels = []
        self.records = []
        
    def _impl_populate(self):
        self.populate_rules_from_git_csv(OCO2Rule)
        
    def _get_run_info(self):
        return {
            'Dictionary File Path': self.filepath,
            'Dictionary Git Commit': 'TBD'
        }





