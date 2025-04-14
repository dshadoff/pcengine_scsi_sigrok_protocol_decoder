##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2024 David Shadoff <david.shadoff@gmail.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
from collections import deque

class SamplerateError(Exception):
    pass


def getluns(datapins):
    value = "LUN "
    first = 0
    for iter in range (7, -1, -1):
        if datapins[iter] == 1:
            if first == 0:
                value = value + str(iter)
                first = 1
            else:
                value = value + "," + str(iter)
    return value


def getbyteval(datapins):
    number = 0
    for iter in range (0, 8):
        if datapins[iter] == 1:
            number = number + (1 << iter)
#    value = '0x%2.2X' % number
    return number


def subphase_label(subphase):
    if subphase == 0:
        sp_label = ['Message In',      'Msg In',   'MI']
    elif subphase == 1:
        sp_label = ['Message Out',     'Msg Out',  'MO']
    elif subphase == 2:
        sp_label = ['Unused Subphase', 'Unused',   'U']
    elif subphase == 3:
        sp_label = ['Unused Subphase', 'Unused',   'U']
    elif subphase == 4:
        sp_label = ['Status',          'Stat',     'S']
    elif subphase == 5:
        sp_label = ['Command',         'Cmd',      'C']
    elif subphase == 6:
        sp_label = ['Data In',         'Data In',  'DI']
    else:
        sp_label = ['Data Out',        'Data Out', 'DO']
    return sp_label


def command_annotation(byte0):
    if ((byte0 == 0x00) or (byte0 == 0x03) or (byte0 == 0x1E)):     # status-type
        annotation = 21

    elif ((byte0 == 0x43) or (byte0 == 0x44)):                      # directory-type
        annotation = 22

    elif ((byte0 == 0x08) or (byte0 == 0x28)):                      # data-type
        annotation = 23

    elif ((byte0 == 0xD8) or (byte0 == 0xD9) or (byte0 == 0x4B)):   # audio-type
        annotation = 24

    elif ((byte0 == 0x42) or (byte0 == 0xDD)):                      # subcode-type
        annotation = 25

    else:                                                           # unknown
        annotation = 28

    return annotation


