#Python Imports
import pdb
from abc import ABC, abstractmethod
from datetime import datetime

#JPL Imports
from jpl_time import Time
from tts_html_utils.core.palette import EvrPalette

#This Library Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem
from tts_html_utils.core.components.base import HtmlComponent

class PipAuditItem(DataItem):
    DICT_VALID_KEYS = [
        ('Library', str), 
        ('Version', str), 
        ('Vulnerability URL', HtmlComponent), 
        ('ID', str), 
        ('Fix Versions', str),
        ('Severity', str),
        ]

    TIME_FORMATS = {
    }
    NAME = 'Pip Audit Vulnerability'

    @property
    def default_html_row_style(self):
        """Returns row styling based on the EVR severity level."""
        if self['Severity'] == 'CRITICAL':            
            return EvrPalette()['FATAL']
        elif self['Severity'] == 'HIGH':
            return EvrPalette()['WARNING_HI']
        elif self['Severity'] == 'MODERATE':
            return EvrPalette()['WARNING_LO']
        elif self['Severity'] == 'LOW':
            return EvrPalette()['ACTIVITY_HI']
        else:
            return EvrPalette()['FATAL']
    
    @property
    def time(self):
        return 

    @property
    def name(self):
        """The mnemonic identifier of the EVR."""
        return self.source['name']


class PipAuditContainer(DataContainer):
    NAME = 'Pip Audit'
    DATA_ITEM_CLS = PipAuditItem
    
    SEVERITY_ORDER = {
        'UNKNOWN': 0,
        'CRITICAL': 1,
        'HIGH': 2,
        'MODERATE': 3,
        'LOW': 4,
    }

    def _impl_init(self):
        """Internal initialization hook."""
        return

    @property
    def repr_cols(self):
        """Columns to be displayed in visual representations."""
        return self._repr_cols

    @property
    def default_time_label(self):
        """The default time field used for chronological operations."""
        return self._default_time_label
    
    def sort_by_severity(self, reverse=False):
        """
        Sort vulnerabilities by severity criticality.
        
        Orders by: CRITICAL > HIGH > MODERATE > LOW > UNKNOWN
        
        :param reverse: If True, sorts from least to most critical
        :type reverse: bool
        :return: A new sorted PipAuditContainer
        :rtype: PipAuditContainer
        """
        return self.sort(
            lam=lambda r: self.SEVERITY_ORDER.get(r['Severity'].upper(), -1),
            reverse=reverse
        )
