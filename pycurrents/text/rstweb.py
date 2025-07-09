'''
helpers for generating restructured text or html
'''


def imagestr(rstlinkname, thumbnail, link_target, alt_text='linked image'):
    '''
    return a string suitable for use in RST image link

    rstlinkname : the name that will be used in RST to call the link
                    call it as          \|rstlinkname\|_
    thumbnail: the image that will be displayed
    link_target:    the target location (where you go when you click)
    alt_text: displays with mousover

    '''
    sstr = '\n'.join(['.. ===============',
        '.. |%(IMAGE_NAME)s| image:: %(thumbnail)s',
        '    :alt: %(alt_text)s',
        '..   _%(IMAGE_NAME)s: %(link_target)s ',
        '.. ==============='])


    return sstr % ({'IMAGE_NAME': rstlinkname,
                  'thumbnail' : thumbnail,
                  'link_target'    : link_target,
                  'alt_text'  : alt_text})