def command_label(ctype):
    if (ctype[0] == 0x00):              # 00 = TEST UNIT READY
        cmd_label = [ f"[00]: TEST UNIT READY   [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]

    elif (ctype[0] == 0x03):            # 03 = REQUEST SENSE
        if ctype[4] == 0x12:
            cmd_label = [ f"[03]: REQUEST SENSE (18 bytes)    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]
        else:
            cmd_label = [ f"[03]: REQUEST SENSE ({ctype[4]} bytes)    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]

    elif (ctype[0] == 0x08):            # 08 = READ (6)
        lba = ((ctype[1] & 0x1F ) << 16) + (ctype[2] << 8) + ctype[3]
        if (ctype[4] == 0x00):
            blks = 256
        else:
            blks = ctype[4]
        cmd_label = [ f"[08]: READ LBA 0x{lba:06X}, 0x{blks:02X} BLOCKS    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]

    elif (ctype[0] == 0x15):            # 15 = MODE SELECT
        if ctype[1] == 0x00:
            cmd_label = [ f"[15]: MODE SELECT (VENDOR-SPECIFIC), LIST LENGTH=0x{ctype[4]:02X}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]
        else:
            cmd_label = [ f"[15]: MODE SELECT (SCSI-2 COMPLIANT), LIST LENGTH=0x{ctype[4]:02X}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]

    elif (ctype[0] == 0x1A):            # 1A = MODE SENSE
        pc = (ctype[2] & 0xC0) >> 6
        page_code = (ctype[2] & 0xBF)
        if ((ctype[1] == 0x00) and (ctype[2] == 0x00)):
            cmd_label = [ f"[1A]: MODE SENSE (VENDOR-SPECIFIC), LIST LENGTH=0x{ctype[4]:02X}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]
        else:
            cmd_label = [ f"[1A]: MODE SENSE PC={pc}, PAGE CODE=0x{page_code:02X}, LIST LENGTH=0x{ctype[4]:02X}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]

    elif (ctype[0] == 0x1E):            # 1E = PREVENT/ALLOW MEDIUM REMOVAL
        if ctype[4] == 0x00:
            cmd_label = [ f"[1E]: ALLOW MEDIUM REMOVAL    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]
        else:
            cmd_label = [ f"[1E]: PREVENT MEDIUM REMOVAL    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]

    elif (ctype[0] == 0x28):            # 28 = READ EXTENDED (10)
        lba = (ctype[2] << 24) + (ctype[3] << 16) + (ctype[4] << 8) + ctype[5]
        blks = (ctype[7] << 8) + ctype[8]
        if ctype[9] == 0x00:
            cmd_label = [ f"[28]: READ LBA 0x{lba:08X}, 0x{blks:04X} BLOCKS    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif ctype[9] == 0x40:
            cmd_label = [ f"[28]: READ MSF {ctype[2]:02X}:{ctype[3]:02X}:{ctype[4]:02X}, 0x{blks:04X} BLOCKS    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif ctype[9] == 0x80:
            cmd_label = [ f"[28]: READ TRACK {ctype[2]:02X}, 0x{blks:04X} BLOCKS    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        else:
            cmd_label = [ f"[28]: UNKNOWN READ, 0x{blks:04X} BLOCKS    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    elif (ctype[0] == 0x43):            # 43 = READ TOC FORMAT
        numbytes = (ctype[7] << 8) + ctype[8]
        numtracks = (numbytes - 4) >> 3
        if ctype[1] == 0x00:
            cmd_label = [ f"[43]: READ TOC, LBA FORMAT, TRACK {ctype[6]}, {numtracks} TRACK(S)    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        else:
            cmd_label = [ f"[43]: READ TOC, MSF FORMAT, TRACK {ctype[6]}, {numtracks} TRACK(S)    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    elif (ctype[0] == 0x44):            # 44 = READ HEADER
        lba = (ctype[2] << 24) + (ctype[3] << 16) + (ctype[4] << 8) + ctype[5]
        numbytes = (ctype[7] << 8) + ctype[8]
        if ctype[1] == 0x00:
            cmd_label = [ f"[44]: READ HEADER, LBA {lba:08X}, {numbytes:04X} BYTES (RETURN IN LBA FORMAT)    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        else:
            cmd_label = [ f"[44]: READ HEADER, LBA {lba:08X}, {numbytes:04X} BYTES (RETURN IN MSF FORMAT)    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    elif (ctype[0] == 0x4B):            # 4B = PAUSE/RESUME
        if ctype[8] == 0x00:
            cmd_label = [ f"[4B]: PAUSE AUDIO PLAYBACK/SCANNING    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        else:
            cmd_label = [ f"[4B]: RESUME AUDIO PLAYBACK/SCANNING    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    elif (ctype[0] == 0xD8):            # D8 = AUDIO TRACK SEARCH
        lba = (ctype[2] << 24) + (ctype[3] << 16) + (ctype[4] << 8) + ctype[5]
        if ctype[1] == 0x00:
            oper = "PAUSE"
        else:
            oper = "PLAY"

        if ctype[9] == 0x00:
            cmd_label = [ f"[D8]: AUDIO TRACK SEARCH - LBA 0x{lba:08X}, {oper}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif ctype[9] == 0x40:
            cmd_label = [ f"[D8]: AUDIO TRACK SEARCH - MSF {ctype[2]:02X}:{ctype[3]:02X}:{ctype[4]:02X}, {oper}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif ctype[9] == 0x80:
            cmd_label = [ f"[D8]: AUDIO TRACK SEARCH - TRACK {ctype[2]:02X}, {oper}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    elif (ctype[0] == 0xD9):            # D9 = PLAY
        lba = (ctype[2] << 24) + (ctype[3] << 16) + (ctype[4] << 8) + ctype[5]
        playmode = ctype[1] & 0x03
        if (playmode == 0):
            mode = "(MUTE)"
        elif (playmode == 1):
            mode = "(L-CH)"
        elif (playmode == 2):
            mode = "(R-CH)"
        elif (playmode == 3):
            mode = "(STEREO)"
        elif (playmode == 4):
            mode = "(REPEAT)"
        elif (playmode == 5):
            mode = "(BUSY)"
        elif (playmode == 6):
            mode = "(UNKNOWN)"
        else:
            mode = "(UNKNOWN)"

        if ctype[9] == 0x00:
            cmd_label = [ f"[D9]: PLAY UNTIL - LBA 0x{lba:08X}, {mode}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif ctype[9] == 0x40:
            cmd_label = [ f"[D9]: PLAY UNTIL - MSF {ctype[2]:02X}:{ctype[3]:02X}:{ctype[4]:02X}, {mode}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif ctype[9] == 0x80:
            cmd_label = [ f"[D9]: PLAY UNTIL - TRACK {ctype[2]:02X}, {mode}    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    elif (ctype[0] == 0xDA):            # DA = STILL
        cmd_label = [ f"[DA]: STILL    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    elif (ctype[0] == 0xDD):            # DD = READ SUBCODE-Q
        numbytes = (ctype[1] & 0x1F)
        cmd_label = [ f"[DD]: READ SUBCODEQ {numbytes} BYTES    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    elif (ctype[0] == 0xDE):            # DE = READ TOC
        rdtype = (ctype[1] & 3)
        if rdtype == 0:
            cmd_label = [ f"[DE]: READ TOC (NUM TRACKS)    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif rdtype == 1:
            cmd_label = [ f"[DE]: READ TOC (LEADOUT)    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif rdtype == 2:
            cmd_label = [ f"[DE]: READ TOC INFO (TRACK {ctype[2]:02X})    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]
        elif rdtype == 3:
            cmd_label = [ f"[DE]: READ TOC PARAMETER ({ctype[2]:02X})    [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} 0x{ctype[6]:02X} 0x{ctype[7]:02X} 0x{ctype[8]:02X} 0x{ctype[9]:02X} ]" ]

    else:                               # ALL OTHERS
        cmd_label = [ f"[{ctype[0]:02X}]: Unknown command  [ 0x{ctype[0]:02X} 0x{ctype[1]:02X} 0x{ctype[2]:02X} 0x{ctype[3]:02X} 0x{ctype[4]:02X} 0x{ctype[5]:02X} ]" ]

    return cmd_label


class Decoder(srd.Decoder):
    api_version = 3
    id = 'pce_scsi'
    name = 'PCE SCSI'
    longname = 'PC Engine SCSI'
    desc = 'SCSI protocol for NEC PC Engine videogame console'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Retro computing']
    channels = (
        {'id': 'scsi_d0',  'name': 'D0',  'desc': 'Data 0'},
        {'id': 'scsi_d1',  'name': 'D1',  'desc': 'Data 1'},
        {'id': 'scsi_d2',  'name': 'D2',  'desc': 'Data 2'},
        {'id': 'scsi_d3',  'name': 'D3',  'desc': 'Data 3'},
        {'id': 'scsi_d4',  'name': 'D4',  'desc': 'Data 4'},
        {'id': 'scsi_d5',  'name': 'D5',  'desc': 'Data 5'},
        {'id': 'scsi_d6',  'name': 'D6',  'desc': 'Data 6'},
        {'id': 'scsi_d7',  'name': 'D7',  'desc': 'Data 7'},
        {'id': 'scsi_sel', 'name': 'SEL', 'desc': 'Sel'},
        {'id': 'scsi_bsy', 'name': 'BSY', 'desc': 'Busy'},
        {'id': 'scsi_cd',  'name': 'CD',  'desc': 'Cmd'},
        {'id': 'scsi_io',  'name': 'IO',  'desc': 'I/O'},
        {'id': 'scsi_msg', 'name': 'MSG', 'desc': 'Msg'},
        {'id': 'scsi_ack', 'name': 'ACK', 'desc': 'Ack'},
    )

# Each of these defines a piece of data and a color
#
# You can several of these on the same row, or they can be separated
# onto different rows below
#
    annotations = (
        ('5',  'bus_free',    'Bus Free'),           # 0 = (row 1)
        ('6',  'arbitration', 'Arbitration'),        # 1 = (row 1)
        ('7',  'selection',   'Selection'),          # 2 = (row 1)
        ('8',  'reselection', 'Reselection'),        # 3 = (row 1)
        ('9',  'inf_xfer',    'Info Xfer'),          # 4 = (row 1)
        ('11', 'unused',      'Unused'),             # 5 = (row 1)
        ('12', 'unused',      'Unused'),             # 6 = (row 1)
        ('10', 'unused',      'Unused'),             # 7 = (row 1)
        ('1',  'unused',      'Unused'),             # 8 = (row 1)
        ('4',  'unused',      'Unused'),             # 9 = (row 1)
        ('0',  'reset',       'Reset'),              # 10 = (row 1)

        ('3',  'unit',        'Unit'),               # 11 = (row 2)
        ('6',  'msg_in',      'Message In'),         # 12 = (row 2)
        ('6',  'msg_out',     'Message Out'),        # 13 = (row 2)
        ('0',  'unused',      'Unused'),             # 14 = (row 2)
        ('0',  'unused',      'Unused'),             # 15 = (row 2)
        ('9',  'status',      'Status'),             # 16 = (row 2)
        ('4',  'command',     'Command'),            # 17 = (row 2)
        ('13', 'data_in',     'Data In'),            # 18 = (row 2)
        ('1',  'data_out',    'Data Out'),           # 19 = (row 2)

        ('6',  'datatotgt',   'Data to Target'),     # 20 = (row 4)
        ('12', 'cmd0',        'Command Type 0'),     # 21 = (row 4) (status-type commands)
        ('2',  'cmd1',        'Command Type 1'),     # 22 = (row 4) (directory-type commands)
        ('8',  'cmd2',        'Command Type 2'),     # 23 = (row 4) (data-type commands)
        ('4',  'cmd3',        'Command Type 3'),     # 24 = (row 4) (audio-type commands)
        ('13', 'cmd4',        'Command Type 4'),     # 25 = (row 4) (subcode-type commands)
        ('6',  'cmd5',        'Command Type 5'),     # 26 = (row 4)
        ('6',  'cmd6',        'Command Type 6'),     # 27 = (row 4)
        ('0',  'cmd7',        'Command Type 7'),     # 28 = (row 4) (unkown commands)

        ('6',  'datafromtgt', 'Data from Target'),   # 29 = (row 5)

        ('10', 'bytenum',     'Byte in Sequence'),   # 30 = (row 6)

        ('6',  'cmd_type',    'Cmd Type'),           # 31 = (row 3)
    )
    annotation_rows = (
        ('phase',        'Phase',       (0,1,2,3,4,5,6,7,8,9,10,)),
        ('type',         'Type',        (11,12,13,14,15,16,17,18,19,)),
        ('cmd_type',     'Cmd Type',    (31,)),
        ('to_target',    'To Target',   (20,21,22,23,24,25,26,27,28,)),
        ('from_target',  'From Target', (29,)),
        ('byte_num',     'Byte Num',    (30,)),
    )

# Note - SCSI Phases:
#   Bus Free
#   Arbitration
#   Selection
#   Reselection
#   Command     --|
#   Data In       |
#   Data Out      |- These are often grouped and categorized as "Information Transfer"
#   Status        |
#   Message In    |
#   Message Out --|


    def __init__(self, **kwargs):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.last_samplenum = None
        self.state = 'BUS FREE'      # starting state for state machine
        self.startsamplenum = 0      # detect start sample of overall phase
        self.phasestartsample = 0    # detect start sample of suphasephase
        self.datastartsample = 0     # detect start sample of data 
        self.datafound = 0           # Do not display subphases unless data was actually transferred within them
                                     # (could just be CD/IO/MSG toggling)
        self.cmd_type = [ 100, 101 ]


    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)


    #
    # NOTE - Not yet implemented:
    # ---------------------------
    #
    # 1) Note that any time SCSI RESET goes low (all phases but BUS FREE):
    #    a) the command is aborted
    #    b) devices are disconnected, and
    #    c) phase goes to BUS FREE
    # (need to add SCSI_RST as input)
    #
    # 2) Currently, SCSI_ATN is not evaluated
    #
    # 3) No time values are currently evaluated (i.e. settling time or timeouts)
    #
    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        while True:
            if self.state == 'BUS FREE':
                # Wait for falling transition on channel 8 (scsi_sel), which starts arbitration/selection
                self.wait({8: 'f'})
                self.put(self.startsamplenum, self.samplenum, self.out_ann,
                                 [0, ['Bus Free', 'Free', 'F']])
                self.state = 'ARBITRATION'
                self.startsamplenum = self.samplenum


            if self.state == 'ARBITRATION':
                # Wait for falling transition on channel 9 (scsi_bsy), which completes arbitration
                (d0, d1, d2, d3, d4, d5, d6, d7, scsi_sel, scsi_bsy, scsi_cd, scsi_io, scsi_msg, scsi_ack) = self.wait({9: 'f'})
                pins = (d0, d1, d2, d3, d4, d5, d6, d7, scsi_sel, scsi_bsy, scsi_cd, scsi_io, scsi_msg, scsi_ack)
                value = getluns(pins)
#                self.put(self.startsamplenum, self.samplenum, self.out_ann,
#                                 [1, ['Arbitration', 'Arb', 'A']])
#                self.put(self.startsamplenum, self.samplenum, self.out_ann,
#                                 [11, [value]])
#                self.state = 'SELECT'
#                self.startsamplenum = self.samplenum
                self.put(self.startsamplenum, self.samplenum, self.out_ann,
                                 [2, ['Selection', 'Sel', 'Se']])
                self.put(self.startsamplenum, self.samplenum, self.out_ann,
                                 [11, [value]])
                self.state = 'INFO XFER'
                self.startsamplenum = self.samplenum
                # set up for (potential) data captures
                self.datafound = 0
                self.datastartsample = self.samplenum
                # get values of cd, io, msg for subphase
                self.subphase = (scsi_msg << 2) + (scsi_cd << 1) + scsi_io
                self.phasestartsample = self.samplenum

#            if self.state == 'SELECT':
#                # Wait for rising transition on channel 8 (scsi_sel), which completed selection
#                (d0, d1, d2, d3, d4, d5, d6, d7, scsi_sel, scsi_bsy, scsi_cd, scsi_io, scsi_msg, scsi_ack) = self.wait({8: 'r'})
#                value = getluns(pins)
#                self.put(self.startsamplenum, self.samplenum, self.out_ann,
#                                 [2, ['Selection', 'Sel', 'Se']])
#                self.put(self.startsamplenum, self.samplenum, self.out_ann,
#                                 [11, [value]])
#                self.state = 'INFO XFER'
#                self.startsamplenum = self.samplenum
#                # set up for (potential) data captures
#                self.datafound = 0
#                self.datastartsample = self.samplenum
#                # get values of cd, io, msg for subphase
#                self.subphase = (scsi_msg << 2) + (scsi_cd << 1) + scsi_io
#                self.phasestartsample = self.samplenum


            if self.state == 'INFO XFER':
                # Within Command, three signals are most important: SCSI_MSG, SCSI_CD and SCSI_IO
                # SCSI_CD = Command (when low), Data (when High)
                # SCSI_IO = Input (when low), Output (when High)
                #
                # Wait for rising transition on channel 9 (scsi_bsy), which completes transaction
                (d0, d1, d2, d3, d4, d5, d6, d7, scsi_sel, scsi_bsy, scsi_cd, scsi_io, scsi_msg, scsi_ack) = self.wait([{10: 'e'}, {11: 'e'}, {12: 'e'}, {13: 'e'}, {9: 'h'}])

                pins = (d0, d1, d2, d3, d4, d5, d6, d7, scsi_sel, scsi_bsy, scsi_cd, scsi_io, scsi_msg, scsi_ack)

                self.match_criteria = self.matched
                double_check = 1
                end_subphase = 0

                while (double_check == 1):

                    end_subphase = 0
                    (ch0, ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8, ch9, ch10, ch11, ch12, ch13) = self.wait([{10: 'e'}, {11: 'e'}, {12: 'e'}, {13: 'e'}, {9: 'e'}, {'skip': 1}])

                    if ((self.matched & 0b11111) == 0):             # if nothing triggered except the 'skip' message (critical lines didn't toggle)
                        double_check = 0

                    if ((self.match_criteria & (0b1 << 0)) and (self.matched & (0b1 << 0))):        # They should cancel each other out
                        self.match_criteria = (self.match_criteria & 0b111110)
                        self.matched        = (self.matched & 0b111110)

                    if ((self.match_criteria & (0b1 << 1)) and (self.matched & (0b1 << 1))):        # They should cancel each other out
                        self.match_criteria = (self.match_criteria & 0b111101)
                        self.matched        = (self.matched & 0b111101)

                    if ((self.match_criteria & (0b1 << 2)) and (self.matched & (0b1 << 2))):        # They should cancel each other out
                        self.match_criteria = (self.match_criteria & 0b111011)
                        self.matched        = (self.matched & 0b111011)

                    if ((self.match_criteria & (0b1 << 3)) and (self.matched & (0b1 << 3))):        # They should cancel each other out
                        self.match_criteria = (self.match_criteria & 0b110111)
                        self.matched        = (self.matched & 0b110111)

                    if ((self.match_criteria & (0b1 << 4)) and (self.matched & (0b1 << 4))):        # They should cancel each other out
                        self.match_criteria = (self.match_criteria & 0b101111)
                        self.matched        = (self.matched & 0b101111)

                    if ((self.match_criteria & (0b1 << 0)) and not (self.matched & (0b1 << 0))):    # triggered on first wait, and confirmed as 'not a glitch'
                        end_subphase = 1

                    if ((self.match_criteria & (0b1 << 1)) and not (self.matched & (0b1 << 1))):
                        end_subphase = 1

                    if ((self.match_criteria & (0b1 << 2)) and not (self.matched & (0b1 << 2))):
                        end_subphase = 1

                    # falling ACK (end of REQ, start of ACK) means data should be sampled
                    if ((self.match_criteria & (0b1 << 3)) and not (self.matched & (0b1 << 3))):
                        if (scsi_ack == 0):                                             # sample data on falling ACK
                            self.dataval = getbyteval(pins)

                        else:

                    # rising ACK means end of data pulse
                            if (self.subphase == 5):        # COMMAND
                                if (self.datafound == 0):   # first byte of command
                                    command_annote = command_annotation(self.dataval)
                                    self.cmd_type.clear()                    # clear cmd_type list
                                self.cmd_type.append(self.dataval)           # add bytes to cmd_type list
                            else:
                                command_annote = 20                     # DATA (if data is being xferred to target)

                            if (self.subphase & (0b1 << 0)):                            # If scsi_io is set, direction is to target device
                                self.put(self.datastartsample, self.samplenum, self.out_ann,
                                                 [command_annote, ['0x%2.2X' % self.dataval]])
                            else:                                                       # If scsi_io is not set, direction is from target device
                                self.put(self.datastartsample, self.samplenum, self.out_ann,
                                                 [29, ['0x%2.2X' % self.dataval]])
                            self.put(self.datastartsample, self.samplenum, self.out_ann,
                                                 [30, ['%d' % self.datafound]])
                            self.datafound = self.datafound + 1
                            self.datastartsample = self.samplenum

                    # High BSY means end of Information Transfer phase
                    if ((self.match_criteria & (0b1 << 4)) and not (self.matched & (0b1 << 4))):
                        self.put(self.startsamplenum, self.samplenum, self.out_ann,
                                         [4, ['Information Transfer', 'Info Xfer', 'Inf']])
                        self.state = 'BUS FREE'
                        self.startsamplenum = self.samplenum
                        end_subphase = 1

                    if (end_subphase == 1):
                        temp_subphase = (scsi_msg << 2) + (scsi_cd << 1) + (scsi_io << 0)
                        if self.datafound > 0:                                          # only annotate if there was data transferred
                            subph_label = subphase_label(self.subphase)
                            self.put(self.phasestartsample, self.samplenum, self.out_ann,
                                         [(12+self.subphase), subph_label])

                            if (self.subphase == 5):                                    # If the command has ended, make extended annotation
                                cmd_type_label = command_label(self.cmd_type)
                                self.put(self.phasestartsample, self.samplenum, self.out_ann,
                                         [31, cmd_type_label])

                        self.phasestartsample = self.samplenum
                        self.subphase = temp_subphase
                        self.datafound = 0
                        self.datastartsample = self.samplenum
                        end_subphase = 0

                    if (double_check == 1):
                        self.last_samplenum = self.samplenum
                        self.match_criteria = self.matched
                        d0 = ch0
                        d1 = ch1
                        d2 = ch2
                        d3 = ch3
                        d4 = ch4
                        d5 = ch5
                        d6 = ch6
                        d7 = ch7
                        scsi_sel = ch8
                        scsi_bsy = ch9
                        scsi_cd  = ch10
                        scsi_io  = ch11
                        scsi_msg = ch12
                        scsi_ack = ch13
                        pins = (d0, d1, d2, d3, d4, d5, d6, d7, scsi_sel, scsi_bsy, scsi_cd, scsi_io, scsi_msg, scsi_ack)


            self.last_samplenum = self.samplenum
