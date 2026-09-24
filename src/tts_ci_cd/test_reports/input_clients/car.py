import logging
from pathlib import Path
import pandas as pd
import pdb
from docx import Document
import re

from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

class CarClient(InputClient):
    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.filepath = None
        self.defalt_time_label = None
        self.time_labels = []

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*OCO2_CAR_ATS_.*\.docx')
        self.doc = Document(self.filepath)
        self.table = []

        previous_cell = None
        for table in self.doc.tables:
            for row in table.rows:
                this_row = []
                for cell in row.cells:
                    if cell.text != previous_cell:
                        this_row.append(cell.text)
                    previous_cell = cell.text

                self.table.append(this_row)

        try:
            car_no_match = re.search(r'CAR#: (\d*)$', self.table[1][1])
            buffer_match = re.search(r'Load ATS (A|B)', self.table[2][0])
        except IndexError:
            car_no_match = None
            buffer_match = None
            self.car_no = None
            self.buffer_name = None

        if car_no_match:
            self.car_no = int(car_no_match.group(1))
        else:
            self.car_no = None

        if buffer_match:
            self.buffer_name = buffer_match.group(1)
        else:
            self.buffer_name = None

    def _get_run_info(self):
        return {
            'Buffer': self.buffer_name,
            'CAR #': self.car_no
        }


