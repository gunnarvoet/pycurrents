'''
Classes and routines for reading raw RDI data files: BB, WH, OS, PN, and SV
(SentinelV).

The SV support is under development.  Missing features:
- The 0x7000-0x7004 IDs are not being parsed and stored.
- The 0x7003 ID, "Features Data", is not being added to the start of any
  chunk obtained or written by the extract_raw() function.
- The "Fixed Leader" can change within a file; it is not clear whether this
  will break something in the reader, given that it was written with the
  assumption that all Fixed Leader records are identical within a file, as
  was the case for all other instruments.  It looks like the fields that
  change are Bin1Dist and Pulse, presumably because soundspeed is being
  varied according to the measured temperature (and pressure?).  In read(),
  we are calculating a single "dep" array using values from the first
  FixedLeader.  We are recording the entire array of FixedLeaders, though,
  so the information needed to make a 2-D depth array is available in
  the ppd.raw['FixedLeader'] array.

'''

import copy
import struct

import numpy as np
import logging

from pycurrents import codas
from pycurrents.adcp import nbvel
from pycurrents.adcp.adcp_specs import Sonar


from pycurrents.adcp.raw_base import (
        Bunch,
        FileBase,
        make_ilist,
        IncompleteFileError,
        )


__all__ = [
    "FileBBWHOS",
    "FileNB",
    "instname_from_file",
]


# Standard logging
_log = logging.getLogger(__name__)


FixedLeader_length_dict = dict(bb=42, wh=59, os=50, sv=60, pn=65)

Data_ID_list = [('Header',          0x7F7F),
                ('FixedLeader',     0x0000),
                ('VariableLeader',  0x0080),
                ('Velocity',        0x0100),
                ('Correlation',     0x0200),
                ('Intensity',       0x0300),
                ('PercentGood',     0x0400),
                ('Status',          0x0500),
                ('BottomTrack',     0x0600),
                ('Navigation',      0x2000),
                ('FixedAttitude',   0x3000),
                ('Transformation',  0x3200),
                ('VBLeader',        0x0F01),
                ('VBVelocity',      0x0A00),
                ('VBCorrelation',   0x0B00),
                ('VBIntensity',     0x0C00),
                ('VBPercentGood',   0x0D00),
                 ]

# VariableAttitude--many possible IDs.
# Abbreviate as VAn, where n is the number of HPR groups
# in the message.
for i in [0x40, 0x44, 0x80, 0x84, 0xc0, 0xc4]:
    Data_ID_list.append(('VA0', i + 0x3000))

for i in [0x48, 0x4c, 0x50, 0x54, 0x60, 0x64,
            0x88, 0x8c, 0x90, 0x94, 0xa0, 0xa4]:
    Data_ID_list.append(('VA1', i + 0x3000))

for i in [0x58, 0x5c, 0x68, 0x6c, 0x70, 0x74,
          0x98, 0x9c, 0xa8, 0xac, 0xb0, 0xb4,
          0xc8, 0xcc, 0xd0, 0xd4, 0xe0, 0xe4]:
    Data_ID_list.append(('VA2', i + 0x3000))

for i in [0x78, 0x7c, 0xb8, 0xbc]:
    Data_ID_list.append(('VA3', i + 0x3000))

for i in [0xd8, 0xdc, 0xe8, 0xec, 0xf0, 0xf4]:
    Data_ID_list.append(('VA4', i + 0x3000))

for i in [0xf8, 0xfc]:
    Data_ID_list.append(('VA6', i + 0x3000))

_inverted_Data_ID_list = [(b,a) for (a,b) in Data_ID_list]

Data_ID_dict = dict(Data_ID_list)              # Name is the key
Data_Name_dict0 =  dict(_inverted_Data_ID_list) # ID is the key
Data_Name_dict = Data_Name_dict0.copy()
# For the OS, there can be two IDs for each array variable name:
for key, value in Data_Name_dict0.items():
    if key < 0x0600:
        Data_Name_dict[key+1] = value

# Fixed leader is essentially the same up through the first 42 bytes, which
# is the length of the BB FL, but the WH and OS have 60 bytes.  Only in the WH
# do some of the extra bytes have documented meaning.

BB_FL_layout = [#('ID', 'H'),
                ('FWV', 'B'),
                ('FWR', 'B'),
                ('SysCfg', 'H'),
                ('spare1', 'B'),
                ('spare2', 'B'),
                ('NBeams', 'B'),
                ('NCells', 'B'),
                ('NPings', 'H'),
                ('CellSize', 'H'),
                ('Blank', 'H'),
                ('SPM', 'B'),
                ('LowCorrThresh', 'B'),
                ('NCodeReps', 'B'),
                ('PGMin', 'B'),
                ('EVMax', 'H'),
                ('TPP_min', 'B'),
                ('TPP_sec', 'B'),
                ('TPP_hun', 'B'),
                ('EX', 'B'),
                ('EA', 'h'),
                ('EV', 'h'),
                ('EZ', 'B'),
                ('SA', 'B'),
                ('Bin1Dist', 'H'),
                ('Pulse', 'H'),
                ('RL0', 'B'),
                ('RL1', 'B'),
                ('WA', 'B'),
                ('spare3', 'B'),
                ('TransLag', 'H')]

WH_FL_layout = copy.deepcopy(BB_FL_layout)
# 2 of the BB spares are now used:
WH_FL_layout[3] = ('RealSimFlag', 'B')
WH_FL_layout[4] = ('LagLength', 'B')
WH_FL_layout.extend( [('CPU_SN', 'S8'),
                      ('WB', 'H'),
                      ('CQ', 'B'),
                      ('spare4', 'B'),
                      ('Inst_SN', 'S4'),
                      ('BeamAngle', 'B')])


SV_FL_layout = copy.deepcopy(WH_FL_layout)
SV_FL_layout.extend([('spare5', 'B'),])

OS_FL_layout = copy.deepcopy(BB_FL_layout)
PN_FL_layout = copy.deepcopy(SV_FL_layout)  # Check this!  Or start from BB.
PN_FL_layout.extend([('PingsPerEnsemble', 'H'),
                     ('Frequency', 'H'),
                     ('Frequency_MSB', 'B'),
                     ])

FL_layouts = {'bb': BB_FL_layout,
              'wh': WH_FL_layout,
              'sv': SV_FL_layout,
              'os': OS_FL_layout,
              'pn': PN_FL_layout,
}

base_VL_layout = [#('ID', 'H'),
                  ('EnsNum', 'H'),
                  ('Year', 'B'),
                  ('Month', 'B'),
                  ('Day', 'B'),
                  ('Hour', 'B'),
                  ('Minute', 'B'),
                  ('Second', 'B'),
                  ('Hundredths', 'B'),
                  ('EnsNumMSB', 'B'),
                  ('BIT', 'H'),
                  ('SoundSpeed', 'H'),
                  ('XducerDepth', 'H'),
                  ('Heading', 'H'),
                  ('Pitch', 'h'),
                  ('Roll', 'h'),
                  ('Salinity', 'H'),
                  ('Temperature', 'h'),
                  ('MPT_minutes', 'B'),
                  ('MPT_seconds', 'B'),
                  ('MPT_hundredths', 'B'),
                  ('HeadingStd', 'B'),
                  ('PitchStd', 'B'),
                  ('RollStd', 'B')]

