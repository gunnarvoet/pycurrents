"""
Access and edit nav sensor data stored in rbin files.

"""

import logging

import numpy as np

from pycurrents.file.binfile_n import BinfileSet
from pycurrents.data.navcalc import unwrap
from pycurrents.num import expand_mask
from pycurrents.num import mask_nonincreasing
from pycurrents.num.glitch import glitch

# Standard logging
_log = logging.getLogger(__name__)


class RbinSet(BinfileSet):
    def __init__(self, filenames, alias=None,
                                  unwrap=False,
                                  mono=True,
                                  m_mono=True,
                                  deglitch=5.0,
                                    **kw):
        """
        filenames: single rbin name, list of names, or glob

        keyword arguments:
            Ashtech:
                maxrms
                maxbms
            POSMV:
                acc_heading_cutoff
                acc_roll_cutoff
                gams_cutoff
                posmv_trim

            unwrap : unwrap any lon, heading columns
            alias : (passed to BinfileSet) column name translation
            mono : if dday column is present, mask out backwards jumps
            m_mono : if m_dday is present, mask out non-increasing pts.
            deglitch: if dday is present, run a glitch detector on it,
                        with this number of seconds as the threshold.
                        Set to 0.0 to disable.

        Note: data are always exposed as masked arrays.

        """
        BinfileSet.__init__(self, filenames, masked=True, alias=alias)
        maskers = {'gga': self._edit_gps,
                   'gps': self._edit_gps,
                   'ggn': self._edit_gps,
                   'gns': self._edit_gns,
                   'rmc': self._edit_rmc,
                   'gps_sea': self._edit_gps_sea,
                   'pmv': self._edit_pmv,
                   'pvec': self._edit_pvec,
                   'sea': self._edit_sea,
                   'att': self._edit_ashtech,
                   'adu': self._edit_ashtech,
                   'at2': self._edit_ashtech,
                   'paq': self._edit_ashtech,
                   'hpr': self._edit_ashtech,
                   'vbw': self._edit_vbw,
                   'psathpr': self._edit_psathpr,
                   'hnc_tss1':self._edit_hdg_tss1,
                   'hdg_tss1':self._edit_hdg_tss1,
                   'hdg': self._edit_none,
                   'hdt': self._edit_none,
                   'hnc': self._edit_none,
                   'gph': self._edit_none,
                   'ths': self._edit_none,
                   'rdi': self._edit_none,
                   'rdinc': self._edit_none,
                   'rnh': self._edit_none,
                   'ixgps': self._edit_none,
                   'ixalg': self._edit_none,
                   'psxn23': self._edit_none,
                   'tss1': self._edit_none,
                   'internal_heading' : self._edit_none,
                   'spd': self._edit_none,
                   'gpgst': self._edit_none,
                   'ptnlvhd': self._edit_none,
                   'jratt': self._edit_none,
                   'jrattn': self._edit_none,
                   'jrhve': self._edit_none,
                   'jrhven': self._edit_none,
                   }
        self._icol = dict(zip(self.columns, range(len(self.columns))))
        self._editor = maskers[self.name]
        self._editorkw = kw
        self._unwrap = unwrap
        self._mono = mono
        self._m_mono = m_mono
        self._deglitch = deglitch

    def get_array(self):
        arr = BinfileSet.get_array(self)
        if arr.shape[0] == 0:
            return arr

        self._editor(arr, **self._editorkw)
        if self._unwrap:
            try:
                j = self._icol['heading']
                arr[:, j] = unwrap(arr[:, j])
            except KeyError:
                pass
            try:
                j = self._icol['lon']
                arr[:, j] = unwrap(arr[:,j])
            except KeyError:
                pass

        if self._deglitch and 'dday' in self.columns:
            dday = arr[:, self._icol['dday']]
            glitchmask = glitch(dday, self._deglitch/86400)
            nglitch = glitchmask.sum()
            if nglitch:
                arr[glitchmask] = np.ma.masked
                _log.warning("In %s, masking records with dday glitches: %s",
                         self.name, nglitch)

        if self._mono and 'dday' in self.columns:
            dday = arr[:, self._icol['dday']]
            _dday = mask_nonincreasing(dday)
            if np.ma.is_masked(_dday):
                nmasked = dday.count() - _dday.count()
                if nmasked:
                    arr[_dday.mask] = np.ma.masked
                    _log.warning("In %s, masking records"
                             " with nonincreasing dday: %s",
                             self.name, nmasked)

        if self._m_mono and 'm_dday' in self.columns:
            dday = arr[:, self._icol['m_dday']]
            _dday = mask_nonincreasing(dday)
            if np.ma.is_masked(_dday):
                nmasked = dday.count() - _dday.count()
                if nmasked:
                    arr[_dday.mask] = np.ma.masked
                    _log.warning("In %s, masking records"
                             " with nonincreasing m_dday: %s",
                             self.name, nmasked)

        return arr

    def _edit_none(self, arr, **kw):
        pass

    def _edit_gps(self, arr, **kw):
        qual = arr[:, self._icol['quality']]
        cond = (qual == 0) | (qual == 6)
        arr[cond, self._icol['lon']] = np.ma.masked
        arr[cond, self._icol['lat']] = np.ma.masked


    def _edit_gns(self, arr, **kw):
        '''
        do not know what this means yet. use hdop==0 for now
        '''
        qual = arr[:, self._icol['hdop']]
        cond = (qual == 0)
        arr[cond, self._icol['lon']] = np.ma.masked
        arr[cond, self._icol['lat']] = np.ma.masked

    def _edit_rmc(self, arr, **kw):
        ok = arr[:, self._icol['ok']]
        cond = (ok == 0)
        arr[cond, self._icol['lon']] = np.ma.masked
        arr[cond, self._icol['lat']] = np.ma.masked


    def _edit_gps_sea(self, arr, **kw):
        qual = arr[:, self._icol['quality']]
        badqual = (qual == 0) | (qual == 6)
        badhqual = arr[:, self._icol['horiz_qual']] > 1
        # It is not clear there is any point in checking both
        # qual and horiz_qual.  It seems that horiz_qual of 1
        # means no DGPS; presumably a value of 2, "invalid",
        # would coincide with the GGA quality field also indicating
        # no valid fix.
        cond = badqual | badhqual
        arr[cond, self._icol['lon']] = np.ma.masked
        arr[cond, self._icol['lat']] = np.ma.masked

    def _edit_pmv(self, arr, **kw):
        # should use flag_IMU also...
        acc_heading_cutoff = kw.get('acc_heading_cutoff', 0.65)
        acc_roll_cutoff = kw.get('acc_roll_cutoff', 0.25)
        gams_cutoff = kw.get('gams_cutoff', 0.5) # disable (too restrictive)
        trim = kw.get('posmv_trim', 0)

        iah = self._icol['acc_heading']
        bad_acc_heading = arr[:, iah] > acc_heading_cutoff
        ifg = self._icol['flag_GAMS']
        bad_gams = arr[:, ifg] < gams_cutoff
        iar = self._icol['acc_roll']
        bad_acc_roll = arr[:, iar] > acc_roll_cutoff

        if trim > 0:
            bad_acc_heading = expand_mask(bad_acc_heading, trim)

        cond = bad_acc_heading | bad_gams
        arr[cond, self._icol['heading']] = np.ma.masked
        arr[bad_acc_roll, self._icol['pitch']] = np.ma.masked
        arr[bad_acc_roll, self._icol['roll']] = np.ma.masked
        cond = bad_acc_roll | bad_acc_heading | bad_gams
        arr[cond, self._icol['heave']] = np.ma.masked
        # The line above is questionable, but doesn't matter for present use.
    def _edit_pvec(self, arr, **kw):
        acc_heading_cutoff = kw.get('acc_heading_cutoff', 0.65)

        iah = self._icol['acc_heading']
        bad_acc_heading = arr[:, iah] > acc_heading_cutoff

        cond = bad_acc_heading
        arr[cond, self._icol['heading']] = np.ma.masked

    def _edit_sea(self, arr, **kw):
        ic = self._icol
        cond = arr[:, ic['head_qual']] != 0
        arr[cond, ic['heading']] = np.ma.masked
        cond = arr[:, ic['rp_qual']] != 0
        arr[cond, ic['pitch']] = np.ma.masked
        arr[cond, ic['roll']] = np.ma.masked
        cond = arr[:, ic['height_qual']] != 0
        arr[cond, ic['heave']] = np.ma.masked

    def _edit_ashtech(self, arr, **kw):
        maxmrms = kw.get('maxmrms', 0.015)
        maxbrms = kw.get('maxbrms', 0.2)
        ic = self._icol
        cond = ((arr[:, ic['mrms']] > maxmrms) |
                (arr[:, ic['brms']] > maxbrms))
        if hasattr(ic, 'reacq'):
            cond = cond | (arr[:, ic['reacq']] == 1)
        if hasattr(ic, 'ia'):
            cond = cond | (arr[:, ic['ia']] == 1)
        arr[cond, ic['heading']] = np.ma.masked
        arr[cond, ic['pitch']] = np.ma.masked
        arr[cond, ic['roll']] = np.ma.masked

    def _edit_psathpr(self, arr, **kw):   # CSI
        ic = self._icol
        cond = arr[:, ic['flag_gps']] != 1
        arr[cond, ic['pitch']] = np.ma.masked
        arr[cond, ic['roll']] = np.ma.masked
        arr[cond, ic['heading']] = np.ma.masked

    def _edit_hdg_tss1(self, arr, **kw):
        ic = self._icol
        cond = ((arr[:, ic['status']] != 7 ) |
                (arr[:, ic['haccel']] < 0  ) | (arr[:, ic['haccel']] > 1   ) |
                (arr[:, ic['vaccel']] < 0.5) | (arr[:, ic['vaccel']] > 0.75) |
                (arr[:, ic['heave']]  < -5 ) | (arr[:, ic['heave']]  > 5   ) |
                (arr[:, ic['roll']]   < -20) | (arr[:, ic['roll']]   > 20  ) |
                (arr[:, ic['pitch']]  < -5 ) | (arr[:, ic['pitch']]  > 5   ) )

        arr[cond, ic['pitch']] = np.ma.masked
        arr[cond, ic['roll']] = np.ma.masked
        arr[cond, ic['heading']] = np.ma.masked
        arr[cond, ic['haccel']] = np.ma.masked
        arr[cond, ic['vaccel']] = np.ma.masked
        arr[cond, ic['heave']] = np.ma.masked

    def _edit_vbw(self, arr, **kw):
        ic = self._icol
        cond = ((arr[:, ic['flag_w']] != 0)
                )
        arr[cond, ic['fwd_w']] = np.ma.masked
        arr[cond, ic['stbd_w']] = np.ma.masked
