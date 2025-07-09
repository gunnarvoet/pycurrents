Tips/Hints
-----------


(1) make yaxis increasing downward

::

  # "ax" is the axes object

  ylims = ax.get_ylim()
  ax.set_ylim([max(ylims), min(ylims)])

(2) put text on an axes object, like "mtext" in matlab

::

   # "ax" is the axes object

   ax.text(xfrac, yfrac, textstring, transform=ax.transAxes, **kwargs)

(3) grab indices ii and jj of a 2-d array

::

  #  eg zz(ii,jj) in matlab

  zz[np.ix_(imask, jmask)]       #imask, jmask are indices or logical


(4) make x-axis label NOT display in scientific notation

::

   # "ax" is the axes object

   ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

(5) get the good values from a masked array

::

   # x_ma is the masked array
   # y is the unmasked collection of values to use

   good_y = np.compress(ma.getmaskarray(x_ma), y)

(6)

::

   # like "repmat", tiling the profiles to contour with depth

   data=get_profiles(dbname)
   nprofs, nbins = data.amp1.shape
   ddayM = np.kron(np.ones((1,nbins)),data.dday[:,np.newaxis])



(7) for debugging; like "keyboard" in matlab

::


   ## for debugging - include these imports

   from IPython.Shell import IPShellEmbed
   ipshell = IPShellEmbed()

   ## later, when desired, add this call to drop into ipython shell:
   ipshell()

   ## NOTE: for use in programs that will be called as scripts
   ## NOTE: write it so there are no switches (options) or the
   #        will be passed to ipython