OS_VL_layout = copy.deepcopy(base_VL_layout)
OS_VL_layout.extend([('reserved1', 'S8'),
                     ('ESW1', 'B'),
                     ('ESW2', 'B'),
                     ('ESW3', 'B'),
                     ('ESW4', 'B')])


PN_VL_layout = copy.deepcopy(base_VL_layout)
PN_VL_layout.extend([('reserved1', 'S8'),
                     ('ESW1', 'B'),
                     ('ESW2', 'B'),
                     ('ESW3', 'B'),
                     ('ESW4', 'B')])

BB_VL_layout = copy.deepcopy(base_VL_layout)
BB_VL_layout.extend([('ADC0', 'B'),
                     ('ADC1', 'B'),
                     ('ADC2', 'B'),
                     ('ADC3', 'B'),
                     ('ADC4', 'B'),
                     ('ADC5', 'B'),
                     ('ADC6', 'B'),
                     ('ADC7', 'B')])

WH_VL_layout = copy.deepcopy(BB_VL_layout)
WH_VL_layout.extend([('ESW', 'I'),
                     ('spare1', 'H'),
                     ('Pressure', 'i'),
                     ('PressureStd', 'I'),
                     ('spare2', 'B'),
                     ('RTCCentury', 'B'),
                     ('RTCYear', 'B'),
                     ('RTCMonth', 'B'),
                     ('RTCDay', 'B'),
                     ('RTCHour', 'B'),
                     ('RTCMinute', 'B'),
                     ('RTCSecond', 'B'),
                     ('RTCHundredths', 'B'),
                     ])

SV_VL_layout = copy.deepcopy(WH_VL_layout)
SV_VL_layout.extend([('spare5', 'B'),])

VL_layouts = {'bb': BB_VL_layout,
              'wh': WH_VL_layout,
              'sv': SV_VL_layout,
              'os': OS_VL_layout,
              'pn': PN_VL_layout,
}

BT_layout = [#('ID', 'H'),
             ('NPings', 'H'),
             ('pad1', 'H'),
             ('BC', 'B'),
             ('BA', 'B'),
             ('pad2', 'B'),
             ('BM', 'B'),
             ('BE', 'H'),
             ('pad3', 'I'),
             ('Range1', 'H'),
             ('Range2', 'H'),
             ('Range3', 'H'),
             ('Range4', 'H'),
             ('Vel1', 'h'),
             ('Vel2', 'h'),
             ('Vel3', 'h'),
             ('Vel4', 'h'),
             ('Cor1', 'B'),
             ('Cor2', 'B'),
             ('Cor3', 'B'),
             ('Cor4', 'B'),
             ('EvalAmp1', 'B'),
             ('EvalAmp2', 'B'),
             ('EvalAmp3', 'B'),
             ('EvalAmp4', 'B'),
             ('pad4', 'S30'),
             ('BX', 'H'),
             ('RSSIAmp1', 'B'),
             ('RSSIAmp2', 'B'),
             ('RSSIAmp3', 'B'),
             ('RSSIAmp4', 'B'),
             ('Gain', 'B'),
             ('RangeMSB1', 'B'),
             ('RangeMSB2', 'B'),
             ('RangeMSB3', 'B'),
             ('RangeMSB4', 'B')]

# If it becomes clear that there really are no differences, we
# can dispense with this dictionary.
BT_layouts = {'bb': BT_layout,
              'wh': BT_layout,
              'sv': BT_layout,
              'os': BT_layout,
              'pn': BT_layout,
}

## OS (or maybe also anything from VMDAS?) only:
##     FixedAttitude, VariableAttitude, Navigation

FA_layout = [#('ID', 'H'),
             ('EE', '8B'),
             ('EF', 'B'),
             ('EH', 'h'),
             ('EHy', 'B'),
             ('EI', 'h'),
             ('EJ', 'h'),
             ('EPx', 'h'),
             ('EPy', 'h'),
             ('EPz', 'B'),
             ('EU', 'B'),
             ('EV', 'h'),
             ('EZ', '8B')]

VA0_layout = [#('ID', 'H')
                ]
VA_layouts = {}
for i in [0, 1, 2, 3, 4, 6]:
    out = copy.copy(VA0_layout)
    for j in range(1, i+1):
        block = [('H%d'%j, 'h'),
                 ('P%d'%j, 'h'),
                 ('R%d'%j, 'h'),
                 ('Hr%d'%j, 'h'),
                 ('Pr%d'%j, 'h'),
                 ('Rr%d'%j, 'h'),
                 ]
        out.extend(block)
    VA_layouts[i] = out

Nav_layout = [#('ID', 'H'),
               ('UTCDay', 'B'),
               ('UTCMonth', 'B'),
               ('UTCYear', 'H'),
               ('UTC_T1', 'I'),    # 1e-4 s
               ('PC_UTC_ms', 'i'),
               ('Lat1_BAM4', 'i'),
               ('Lon1_BAM4', 'i'),
               ('UTC_T2', 'I'),    # 1e-4 s
               ('Lat2_BAM4', 'i'),
               ('Lon2_BAM4', 'i'),
               ('AvgSpeed_mms', 'h'), # Why is this listed as signed?  Is it?
               ('AvgTrackT_BAM2', 'h'),
               ('AvgTrackM_BAM2', 'h'),
               ('SMG_mms', 'h'),
               ('DMG_BAM2', 'h'),
               ('spare1', 'h'),
               ('Flags', 'H'),
               ('spare2', 'h'),
               ('EnsNum', 'I'),
               ('EnsYear', 'H'),
               ('EnsDay', 'B'),
               ('EnsMonth', 'B'),
               ('EnsTime', 'I'),  # 1e-4 s
               ('Pitch_BAM2', 'h'),
               ('Roll_BAM2', 'h'),
               ('Heading_BAM2', 'h'),
               ('NSpeed', 'H'),
               ('NTrackT', 'H'),
               ('NTrackM', 'H'),
               ('NHeading', 'H'),
               ('NPitchRoll', 'H'),
               ]

VBLeader_layout = [#('ID', 'H'),    sv Vertical Beam
                ('NCells', 'H'),
                ('NPings', 'H'),
                ('CellSize', 'H'),
                ('Bin1Dist', 'H'),
                ('Mode', 'H'),
                ('Pulse', 'H'),
                ('Lag', 'H'),
                ('NCode', 'H'),  # NCodeReps?
                ('RSSI_Threshold', 'H'),
                ('ShallowBin', 'H'),
                ('StartBin', 'H'),
                ('ShallowRSSIBin', 'H'),
                ('MaxCoreThreshold', 'H'),
                ('MinCoreThreshold', 'H'),
                ('PingOffsetTime', 'h'),
                ('Spare1', 'H'),
                ('DepthScreen', 'H'),
                ('PercentGoodThreshold', 'H'),
                ('PercentDOProofing', 'H'),
                ]

def dtype_from_layout(layout, endian='little'):
    L = []
    if endian == 'little':
        endiansym = '<'
    else:
        endiansym = '>'
    for item in layout:
        L.append((item[0], endiansym + item[1]))
    return np.dtype(L)


