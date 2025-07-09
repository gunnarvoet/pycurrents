"""
This was moved here from adcpgui/tools.py
"""


from pycurrents.plot.mpltools import get_extcmap

display_opt = {}

def reset_display_opt():
    global display_opt

    display_opt.clear()
    display_opt['use_bins'] = False     # plot against bins or depth
    display_opt['use_cbarjet'] = False
    display_opt['axes'] = ['u', 'v', 'pg', 'amp', 'w','e','fvel','pvel']
    display_opt['show_spd'] = False
    display_opt['nbins'] = 128
    display_opt['velrange'] = [-.6,.6]
    display_opt['refbins'] = [2, 10]
    display_opt['depth'] = None
    display_opt['mask'] = None
#---

cmap_pg3080 = get_extcmap('pg3080')
cmap_jet = get_extcmap('jet')
cmap_gautoedit = get_extcmap('gautoedit')
cmap_ob = get_extcmap('ob_vel')
cmap_rbvel = get_extcmap('rb_vel')
cmap_diff = get_extcmap('blue_white_red')

jet_cmapdict = {
'pg'         :   cmap_pg3080,
'pflag'      :   cmap_pg3080,
'amp'        :   cmap_jet,
'ramp'       :   cmap_jet,
'sw'         :   cmap_jet,
'umeas'      :   cmap_rbvel,
'vmeas'      :   cmap_rbvel ,
'w'          :   cmap_rbvel ,
'e'          :   cmap_rbvel ,
'u'          :  cmap_gautoedit ,
'v'          :  cmap_gautoedit ,
'fvel'       :  cmap_gautoedit ,
'pvel'       :  cmap_gautoedit ,
'resid_stats_fwd' :  cmap_rbvel,
'diff'       : cmap_diff}

alt_cmapdict = jet_cmapdict.copy()
alt_cmapdict['u'] = cmap_ob
alt_cmapdict['v'] = cmap_ob
alt_cmapdict['fvel'] = cmap_ob
alt_cmapdict['pvel'] = cmap_ob

clims = {'u'   : [-.6, .6],
         'v'   : [-.6, .6],
         'diff': [-.12, .12],
         'pg'  : [0, 100],
         'amp' : [0, 200],
         'fvel': [-.6, .6],
         'pvel': [-.6, .6],
         'e'   : [-100,100],
         'w'   : [-100,100],
         'pflag' : [0,8],
         'resid_stats_fwd':[0,100]}

titles = {'u'    : 'ocean u m/s',
          'v'    : 'ocean v m/s',
          'pg'   : 'percent good',
          'amp'  : 'signal return',
          'fvel' : 'ocean fwd m/s',
          'pvel' : 'ocean port m/s',
          'e'    : 'error vel mm/s',
          'w'    : 'vert. vel mm/s',
          'pflag': 'profile flags',
          'resid_stats_fwd' : 'resid fvel std'}
