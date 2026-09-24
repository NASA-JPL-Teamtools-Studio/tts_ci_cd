#Python Imports
import logging
from pathlib import Path
import pdb
from datetime import datetime, timedelta
import uuid

#JPL Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem
from tts_data_utils.core.generic import GenericContainer
from tts_html_utils.visdiff.visdiff import VisualDiff
from tts_html_utils.core.components.text import H2

#This Library Imports
from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

class SwitchBufferItem(DataItem):
    DICT_VALID_KEYS = [
        ('Orbit', int),
        ('Station', str),
        ('Contact', str),
        ('AOS', datetime),
        ('LOS', datetime),
        ('AOS (NG)', datetime),
        ('LOS (NG)', datetime),
        ('Duration (NG)', str),
        ('Type', str),
        ('Start Time', datetime),
        ('Stop Time', datetime)
        ]

    TIME_FORMATS = {
        'Start Time': '%Y-%m-%dT%H:%M:%S.%fZ',
        'Stop Time': '%Y-%m-%dT%H:%M:%S.%fG',
    }

    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        return


class SwitchBufferClient(InputClient, DataContainer):
    NAME = 'Switch Buffer'
    DATA_ITEM_CLS = SwitchBufferItem


    def _impl_init(self, last_week_dir_client, week_dir_client, expanded_ats_client, last_expanded_ats_client):
        self.last_week_dir_client = last_week_dir_client
        self.week_dir_client = week_dir_client
        self.expanded_ats_client = expanded_ats_client        
        self.last_expanded_ats_client = last_expanded_ats_client        
        self.filepath = None
        self.defalt_time_label = None
        self.records = []
        self.time_labels = [
            {'name': 'Start Time', 'format': '%Y/%j %H:%M:%S'},
            {'name': 'Stop Time', 'format': '%Y/%j %H:%M:%S'}
        ]
        DataContainer.__init__(self)

    def _impl_populate(self):

        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*Switch_Buffer\.txt$')

        if self.filepath is None: 
            log.warning('Switch_Buffer.txt not found')
            return

        for line in open(self.filepath, 'r'): 
            line = line.strip()
            if line == '': continue
            orbit, station, start_time, stop_time, duration, x_or_s = line.split('\t')[:6]
            self.calculate_sbw(int(orbit), station, start_time, stop_time, duration, x_or_s)

    def calculate_sbw(self, orbit, station, ng_start_time, ng_stop_time, duration, x_or_s):
        if self.filepath is None: return

        #this is overly complex, but the way the code is currently written I think it needs to be.
        #Switch_Buffer.txt has at least some level of manual manipulation (or at least use to)
        #so we can't programatically assume that we can detect when it is telling use we have
        # a blind acq. Different files give "S-band blind acq", "S-Band blind acq", "S-Band blind acq.",
        #or just "S-band". So instead we just look for a max of 1 AOS/LOS record
        #if we find more than 1, we fail. If we find exactly 1, we take from the xats, if we find
        #none, we take from Switch_Buffer.txt.
        #and if we find one AOS and no LOS or vice versa, we fail
        aos_time = self.expanded_ats_client.eq('Orbit #', orbit).contains('command note', 'AOS at', maximum=1)
        los_time = self.expanded_ats_client.eq('Orbit #', orbit).contains('command note', 'LOS at', maximum=1)
        last_aos_time = self.last_expanded_ats_client.eq('Orbit #', orbit).contains('command note', 'AOS at', maximum=1)
        last_los_time = self.last_expanded_ats_client.eq('Orbit #', orbit).contains('command note', 'LOS at', maximum=1)

        if len(aos_time) == 0 and len(los_time) == 0:
            aos_time = datetime.strptime(ng_start_time, '%Y/%j %H:%M:%S')
            los_time = datetime.strptime(ng_stop_time, '%Y/%j %H:%M:%S')
        elif len(aos_time) == 0 or len(los_time) == 0:
            raise Exception(f'Only one of AOS and LOS found in xats on orbit {orbit}')
        else:
            aos_time = aos_time[0]['Time (UTC)']
            los_time = los_time[0]['Time (UTC)']
            last_aos_time = last_aos_time[0]['Time (UTC)']
            last_los_time = last_los_time[0]['Time (UTC)']
            #take the later of the two AOS times
            if aos_time < last_aos_time:
                aos_time = last_aos_time
            #take the earlier of the two LOS times
            if los_time > last_los_time:
                los_time = last_los_time

        ats_abs_records = self.expanded_ats_client.eq('Orbit #', orbit).isin('Event Type', ['ABS', 'ATS', 'LNR'])
        ats_abs_records += self.last_expanded_ats_client.eq('Orbit #', orbit).isin('Event Type', ['ABS', 'ATS', 'LNR'])
        # rts_8x_records = self.expanded_ats_client.eq('Orbit #', orbit).isin('Event Type', ['RTS #80', 'RTS #81'])
        #why is this commented out? We used to check all the RTS 80/1 commands in either ATS, but since we can't 
        #start this until RTS8x is done anyway, we'll ALWAYS be beholden to the old RTS8x time and not the new one.
        #(since RTS8x sets us up for X/S band comm). We used to append last week's thi this week's, but that was
        #getting some wrong answers sometimes, so we changed it.
        rts_8x_records = self.last_expanded_ats_client.eq('Orbit #', orbit).isin('Event Type', ['RTS #80', 'RTS #81'])

        #Ignore commands before AOS
        ats_abs_records = ats_abs_records.after(aos_time)
        rts_8x_records = rts_8x_records.after(aos_time)
        #Ignore commands after LOS
        ats_abs_records = ats_abs_records.before(los_time)
        rts_8x_records = rts_8x_records.before(los_time)
        #sort them to make sure last is really last in time
        rts_8x_records = rts_8x_records.sort()

        candidate_times = []
        if len(rts_8x_records):
            candidate_times.append(('NET', rts_8x_records[-1]['Time (UTC)'] + timedelta(seconds=10)))
        else:
            candidate_times.append(('NET', aos_time + timedelta(seconds=10)))
        candidate_times.append(('NLT', los_time - timedelta(seconds=30)))

        for ats_abs_record in ats_abs_records:
            candidate_times.append(('NET', ats_abs_record['Time (UTC)'] + timedelta(seconds=10)))
            candidate_times.append(('NLT', ats_abs_record['Time (UTC)'] - timedelta(seconds=15)))

        candidate_times = sorted(candidate_times, key=lambda x: x[1])

        candidate_windows = []
        
        for time_a, time_b in zip(candidate_times[:-1], candidate_times[1:]):
            if time_a[0] == 'NLT': continue
            if time_a[0] == time_b[0]: continue
            if (time_b[1] -  time_a[1]).total_seconds() < 60: continue            # SBWs cannnot be shorter than 1 min
            if (time_b[1] -  aos_time).total_seconds() < 120: continue            # SBWs cannot end wihin 2 min of AOS
            candidate_windows.append((time_a, time_b))

        for candidate_window in candidate_windows:
            record = {}
            record['Orbit'] = orbit
            record['Station'] = station
            record['Contact'] = f'{orbit} {station}'
            record['AOS'] = aos_time
            record['LOS'] = los_time
            record['AOS (NG)'] = datetime.strptime(ng_start_time, '%Y/%j %H:%M:%S')
            record['LOS (NG)'] = datetime.strptime(ng_stop_time, '%Y/%j %H:%M:%S')
            record['Duration (NG)'] = duration
            record['Type'] = x_or_s
            record['Start Time'] = candidate_window[0][1]
            record['Stop Time'] = candidate_window[1][1]
            self.append(record)

    def sbw_table(self, orbit, outtype='html', template=None):
            ats_table_records = self.expanded_ats_client.eq('Orbit #', orbit)
            last_ats_table_records = self.last_expanded_ats_client.eq('Orbit #', orbit)
            for sbw in self.eq('Orbit', orbit):
                gps_offset = ats_table_records[0]['Time (GPS)'] - ats_table_records[0]['Time (UTC)']
                #TO DO: This solution sucks. But I had do to it to get over a hump        
                last_ats_record = ats_table_records.before(sbw['Start Time'])[-1]
                sbw_start_record = {
                        'Line #': None,
                        'Orbit #': orbit, 
                        'Time (UTC)': sbw['Start Time'],
                        'Time (GPS)': sbw['Start Time'] + gps_offset, 
                        'Event Type': 'SBW',
                        'command': 'N/A', 
                        'command note': 'Switch Buffer Start', 
                        'ACS Mode': last_ats_record['ACS Mode'], 
                        'Instrument Mode': last_ats_record['Instrument Mode'], 
                        'Door Position': last_ats_record['Door Position'], 
                        'Lamp Status': last_ats_record['Lamp Status'], 
                        'in_sun': last_ats_record['in_sun'], 
                    }
                last_ats_record = ats_table_records.before(sbw['Stop Time'])[-1]
                sbw_stop_record = {
                        'Line #': None, 
                        'Orbit #': orbit, 
                        'Time (UTC)': sbw['Stop Time'],
                        'Time (GPS)': sbw['Stop Time'] + gps_offset,
                        'Event Type': 'SBW', 
                        'command': 'N/A', 
                        'command note': 'Switch Buffer Stop', 
                        'ACS Mode': last_ats_record['ACS Mode'],
                        'Instrument Mode': last_ats_record['Instrument Mode'],
                        'Door Position': last_ats_record['Door Position'],
                        'Lamp Status': last_ats_record['Lamp Status'],
                        'in_sun': last_ats_record['in_sun'],
                    }

                ats_table_records.append(sbw_start_record)
                ats_table_records.append(sbw_stop_record)
                last_ats_table_records.append(sbw_start_record)
                last_ats_table_records.append(sbw_stop_record)

            if sbw['Type'] == 'S-Band Blind Acq':
                last_ats_record = ats_table_records.before(sbw['AOS'])[-1]
                predicted_aos_record = {
                        'Line #': None, 
                        'Orbit #': orbit, 
                        'Time (UTC)': sbw['AOS'],
                        'Time (GPS)': sbw['AOS'] + gps_offset,
                        'Event Type': 'SBW', 
                        'command': 'N/A', 
                        'command note': 'Predicted AOS', 
                        'ACS Mode': last_ats_record['ACS Mode'],
                        'Instrument Mode': last_ats_record['Instrument Mode'],
                        'Door Position': last_ats_record['Door Position'],
                        'Lamp Status': last_ats_record['Lamp Status'],
                        'in_sun': last_ats_record['in_sun'],
                    }
                last_ats_record = ats_table_records.before(sbw['LOS'])[-1]
                predicted_los_record = {
                        'Line #': None, 
                        'Orbit #': orbit, 
                        'Time (UTC)': sbw['LOS'],
                        'Time (GPS)': sbw['LOS'] + gps_offset,
                        'Event Type': 'SBW', 
                        'command': 'N/A', 
                        'command note': 'Predicted LOS', 
                        'ACS Mode': last_ats_record['ACS Mode'], 
                        'Instrument Mode': last_ats_record['Instrument Mode'], 
                        'Door Position': last_ats_record['Door Position'], 
                        'Lamp Status': last_ats_record['Lamp Status'], 
                        'in_sun': last_ats_record['in_sun'], 
                    }

                ats_table_records.append(predicted_aos_record)                
                ats_table_records.append(predicted_los_record)
                last_ats_table_records.append(predicted_aos_record)
                last_ats_table_records.append(predicted_los_record)


            ats_table_records = ats_table_records.sort()
            last_ats_table_records = last_ats_table_records.sort()

            this_week_aos_record = ats_table_records.contains('command note', 'AOS at')
            this_week_los_record = ats_table_records.contains('command note', 'LOS at')
            this_week_aos = datetime(3000, 1, 1) if len(this_week_aos_record) == 0 else this_week_aos_record[0]['Time (UTC)']
            this_week_los = datetime(2000, 1, 1) if len(this_week_los_record) == 0 else this_week_los_record[0]['Time (UTC)']

            last_week_aos_record = last_ats_table_records.contains('command note', 'AOS at')
            last_week_los_record = last_ats_table_records.contains('command note', 'LOS at')
            last_week_aos = datetime(3000, 1, 1) if len(last_week_aos_record) == 0 else last_week_aos_record[0]['Time (UTC)']
            last_week_los = datetime(2000, 1, 1) if len(last_week_los_record) == 0 else last_week_los_record[0]['Time (UTC)']

            report_start_time = min(this_week_aos, last_week_aos, sbw['AOS'])
            report_end_time   = max(this_week_los, last_week_los, sbw['LOS'])

            records_during_contact = ats_table_records.between('Time (UTC)', report_start_time-timedelta(seconds=6), report_end_time+timedelta(seconds=6), inclusive='both')
            last_records_during_contact = last_ats_table_records.between('Time (UTC)', report_start_time-timedelta(seconds=6), report_end_time+timedelta(seconds=6), inclusive='both')

            this_table_id = str(uuid.uuid4()).replace('-','')

            sbw_styles = {
                # Started to add predicted AOS/LOS, but left them out in the end
                # 'Predicted AOS': {'background-color': 'dodgerblue'},
                # 'Predicted LOS': {'background-color': 'tomato'},
                'Switch Buffer Start': {'background-color': '2F4F4F', 'color': '#F0F0F0'},
                'Switch Buffer Stop': {'background-color': 'A9A9A9', 'color': '#2B2B2B'}
            }
            

            visdiff_left, visdiff_right = last_records_during_contact.visual_diff(records_during_contact, ignore_cols=['Line #'])
            left_row_styles = [sbw_styles.get(l['command note'], l.default_html_row_style) for l in visdiff_left]
            right_row_styles = [sbw_styles.get(r['command note'], r.default_html_row_style) for r in visdiff_right]
            power_table_left = visdiff_left.power_table(id=f'visdiff-left-{this_table_id}', row_styles=left_row_styles)
            power_table_right = visdiff_right.power_table(id=f'visdiff-right-{this_table_id}', row_styles=right_row_styles)
            
            time_diffs = []
            row_styles = []
            for time_l, time_r in zip(visdiff_left['Time (UTC)'], visdiff_right['Time (UTC)']):
                if time_l is not None and time_r is not None:
                    time_diff = (time_l - time_r).total_seconds()
                    time_diffs.append({'&Delta;t (UTC)': str(time_diff)})
                    if abs(time_diff) >= 5: 
                        row_styles.append({'background-color': '#FF614A', 'color': '#333333'})
                    else:
                        row_styles.append({})
                else:
                    time_diffs.append({'&Delta;t (UTC)': 'NA'})
                    row_styles.append({})

            sbw_tables = VisualDiff(
                power_table_left,
                power_table_right,
                left_label=H2(self.last_week_dir_client.planning_week),
                right_label=H2(self.week_dir_client.planning_week),
                uuid=this_table_id,
                overflow='synced_scroll'
                )

            time_diffs = GenericContainer(raw_data=time_diffs)
            time_diff_table = time_diffs.power_table(
                row_styles=row_styles,
                id=f'time-diff-{this_table_id}', 
                style={'width': '5%', 'float': 'left', 'margin-left': '2.5%'}
                )
            time_diff_table.add_header()
            sbw_tables.js_includes[0][1]['table_ids'].append(f'time-diff-{this_table_id}')

            #oof, this table structure is dumb... I probably could have done better, but if it's stupid and it works...
            sbw_tables.children[0].children[0].children.insert(1, H2('&Delta;t', style={'width': '5%', 'float': 'left', 'margin-left': '2.5%', 'color': 'white'}))
            sbw_tables.children[0].children[1].children.insert(1, time_diff_table)

            if outtype == 'html':
                return sbw_tables
            elif outtype == 'docx':
                records_during_contact._unlock()
                records_during_contact._repr_cols = [x for x in records_during_contact._repr_cols if x not in ['ACS Mode', 'Instrument Mode', 'Door Position', 'Lamp Status', 'in_sun']]
                records_during_contact._lock()
                return records_during_contact.docx_table(template=template)
            else:
                raise Exception(f'outtype of "{outtype}" is not recognized.')

    def _get_run_info(self):
        switch_buffer_contacts = list(set([f"{r['Orbit']} {r['Station']} {r['Type']}" for r in self]))
        return {
            'Prime Switch Buffer Contact': switch_buffer_contacts[0],
            'Secondary Switch Buffer Contact': switch_buffer_contacts[1],
            'Tertiary Switch Buffer Contact': switch_buffer_contacts[2] if len(switch_buffer_contacts) == 3 else 'None',
        }