def trim_dtype(dt, layout, length):
    '''
    Chop fields off end of a dtype until it fits a given length.

    This is needed because different firmware versions for a given
    instrument use FixedLeader and VariableLeaders of different
    lengths.
    '''
    layout[:] = layout
    while dt.itemsize > length:
        layout = layout[:-1]
        dt = dtype_from_layout(layout)
    return dt


def make_dtype_dict(inst):
    d = {}
    d['FixedLeader'] = (dtype_from_layout(FL_layouts[inst]), 'struct')
    d['VariableLeader'] = (dtype_from_layout(VL_layouts[inst]), 'struct')
    d['Velocity'] = (np.dtype('<h'), 'array')
    d['Correlation'] = (np.dtype('B'), 'array')
    d['Intensity'] = (np.dtype('B'), 'array')
    d['PercentGood'] = (np.dtype('B'), 'array')
    d['Status'] = (np.dtype('B'), 'array')
    d['BottomTrack'] = (dtype_from_layout(BT_layouts[inst]), 'struct')
    # Navigation from VMDAS--probably for any instrument type
    d['Navigation'] =  (dtype_from_layout(Nav_layout), 'struct')
    # others for VMDAS?
    d['FixedAttitude'] = (dtype_from_layout(FA_layout), 'struct')
    for i in [0, 1, 2, 3, 4, 6]:
        d['VA%d'%(i,)] = (dtype_from_layout(VA_layouts[i]), 'struct')
    d['Transformation'] = (np.dtype([('matrix', '<h', (4,4))]), 'struct')
    d['VBLeader'] = (dtype_from_layout(VBLeader_layout), 'struct')  # sv
    d['VBVelocity'] = (np.dtype('<h'), 'array1')
    d['VBCorrelation'] = (np.dtype('B'), 'array1')
    d['VBIntensity'] = (np.dtype('B'), 'array1')
    d['VBPercentGood'] = (np.dtype('B'), 'array1')

    return d

dtype_dicts = {'bb': make_dtype_dict('bb'),
               'wh': make_dtype_dict('wh'),
               'os': make_dtype_dict('os'),
               'pn': make_dtype_dict('pn'),
               'sv': make_dtype_dict('sv'),}

class SysCfg(dict):
    """
    Decoder for BBWHOS SysCfg field in FixedLeader
    """
    _freq = int('111', 2)
    _convex = int('1000', 2)       #3
    _up = int('10000000', 2)       #7
    _angle = int('11', 2)         # mask in MSB
#    _freqs = [75, 150, 300, 600, 1200, 2400, 38]
    _angles = [15, 20, 30, 25]  # 25 is for SV

    def __init__(self, val):
        dict.__init__(self)
        self.__dict__ = self
        self.angle = self._angles[(val >> 8) & self._angle]
        # FIXME: Pinnacle doesn't seem to be behaving correctly here, in the
        # current sample in pycurrents_test_data (ADCP-Aldabra-W1_*):
        if self.angle == 0:
            self.angle = 20  # Assume Pinnacle data that doesn't match spec.
        if self.angle == 25:  # It's an SV
            _freqs = [0, 0, 300, 500, 1000, 0, 0]
        else:
            # FIXME: here we are using a nominal Pinnacle frequency of 45,
            # which probably should be 44.  Furthermore, the actual frequency
            # for the Pinnacle can be read from a different location in the FL.
            _freqs = [75, 150, 300, 600, 1200, 2400, 38, 45]
        self.kHz = _freqs[val & self._freq]
        self.convex = bool(val & self._convex)
        self.up = bool(val & self._up)


class CoordTrans(dict):
    """
    Decoder for BBWHOS EX field in FixedLeader
    """
    _coord = int('11000', 2) # 3
    _coords = ['beam', 'xyz', 'ship', 'earth']

    def __init__(self, val):
        dict.__init__(self)
        self.__dict__ = self
        self.coordsystem = self._coords[(self._coord & val) >> 3]
        self.tilts = bool(4 & val)
        self.threebeam = bool(2 & val)
        self.binmap = bool(1 & val)



