#!/usr/bin/env python
'''
grab the watertrack calibration from the right file and print to screen
'''

def cat_wt():
    with open('cal/watertrk/adcpcal.out','r') as newreadf:
        txt = newreadf.read()
    chunks = txt.split('ADCP watertrack calibration')
    lines = chunks[-1].split('\n')

    olist=['\n','\n','   **watertrack**  ','-----------']
    count=0
    for line in lines:
        if 'edited' in line:
            olist.append(line)
            olist.append('')
            break
        count += 1

    olist.extend(lines[count+3:count+6],)
    olist.extend(['-----------','\n'])


    print('getting watertrack from cal/watertrk/adcpcal.out')
    print('\n'.join(olist))


if __name__ == "__main__":
    cat_wt()