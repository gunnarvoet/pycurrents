#!/usr/bin/env python
'''
grab the transdcuer-gps horizontal offset and print to screen
'''

def cat_xy():
    with open('cal/watertrk/guess_xducerxy.out','r') as newreadf:
        txt = newreadf.read()
    chunks = txt.split('\n\n')

    print('getting transducer-gps offset from cal/watertrk/guess_xducerxy.out')


    print('\n\n**transducer-gps offset**\n-----------')
    print(chunks[-1].rstrip())
    print('-----------\n')

if __name__ == "__main__":
    cat_xy()