class FileBBWHOS(FileBase):
    '''
    RDI raw data file reader.

    This is quite specialized, and instances should not be thought
    of as file-like objects.
    '''

    # All use the same header format.  It does not have a fixed
    # length, so it has to be read in two steps.

    class Header:
        def __init__(self):
            self.nbytes = None

        def read(self, fobj):
            '''
            Main effect is to set self.offsets, the list of offsets
            for all data types.
            '''
            part1 = fobj.read(6)
            if len(part1) != 6:
                raise IncompleteFileError('Header: found only %d bytes' %
                                            len(part1))
            tup = struct.unpack('<BBHxB', part1)
            if not (tup[0] == tup[1] == 0x7F):
                raise RuntimeError('first 6 bytes of header parse as %s'%str(tup))
            self.nbytes = tup[2] + 2 # Adding 2 for the checksum
            self.ndatatypes = tup[3]
            part2 = fobj.read(2*self.ndatatypes)
            if len(part2) != 2*self.ndatatypes:
                raise IncompleteFileError('Header: expected %d bytes, found %d' %
                                            (2*self.ndatatypes, len(part2)))
            self.offsets = struct.unpack('<' + 'H'*self.ndatatypes, part2)
            self.FLsize = self.offsets[1] - self.offsets[0] - 2
            self.VLsize = self.offsets[2] - self.offsets[1] - 2
            if self.FLsize < 40 or self.FLsize > 80:
                _log.warning("Fixed Leader size looks wrong;  "
                         "it is calculated as %d." % self.FLsize)
                # 40 looks like a reliable indicator of BB, but
                # after that it seems there can be sizes of 51, 57, 58,
                # or who knows what!


    def __init__(self, fname, sonar=None, trim=True, yearbase=None):
        self.offset_dict = {}
        self.varnames = {}
        self.bad_ID_list = []  # for unsupported IDs
        FileBase.__init__(self, fname, inst=None,  # Don't call open() yet.
                          trim=trim, yearbase=yearbase)
        if sonar is None:
            FileBase.open(self)  # reads the header
            ens = self.get_ens(0)
            self.close()
            FL_dtype = dtype_dicts['bb']['FixedLeader'][0]
            offset = 2 + self.header.offsets[0]
            FL = np.frombuffer(ens, dtype=FL_dtype, count=1, offset=offset)[0]
            sysconfig = SysCfg(FL['SysCfg'])
            freq = sysconfig['kHz']
            self.inst = self.inst_from_firmware_version(FL['FWV'])
            sonar = self.inst + str(freq)

        self.sonar = Sonar(sonar)
        self.dtype_dict = make_dtype_dict(self.sonar.model)
        self._ping_selected = False
        # The following calls self.open()
        FileBase.__init__(self, fname, inst=self.sonar.model,
                          trim=trim, yearbase=yearbase)
        self._missing_data_IDs = set()

    @staticmethod
    def inst_from_firmware_version(fwv):
        # Based on email from rdifs, 2023/01/17, 10:27 AM.
        if fwv < 6:
            return "bb"
        if fwv in (8, 16, 50, 51, 52, 77, 78):
            # 77, 78 are for "WHII".
            return "wh"
        if fwv in (14, 23, 59):
            return "os"
        if fwv in (47, 66):
            return "sv"
        if fwv == 61:
            return "pn"
        raise RuntimeError(f"Firmware version {fwv} is unknown")

    def open(self):
        '''
        Open the file for reading.  There are no arguments.

        This should be followed by a call to the trim() method
        if one is working with a static file from a self-contained
        instrument rather than one that is being accreted in real time.
        '''
        FileBase.open(self)
        if not self.opened:
            return
        FL_dtype = self.dtype_dict['FixedLeader'][0]
        FL_dtype = trim_dtype(FL_dtype, FL_layouts[self.inst],
                                    self.header.FLsize)
        self.dtype_dict['FixedLeader'] =  (FL_dtype, 'struct')
        VL_dtype = self.dtype_dict['VariableLeader'][0]
        VL_dtype = trim_dtype(VL_dtype, VL_layouts[self.inst],
                                    self.header.VLsize)
        self.dtype_dict['VariableLeader'] =  (VL_dtype, 'struct')

        ens = self.get_ens(0)

        self.IDs = []
        for offset in self.header.offsets:
            ID = struct.unpack('<H', ens[offset:offset+2])[0]
            # VMDAS bug: sometimes Navigation is missing, replaced by 0
            # (The first ID is always FixedLeader, which is 0.)
            if 0 in self.IDs and ID == 0:
                ID = Data_ID_dict['Navigation']  # 0x2000
            if ID in self.bad_ID_list:
                continue
            try:
                self.varnames[ID] = Data_Name_dict[ID]
            except KeyError:
                _log.warning("ID %s in file %s is not supported",
                            hex(ID), self.fname)
                self.bad_ID_list.append(ID)
                continue
            self.IDs.append(ID)
            self.offset_dict[ID] = offset
            if ID == 0x3000:
                b = ens[offset:]
                dtype = self.dtype_dict['FixedAttitude'][0]
                self.FA = np.frombuffer(b, dtype=dtype, count=1)[0]
        self.available_varnames = list(set(self.varnames.values()))
        self.available_varnames.sort()
        self.FLs = []
        self.ID_lsbs = []      # least significant bit, not byte
        self.FLs.append(np.frombuffer(ens[self.header.offsets[0]+2:],
                                    dtype=FL_dtype, count=1)[0])
        self.ID_lsbs.append(self.IDs[0])  # 0 or 1; first fixed leader
        if self.inst in ('os', 'pn'):
            if 0 in self.IDs[1:]:
                self.FLs.append(self._readvar(ens, 0))
                self.ID_lsbs.append(0)
            elif 1 in self.IDs[1:]:
                self.FLs.append(self._readvar(ens, 1))
                self.ID_lsbs.append(1)
        self.pingtypes = {}   #dict e.g. 'bb' -> index into FLs etc.
        self.dparamdicts = {}
        self.configs = []     # list of tuples that identify basic config
        self.includes_watertrack = False
        for ind, FL in enumerate(self.FLs):
            spm = 1 # This seems not to be set correctly by old instruments
            if self.inst in ('os', 'pn'):
                spm = FL['SPM']
            # As of 2022-08-20, the value "2" for "bb" seems to
            # be valid for the PN, contrary to the June 2022 docs.
            ping = {1:'bb', 2: 'bb', 10:'nb'}[spm]
            self.pingtypes[ping] = ind
            dp = self.decode_dparams(FL)
            if dp["NPings"] > 0:
                self.includes_watertrack = True
            self.dparamdicts[ping] = dp
            self.configs.append(self.configtuple(dp, ping))

        # Don't initialize this to the selected ping type, because
        # it may not exist--in which case Multiread fails.  Multiread
        # needs to know about the file, even if it is not going to
        # read it because it lacks the desired pingtype.
        if not self._ping_selected:
            self._select_ping() # to set FL, NCells, NBeams, pingtype

        IDVL = self.IDs_from_varlist()[0]
        VL = self._readvar(ens, IDVL)
        # Without "astype" the following would end up as a long.
        year = int(VL['Year'].astype(np.int64))
        if year > 80:
            year += 1900
        else:
            year += 2000
        if self.yearbase is None:
            self.yearbase = year
        dt_tup = (year, VL['Month'], VL['Day'],
                  VL['Hour'], VL['Minute'], VL['Second'])
        self.dtstr = "%04d/%02d/%02d %02d:%02d:%02d" % dt_tup
        self.sysconfig = SysCfg(FL['SysCfg'])
        self.sonar.frequency = self.sysconfig.kHz
        if 'VBLeader' in self.available_varnames:
            VBVL0 = self._readvar(ens, self.IDs_from_varlist(['VBLeader'])[0])
            self.VBNCells = VBVL0['NCells']
        self.opened = True

    def refresh_nprofs(self):
        if self.inst == 'sv':
            self.find_starts_and_lengths()
            self.nprofs = len(self.starts)
        else:
            FileBase.refresh_nprofs(self)

    def find_starts_and_lengths(self):
        if not hasattr(self, 'starts'):
            self.starts = []
            self.lengths = []
            ii = 0
        else:
            ii = self.starts[-1] + self.lengths[-1]
        while True:
            self.fobj.seek(ii)
            try:
                ID, length = np.fromfile(self.fobj, dtype=np.uint16, count=2)
            except ValueError:
                break
            if ID != 0x7f7f:
                break
            length += 2  # for checksum
            self.starts.append(ii)
            self.lengths.append(length)
            ii += length
        self.fobj.seek(0)

    def get_offset_dict(self, ens):
        # With SentinelV, it can vary within a file, so we get it each time.
        od = {}
        ndatatypes = struct.unpack('B', ens[5:6])[0]
        offsets = struct.unpack('<' + 'H'*ndatatypes, ens[6:6+2*ndatatypes])
        for offset in offsets:
            ID = struct.unpack('<H', ens[offset:offset+2])[0]
            od[ID] = offset
        return od

    def _select_ping(self, ping=None):
        if ping is None:
            ind = 0
        elif ping in ['bb', 'nb']:
            ind = self.pingtypes[ping]
        else:
            ind = ping  # so 0 or 1 for first or second set
        self.FL = self.FLs[ind]
        self.pingtype = 'bb' # for old instruments that don't set SPM correctly
        if self.inst in ('os', 'pn'):
            # As of 2022-08-20, the value "2" for "bb" seems to
            # be valid for the PN, contrary to the June 2022 docs.
            self.pingtype = {1:'bb', 2: 'bb', 10:'nb'}[self.FL['SPM']]
        self.ID_lsb = self.ID_lsbs[ind]

        dp = self.dparamdicts[self.pingtype]
        for k in dp:
            self.__setattr__(k, dp[k])

    @staticmethod
    def decode_dparams(FL):
        dp = dict()
        dp['NCells'] = int(FL['NCells'])
        dp['NBeams'] = int(FL['NBeams'])
        dp['NPings'] = int(FL['NPings'])
        dp['CellSize'] = float(FL['CellSize']) * 0.01
        dp['Pulse'] = float(FL['Pulse']) * 0.01
        dp['Blank'] = float(FL['Blank']) * 0.01
        dp['Bin1Dist'] = float(FL['Bin1Dist']) * 0.01
        dp['depth_interval'] = dp['CellSize']
        return dp


    def select_ping(self, ping=None):
        '''
        Pick the ping type ('nb' or 'bb') for the next read operation.

            None : (default) first set of entries in the offset table
            0    : same as above
            1    : second set in offset table, if present
            'nb' : nb ping, if present
            'bb' : bb ping, if present

        If a requested ping type is not present, it will raise
        IndexError or KeyError.  To find out what ping types
        are present in an instance 'f' of the class, see
        f.pingtypes.keys().

        This is effective only for Ocean Surveyor-type data.
        '''

        if self.inst not in ('os', 'pn'):
            return
        self._select_ping(ping)
        self._ping_selected = True


    def IDs_from_varlist(self, varlist=None):
        if varlist is None:
            varlist = ['VariableLeader']
        if varlist != 'all':
            if not set(varlist).issubset(set(self.dtype_dict.keys())):
                raise ValueError(
                    "varlist %s must be None, 'all', or subset of:\n  %s" % (varlist,
                                            self.available_varnames))
        IDlist = []
        for ID in self.offset_dict.keys():
            if varlist == 'all' or self.varnames[ID] in varlist:
                if ID >= 0x0600:
                    IDlist.append(ID)
                elif (ID & 1) == self.ID_lsb:
                    IDlist.append(ID)
        return IDlist

    def trim(self):
        '''
        Remove junk from end of file.

        It seems the Workhorse, at least, sometimes yields
        a file in which the last few records have the right structure
        but are otherwise filled with junk.  This method does a
        sanity check at the end of the file and backs up the
        nprofs attribute until things look reasonable.

        Presently, the reasonableness runs backwards from the
        end, looking for the point where the difference between
        the current ensemble number and the next earlier one is
        unity.  This permits gaps in ensemble number, such as
        those that occur when an LADCP profile is broken into
        two files and glued back together.
        '''
        varlist = ['VariableLeader']
        ID = Data_ID_dict['VariableLeader'] + self.ID_lsb
        ok = False
        for ii in range(self.nprofs-1, 0, -1):
            vl1 = self.readprof(ii, varlist)[ID]
            ens1 = (vl1['EnsNum'].astype(np.uint)
                        + vl1['EnsNumMSB'].astype(np.uint)*65536)
            vl0 = self.readprof(ii-1, varlist)[ID]
            ens0 = (vl0['EnsNum'].astype(np.uint)
                        + vl0['EnsNumMSB'].astype(np.uint)*65536)
            if ens1 - ens0 == 1:
                ok = True
                break
        if not ok:
            ii = -1  # Can't find 2 consecutive, so all are judged bad.
        self.nbadend = self.nprofs - ii -1
        self.nprofs = ii + 1

    def scan_checksums(self):
        """
        Check all checksums.
        Sets a chesksum_mask that is True where a checksum fails.
        Returns the count of bad checksums.
        """
        mask = np.zeros((self.nprofs,), dtype=bool)
        for ind in range(self.nprofs):
            ens = np.frombuffer(self.get_ens(ind), dtype=np.uint8)
            cs = ens[:-2].sum(dtype=np.uint32) % 65536
            target = 256 * ens[-1].astype(np.uint16) + ens[-2]
            if target != cs:
                mask[ind] = 1
        self.checksum_mask = mask
        return mask.sum()

    def write_clean_file(self, fname):
        """
        Write out the current file, omitting ensembles that fail the checksum.
        """
        self.scan_checksums()
        igood = np.nonzero(~self.checksum_mask)[0]
        with open(fname, 'wb') as outf:
            for i in igood:
                ens = self.get_ens(i)
                outf.write(ens)


    def _readvar(self, ens, ID):
        name = self.varnames[ID]
        dtype, kind = self.dtype_dict[name]
        if self.inst == 'sv':
            offset_dict = self.get_offset_dict(ens)
            # (FIXME: inefficient to do it for each variable...)
        else:
            offset_dict = self.offset_dict
        b = ens[offset_dict[ID]+2:]
        if kind == 'struct':
            var = np.frombuffer(b, dtype=dtype, count=1)[0]
        elif kind == 'array1':  # sv vertical beam
            nelem = self.VBNCells
            var = np.frombuffer(b, dtype=dtype, count=nelem)
        else:
            try:
                nelem = self.NCells * self.NBeams
                var = np.frombuffer(b, dtype=dtype, count=nelem)
                var.shape = self.NCells, self.NBeams
            except ValueError:   # some bad old VMDAS ENR files...
                var = np.zeros((self.NCells, self.NBeams), dtype=dtype)
                if ID not in self._missing_data_IDs:
                    _log.warning("Warning: Missing data for %s",
                             self.varnames[ID])
                    self._missing_data_IDs.add(ID)
        return var

    def readprof(self, ind=0, varlist=None, ping=None):
        if ping is not None:
            self.select_ping(ping)
        if ind < 0:
            ind += self.nprofs
        IDlist = self.IDs_from_varlist(varlist)
        ens = self.get_ens(ind)
        pd = Bunch()
        for ID in IDlist:
            pd[ID] = self._readvar(ens, ID)
        return pd


    def readprofs(self, start=0, stop=None, step=1, ilist=None, ends=None,
                        varlist=None, ping = None):
        if ping is not None:
            self.select_ping(ping)

        ilist = make_ilist(self.nprofs, start=start, stop=stop, step=step,
                                                    ilist=ilist, ends=ends)
        nprofs = len(ilist)
        self.nsamples = nprofs
        IDlist = self.IDs_from_varlist(varlist)
        pd = Bunch()
        for ID in IDlist:
            varname = self.varnames[ID]
            dtype, kind = self.dtype_dict[varname]
            if kind == 'struct':
                var = np.empty((nprofs,), dtype=dtype)
            elif kind == 'array1':  # sv vertical beam
                var = np.empty((nprofs, self.VBNCells), dtype=dtype)
            else:
                var = np.empty((nprofs, self.NCells, self.NBeams), dtype=dtype)
            pd[varname] = var
        for ii, ind in enumerate(ilist):
            ens = self.get_ens(ind)
            for ID in IDlist:
                varname = self.varnames[ID]
                pd[varname][ii] = self._readvar(ens, ID)
            pd['ilist'] = ilist
        return pd

    def decode_BT(self, bt):
        # We could add a kwarg to specify additional variables
        # to be passed on, but maybe this will be enough.
        nprofs = bt.shape[0]
        vel = np.ma.zeros((nprofs, 4), float)
        depth = np.ma.zeros((nprofs, 4), float)
        for i, v in enumerate(['Vel1', 'Vel2', 'Vel3', 'Vel4']):
            vel[:,i] = np.ma.masked_equal(bt[v], -32768)
        for i in range(4):
            ii = i+1
            depth[:,i] = np.ma.masked_equal((bt['RangeMSB%d' % ii] * 65536.0
                                                     + bt['Range%d' % ii]), 0)
        vel *= 0.001 # mm per s to m per s
        depth *= 0.01 # cm to meters
        return vel, depth

    def read(self, start=0, stop=None, step=1, ilist=None, ends=None,
                        varlist='all', ping = None):
        """
        Read a sequence of ping records.

        Parameters
        ----------
        start, stop, step : int or None
            Slice parameters for specifying the pings to extract.
        ilist : list of positive integers
            Alternative method for specifying the pings to extract.
        ends : int or None
            Extract just the first and last *ends* pings from the sequence
            remaining after slicing or selecting via the *ilist*.
        varlist : 'all' or sequence of strings
            List the variables to be extracted. FixedLeader, VariableLeader,
            and VBLeader (if VB variables are in the list) are included
            automatically and may be omitted from the list.
        ping : ['nb' | 'bb' | None]
            Ping type to be extracted (only valid for OS data).

        Returns
        -------
        ppd : Bunch
            ndarrays with requested variables in conventional units,
            and an attribute `raw` that is a Bunch with the unaltered
            arrays, directly as read from the file.

        """
        if varlist != 'all':
            vl = list(varlist)
            if 'FixedLeader' not in vl:
                vl.append('FixedLeader')
            if 'VariableLeader' not in vl:
                vl.append('VariableLeader')
            vbvars = [name for name in vl if name.startswith('VB')]
            if vbvars and 'VBLeader' not in vbvars:
                vl.append('VBLeader')
            varlist = vl
        pd = self.readprofs(start=start, stop=stop, step=step, ilist=ilist,
                            ends=ends, varlist=varlist, ping=ping)
        ppd = Bunch(sonar=self.sonar)  # to be returned full of goodies
        # retain access to everything in original form:
        ppd.raw = pd

        ppd.FL = Bunch.from_structured(pd.FixedLeader)
        for attr in ['NPings', 'NCells', 'NBeams', 'CellSize',
                      'Pulse', 'Blank', 'Bin1Dist', 'depth_interval']:
            ppd[attr] = self.__getattribute__(attr)

        # For LTA and STA, we need NPings from each FixedLeader.
        ppd.num_pings = pd['FixedLeader']['NPings']
        ppd.sysconfig = SysCfg(ppd.FL.SysCfg)
        ppd.trans = CoordTrans(ppd.FL.EX)

        ppd.dep = np.arange(ppd.NCells) * ppd.depth_interval + ppd.Bin1Dist

        ppd.VL = pd['VariableLeader']
        # experimental alternative or supplement:
        ppd.rVL = ppd.VL.view(np.recarray)
        VL = ppd.VL
        year = VL['Year'].astype(np.int16)
        year[year > 80] += 1900
        year[year <= 80] += 2000
        ppd.dday = codas.to_day(self.yearbase,
                                    year, VL['Month'], VL['Day'],
                                    VL['Hour'], VL['Minute'], VL['Second'])
        ppd.dday += VL['Hundredths'] / 8640000.0
        ppd.ens_num = VL['EnsNum'] + VL['EnsNumMSB'].astype(np.int64)*65536
        ppd.temperature = VL['Temperature'].astype(float) * 0.01
        ppd.heading = VL['Heading'].astype(float) * 0.01
        ppd.pitch = VL['Pitch'].astype(float) * 0.01
        ppd.roll = VL['Roll'].astype(float) * 0.01
        ppd.XducerDepth  = VL['XducerDepth'].astype(float) * 0.1

        if 'Velocity' in pd:
            ppd.vel = np.ma.masked_equal(pd['Velocity'], -32768).astype(float)
            ppd.vel /= 1000.0  # mm/s to m/s
            ppd.split('vel')
        if 'VBVelocity' in pd:
            ppd.vbvel = np.ma.masked_equal(pd['VBVelocity'], -32768).astype(float)
            ppd.vbvel /= 1000.0  # mm/s to m/s
        for name in ('VBIntensity', 'VBCorrelation', 'VBPercentGood'):
            if name in pd:
                ppd[name] = pd[name]
        if 'Intensity' in pd:
            ppd.amp = pd['Intensity']
            ppd.split('amp')
        if 'Correlation' in pd:
            ppd.cor = pd['Correlation']
            ppd.split('cor')
        if 'BottomTrack' in pd:
            ppd.bt_vel, ppd.bt_depth = self.decode_BT(pd['BottomTrack'])
        elif 'BottomTrack' in varlist or varlist == 'all':
            ppd.bt_vel = np.ma.zeros((self.nsamples, self.NBeams), dtype=float)
            ppd.bt_vel.mask = True
            ppd.bt_depth = ppd.bt_vel.copy()
        if 'Navigation' in pd:
            nav = Navigation(pd['Navigation'], ppd.dday)
            ppd.nav_start_txy = nav.txy1
            ppd.nav_end_txy = nav.txy2
            ppd.nav_heading = nav.heading
            ppd.nav_PC_minus_UTC = nav.PC_minus_UTC
            ppd.rawnav = nav.nav
        if 'PercentGood' in pd:
            ppd.pg = pd['PercentGood']
            ppd.split('pg')
        if 'Transformation' in pd:
            ppd.trans_matrix = pd['Transformation']['matrix'] * 1e-4
        return ppd

