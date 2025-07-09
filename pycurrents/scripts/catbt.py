#!/usr/bin/env python
'''
grab the bottom track calibration from the right file and print to screen
'''

def cat_bt():
    with open('cal/botmtrk/btcaluv.out','r') as newreadf:
        txt = newreadf.read()
    chunks = txt.split('ADCP bottomtrack calibration')
    lines = chunks[-1].split('\n')

    olist=['\n','   **bottomtrack**  ','-----------']
    count=0
    for line in lines:
        if 'unedited' in line:
            olist.extend(lines[count:count+5])
            break
        count += 1

    olist.extend(['-----------','\n'])


    print('getting bottom track information from cal/botmtrk/btcaluv.out')
    print('\n'.join(olist))


if __name__ == "__main__":
    cat_bt()