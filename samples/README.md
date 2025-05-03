# Samples

Samples of the SCSI data from PC Engine CDROM, for use with the Protocol decoder (for sigrok/pulseview-based logic state analyzers).

## Overview

Various samples have been collected and placed here for review. To a certain extent, they are sorted
into categories according to usage.

## Significant Information from "Specific Tests"

The "specific tests" folder contains some deliberate tests which will probably not show up in actual games.

jbrandwood wrote a program to exercise the SCSI interface ("scsitest.pce", included), to test various scenarios.
It works in concert with a PC Engine game disc which has a normal audio track as track 1.

Source code for the scsitest program can be found here:
[https://github.com/pce-devel/huc/tree/master/examples/asm/elmer/cd-core-scsitest](https://github.com/pce-devel/huc/tree/master/examples/asm/elmer/cd-core-scsitest)

### Test 6 (Read Data and Abort) & Test 7 (Read Data and Abort part 2):

In these tests, the command is initiated, and the SEL signal is asserted in order to abort.

The situation here is that - since the subphase is DATA_IN - the data buffer needs to be
drained before BSY will acknowledge the abort request.


### Test 8 (Read Data and Abort STAT_IN) & Test 9 (Read Data and Abort MESG_IN):

In these tests, the command is initiated, and the SEL signal is asserted in order to abort,
but in different subphases of the Information Transfer phase - STAT_IN and MESG_IN.

In these cases, after the SEL signal is asserted, the BSY signal will go high and close the
transaction comlpetely.

### Test 14 (Play Audio 7 seconds and Abort after 3 seconds):

This test is significant for several reasons:

1. While playing the audio, the SCSI controller stays in COMMAND phase for the entire time until
SEL is asserted.  Once SEL is asserted, the BSY signal goes high, and quickly goes low again,
re-entering COMMAND phase in order to accept a new command.

2. In order to exit the COMMAND phase, the special command 0xFF (abort) is sent, and the SCSI
bus enters into STAT_IN and MSG_IN phases quickly in order to close out the SCSI command.

3. When the CD completes the original PLAY operation, the SCSI command re-enters into STAT_IN
phase (BSY low, CD low, IO low, MSG high) in an attempt to close out the original SCSI command.
This seems unusual, but it seems like either (a) STAT and MSG codes must be comsumed, or (b) as in
tests 8 and 9 above, the SEL can be asserted again, and the transaction will close automatically.

### Abort During Command Phase:

![Abort During Command Phase](img/Abort_during_Command_phase.jpg)


### Unexpected Re-assert After Audio Playback Completion:

![Unexpected SCSI Re-Engage after Song Completion](img/Unexpected_SCSI_Re-Engage.jpg)