class Navigation:
    """
    Parser for the VMDAS Navigation structure
    """
    updated = 1
    PSN_valid = 1 << 1
    DateTime_valid = 1 << 5
    heading_valid = 1 << 8
    ADCP_time_valid  = 1 << 9
    ClockOffset_valid = 1 << 10

    def __init__(self, nav, dday, yearbase=None):
        self.nav = nav
        self.n = len(nav)
        if yearbase is None:
            if self.n > 0:
                self.yearbase = nav['UTCYear'][0]
        if self.n > 0:
            self.dday = dday
            self.dday_base = np.floor(dday)
            self.dday_frac = dday - self.dday_base
            # VMDAS: nav['EnsDay'] etc. seem to be unreliable,
            # so we use time from the Variable Leader to get
            # the date for the fix times.
        self._txy1 = None
        self._txy2 = None
        self._PC_minus_UTC = None
        self._heading = None
        self._flags = None
        self._fixmask = None

    def get_flags(self):
        if self._flags is None:
            self._flags = self.nav['Flags']
        return self._flags

    flags = property(get_flags)

    def get_fixmask(self):
        if self._fixmask is None:
            good = np.logical_and((self.flags & self.updated),
                                    (self.flags & self.PSN_valid))
            self._fixmask = np.logical_not(good)
        return self._fixmask

    fixmask = property(get_fixmask)

    def get_txy1(self):
        if self._txy1 is None:
            self._txy1 = np.ma.zeros((self.n, 3), np.float64)
            t1d = self.nav['UTC_T1'] / 864000000.0
            dayfix = np.round(self.dday_frac - t1d)
            self._txy1[:,0] = self.dday_base + t1d + dayfix

            self._txy1[:,1] = self.BAM4_to_degrees(self.nav['Lon1_BAM4'])
            self._txy1[:,2] = self.BAM4_to_degrees(self.nav['Lat1_BAM4'])
            self._txy1[self.fixmask] = np.ma.masked
        return self._txy1

    txy1 = property(fget=get_txy1)

    def get_txy2(self):
        if self._txy2 is None:
            self._txy2 = np.ma.zeros((self.n, 3), np.float64)
            t2d = self.nav['UTC_T2'] / 864000000.0
            dayfix = np.round(self.dday_frac - t2d)
            self._txy2[:,0] = self.dday_base + t2d + dayfix

            self._txy2[:,1] = self.BAM4_to_degrees(self.nav['Lon2_BAM4'])
            self._txy2[:,2] = self.BAM4_to_degrees(self.nav['Lat2_BAM4'])
            self._txy2[self.fixmask] = np.ma.masked
        return self._txy2

    txy2 = property(fget=get_txy2)

    def get_PC_minus_UTC(self):
        if self._PC_minus_UTC is None:
            mask = np.logical_not(self.flags & self.ClockOffset_valid)
            self._PC_minus_UTC = np.ma.array(1e-3 * self.nav['PC_UTC_ms'],
                                             mask = mask)
        return self._PC_minus_UTC

    PC_minus_UTC = property(fget=get_PC_minus_UTC)

    def get_heading(self):
        if self._heading is None:
            mask = np.logical_not(self.flags & self.heading_valid)
            self._heading = np.ma.array(self.BAM2_to_degrees(
                                             self.nav['Heading_BAM2']),
                                             mask=mask)
        return self._heading

    heading = property(fget=get_heading)

    @staticmethod
    def BAM2_to_degrees(bam):
        return bam * (180.0 / (2**15))

    @staticmethod
    def BAM4_to_degrees(bam):
        return bam * (180.0 / (2**31))

class FileNB(FileBase):
    variables = ['Leader', 'Velocity', 'SpectralWidth',
                 'Intensity', 'PercentGood', 'Status']
    vname_to_ind = {}
    ind_to_vname = {}
    for i, var in enumerate(variables):
        vname_to_ind[var] = i
        ind_to_vname[i] = var
    LeaderLayout = [
                    ('Month', 'B'),  # RTC fields are in BCD
                    ('Day', 'B'),
                    ('Hour', 'B'),
                    ('Minute', 'B'),
                    ('Second', 'B'),
                    ('TPP_min', 'B'), # also BCD
                    ('TPP_sec', 'B'),
                    ('TPP_hun', 'B'),
                    ('NPings', 'H'),
                    ('NCells', 'B'),
                    ('CellSize', 'B'),
                    ('Pulse', 'B'),
                    ('Blank', 'B'),
                    ('Delay', 'B'),
                    ('EnsNum', 'H'),
                    ('BIT', 'B'),
                    ('Config', 'B'),
                    ('SN_min', 'B'),
                    ('PG_min', 'B'),
                    ('Pitch', 'h'),
                    ('Roll', 'h'),
                    ('Heading', 'h'),
                    ('Temperature', 'H'), # -5 + (50*val/4096)  (?)
                    ('HVI', 'B'),
                    ('XMT', 'B'),
                    ('LVI', 'B'),
                    ('CTD_C', '3B'),
                    ('CTD_T', '3B'),
                    ('CTD_D', '3B'),
                    ('BT_Vel', '6B'),   # has to be unpacked
                    ('BT_Range', '4H'),
                    ('PitchStd', 'B'),
                    ('RollStd', 'B'),
                    ('HeadingStd', 'B'),
                    ('CTDMI', '3B'),     # 24-bit number
                    ('BT_PG', '2B'),     # 4 nibbles
                   ]

    dtypes = [(dtype_from_layout(LeaderLayout, 'big'), 'struct'),
              (np.int16, 'velocity'),
              (np.uint8, 'array'),         # SW
              (np.uint8, 'array'),         # Amp
              (np.uint8, 'array'),         # PG
              (np.uint8, 'status')]        # We usually ignore it.

    dtype_dict = dict(zip(variables, dtypes))

    class Header:
        def __init__(self):
            self.nbytes = None

        def read(self, fobj):
            '''
            Main effect is to set self.offsets, the list of offsets
            for all data types.
            '''
            hd = fobj.read(14)
            if len(hd) != 14:
                raise IncompleteFileError('Header: found only %d bytes' %
                                            len(hd))
            (nb, nL, nV, nSW, nA, nPG, nS) = struct.unpack('>7H', hd)
            self.nbytes = nb + 2  # 2 for the checksum
            sizes = np.array([14, nL, nV, nSW, nA, nPG, nS], dtype=np.int16)
            offsets = np.cumsum(sizes)[:-1]
            self.sizes = sizes[1:]
            self.offsets = offsets
            self.ndatatypes = (self.sizes > 0).sum()

    class SysCfg(dict):
        """
        Decoder for part of Config field in Leader
        """
        _freq = int('1110000', 2)
        _convex = int('1000', 2)       #3
        _up = int('100', 2)            #2
        _freqs = [75, 150, 300, 600, 1200, 115, 9999]

        def __init__(self, val):
            dict.__init__(self)
            self.__dict__ = self
            self.kHz = self._freqs[(val & self._freq) >> 4 ]
            self.angle = 30
            self.convex = not bool(val & self._convex)
            self.up = not bool(val & self._up)

    class CoordTrans(dict):
        """
        Decoder for remaining part of Config field in Leader,
        plus hardwired fields for compat with OS etc.
        """
        _velrange = 1
        _velranges = ['low', 'high']
        _coord = int('10', 2) # 3
        _coords = ['beam', 'earth']

        def __init__(self, val):
            dict.__init__(self)
            self.__dict__ = self
            self.velrange = self._velranges[self._velrange & val]
            self.coordsystem =  self._coords[(self._coord & val) >> 1]
            self.tilts = False
            self.threebeam = False
            self.binmap = False



    def __init__(self, fname, yearbase):
        FileBase.__init__(self, fname, 'nb', yearbase=yearbase)
        self.sonar = Sonar('nb')
        self.sonar.set_frequency(self.sysconfig.kHz)

    def open(self):
        FileBase.open(self)
        if not self.opened:
            return
        self.offsets = self.header.offsets
        self.available_varnames = [name for i, name in enumerate(self.variables)
                                    if self.header.sizes[i]]
        ens = self.get_ens(0)
        leader = self._readvar(ens, 'Leader')
        # Note: this leader requires lots of decoding.
        # Conversion of the BCD in the first 8 bytes is being done by _readvar.
        dt_tup = (self.yearbase, leader['Month'], leader['Day'],
                  leader['Hour'], leader['Minute'], leader['Second'])
        self.dtstr = "%04d/%02d/%02d %02d:%02d:%02d" % dt_tup
        self.leader = leader

        trans = self.CoordTrans(leader['Config'][0])
        sysconf = self.SysCfg(leader['Config'][0])
        self.sysconfig = sysconf
        if trans.coordsystem == 'beam':
            self.velscale = 2.5e-3
        else:
            self.velscale = 5.0e-3
        if trans.velrange == 'low' and sysconf.kHz != 75:
            self.velscale *= 0.5

        dp = self.decode_dparams(leader)
        self.includes_watertrack = dp["NPings"] > 0
        self.configs = [self.configtuple(dp)]  # list for consistency w. OS
        for k, v in dp.items():
            self.__setattr__(k, v)


    @staticmethod
    def decode_dparams(leader):
        dp = dict()
        dp['NCells'] = int(leader['NCells'])
        dp['NBeams'] = 4
        dp['NPings'] = int(leader['NPings'])
        dp['CellSize'] = 2.0**float(leader['CellSize'])
        dp['Pulse'] = float(leader['Pulse'])
        dp['Blank'] = float(leader['Blank'])
        dp['Bin1Dist'] = dp['Blank'] + 0.5 * (dp['Pulse'] + dp['CellSize'])
        dp['depth_interval'] = dp['CellSize']
        return dp


    def vnames_from_varlist(self, varlist=None):
        if varlist is None:
            return ['Leader']
        if varlist == 'all':
            return self.available_varnames
        for n in varlist:
            if n not in self.available_varnames:
                raise ValueError(
                    "Variable %s is not among available vars:\n  %s" % (n,
                                            self.available_varnames))
        if 'Leader' not in varlist:
            varlist.append('Leader')
        return varlist

    def _readvar(self, ens, varname):
        ID = self.vname_to_ind[varname]
        dtype, kind = self.dtypes[ID]
        b = ens[self.offsets[ID]:]
        if kind == 'struct':   # must be leader
            var = np.frombuffer(b, dtype=dtype, count=1)
            nbvel.unpack_leader_BCD(var) # unpacks first 8 bytes in place
        elif kind == 'array':
            var = np.frombuffer(b, dtype=dtype,
                                    count=self.NCells*self.NBeams)
            var.shape = self.NCells, self.NBeams
        elif kind == 'velocity':
            _var = np.frombuffer(b, dtype=np.uint8,
                                    count = self.NCells*6)
            #_var = b[:self.NCells*6]
            # TODO: Change unpack_vel interface, in anticipation of
            # Python 3 distinction between strings and byte sequences.
            var = nbvel.unpack_vel(_var, self.NCells)
        else:
            # Just return raw status, 2 bytes per depth cell.
            var = np.frombuffer(b, dtype=dtype,
                                    count=self.NCells*2)
            var.shape = self.NCells, 2
        return var



    def readprof(self, ind=0, varlist=None):
        if ind < 0:
            ind += self.nprofs
        vnames = self.vnames_from_varlist(varlist)
        self.fobj.seek(ind*self.header.nbytes)
        ens = self.fobj.read(self.header.nbytes)
        pd = Bunch()
        for var in vnames:
            pd[var] = self._readvar(ens, var)
        return pd


    def readprofs(self, start=0, stop=None, step=1, ilist=None, ends=None,
                        varlist=None):

        ilist = make_ilist(self.nprofs, start=start, stop=stop, step=step,
                                                    ilist=ilist, ends=ends)
        nprofs = len(ilist)
        self.nsamples = nprofs
        vnames = self.vnames_from_varlist(varlist)
        pd = Bunch()
        for varname in vnames:
            dtype, kind = self.dtype_dict[varname]
            if kind == 'struct':
                var = np.empty((nprofs,), dtype=dtype)
            elif kind == 'velocity' or kind == 'array':
                var = np.empty((nprofs, self.NCells, self.NBeams), dtype=dtype)
            elif kind == 'status':
                var = np.empty((nprofs, self.NCells, 2), dtype=dtype)
            else:
                raise ValueError("unrecognized variable: %s" % varname)
            pd[varname] = var
        for ii, ind in enumerate(ilist):
            self.fobj.seek(ind*self.header.nbytes)
            ens = self.fobj.read(self.header.nbytes)
            for varname in vnames:
                pd[varname][ii] = self._readvar(ens, varname)
            pd['ilist'] = ilist
        return pd

    def read(self, **kw):
        kw.setdefault('varlist', 'all')
        pd = self.readprofs(**kw)
        ppd = Bunch(sonar=self.sonar)  # to be returned full of goodies
        # retain access to everything in original form?
        ppd.raw = pd
        # Keep the "VL" term from BB?
        # Probably need one more stage of decoding
        # and regularizing.
        ppd.VL = pd['Leader']
        # experimental alternative or supplement:
        ppd.rVL = ppd.VL.view(np.recarray)

        for attr in ['NPings', 'NCells', 'NBeams', 'CellSize',
                      'Pulse', 'Blank', 'Bin1Dist', 'depth_interval']:
            ppd[attr] = self.__getattribute__(attr)

        # For consistency with LTA and STA:.
        ppd.num_pings = np.ones((len(ppd.VL),), dtype=np.uint16)
        ppd.num_pings *= ppd.NPings  # Maybe not 1 in old LADCP files.

        FL = Bunch.from_structured(ppd.VL)
        ppd.sysconfig = self.SysCfg(FL.Config)
        ppd.trans = self.CoordTrans(FL.Config)

        ppd.dep = ppd.Bin1Dist + ppd.depth_interval * np.arange(ppd.NCells)

        if 'Velocity' in pd:
            ppd.vel = np.ma.masked_equal(pd['Velocity'], 2048).astype(float)
            ppd.vel *= self.velscale
            ppd.split('vel')
        if 'Intensity' in pd:
            ppd.amp = pd['Intensity']
            ppd.split('amp')
        if 'SpectralWidth' in pd:
            ppd.sw = pd['Intensity']
            ppd.split('sw')
        # Don't bother with PG; all this is for single-ping data.
        # Status also provides no new information.
        VL = ppd.VL
        # We could try to watch for crossing a year boundary, so
        # that at least the dday differences would always be
        # correct.
        ppd.dday = codas.to_day(self.yearbase,
                                    self.yearbase, VL['Month'], VL['Day'],
                                    VL['Hour'], VL['Minute'], VL['Second'])
        # We could try to unwrap the following:
        ppd.ens_num = VL['EnsNum'].astype(np.int64)
        # but both unwrapping operations might better be left to
        # code outside the reader, because they are global operations,
        # not file-specific.
        ppd.temperature = 45.0 - (VL['Temperature'] * (50.0 / 4096))
        ppd.heading = VL['Heading'].astype(float) *(360.0/ 65536.0)
        ppd.pitch = VL['Pitch'].astype(float) *(360.0/ 65536.0)
        ppd.roll = VL['Roll'].astype(float) *(360.0/ 65536.0)
        _bt_vel = np.ascontiguousarray(VL['BT_Vel'])
        _bt_vel = nbvel.unpack_vel(_bt_vel, len(ppd.dday))
        ppd.bt_vel = np.ma.masked_equal(_bt_vel, 2048).astype(float)
        ppd.bt_vel *= self.velscale
        ppd.bt_depth = np.ma.array(VL['BT_Range'],
                                    mask=ppd.bt_vel.mask, dtype=float)
        return ppd


def instname_from_file(fname):
    """
    Return the sonar instname string for a raw data file.

    Only BB, WH, and OS files are supported.
    (adding SV and PN; untested as of 2020-09-25)

    """
    try:
        reader = FileBBWHOS(fname, sonar=None, trim=False)
    except:
        _log.exception("File %s cannot be interpreted as raw BB, WH, OS, SV, or PN.",
                      fname)
        raise
    instname = reader.sonar.instname
    reader.close()
    return instname

