#!/usr/bin/env python

#==============================================================================
# Program to dump out the values for 1 field from a BUFR file
#==============================================================================

import argparse
import collections
import ncepbufr
try:
    import netCDF4
except ModuleNotFoundError:
    print("netCDF4 module not found, so can't choose netCDF output option")
import numpy as np
import os.path
import subprocess
import sys

sys.path.append(os.path.dirname(sys.argv[0]))
import bufrTableTools


def bufrdump(BUFRFileName, obsType, textFile=None, netCDFFile=None):
    """ dumps a field from a BUFR file

        Input:
            BUFRFileName - complete pathname of file that a field is to be
                           dumped from
            obsType - the observation type (e.g., NC001001)
            textFile - if passed, write output as text to this file
            netCDFFile - if passed, write output as netCDF to this file

        If both textFile and netCDFFile are passed, output will be written
        to textFile but not to netCDFFile.
    """

    # there undoubtedly is a better way to extract tables from BUFR files
    # than by running another process that dumps the tables but I don't know
    # what it is
    execDir = os.path.dirname(sys.argv[0])
    executable = os.path.join(execDir, "bufrtblstruc.py")
    ts = subprocess.run(args=[executable, BUFRFileName, obsType],
                        capture_output=True)
    tblLines = ts.stdout.decode("utf-8").split('\n')
    try:
        (section1, section2, section3) = bufrTableTools.parseTable(tblLines)
    except bufrTableTools.BUFRTableError as bte:
        print(bte.message)
        sys.exit(-1)

    # get a list of the mnemonics of all the fields shown for the observation
    # type in the .tbl file
    mnemonicList = bufrTableTools.getMnemonicListAll(obsType, section2)
    #mnemonicList = bufrTableTools.getMnemonicListBase(obsType, section2)

    # get the user's choice of which field to dump
    whichField = getMnemonicChoice(mnemonicList, section1)

    # dump the field
    if textFile:
        fd = open(textFile, 'w')
        dumpBUFRField(BUFRFileName, obsType, whichField, fd)
        fd.close()
    elif netCDFFile:
        BUFRField2netCDF(BUFRFileName, obsType, whichField, netCDFFile)
    else:
        dumpBUFRField(BUFRFileName, obsType, whichField, sys.stdout)

    return


def getMnemonicChoice(mnemonicList, section1):
    """ gets user's choice of which field to dump

        Input:
            mnemonicList - list containing the mnemonic names of the fields
                           in the BUFR file
            section1 - first section from a BUFR table

        Return:
            whichField - MnemonicNode object for field to dump
    """

    # separate the fields into sequences and single ("solitary") fields
    solitaryList = [x for x in mnemonicList if len(x.children) == 0]
    sequenceList = [x for x in mnemonicList if len(x.children) > 0]

    # post a list of the fields
    idx = 0
    print("\nIndividual Fields:")
    for m in solitaryList:
        idx += 1
        # don't know what to do with mnemonics that start with a period
        if m.name[0] == '"':
            print("{:3}) {:10} - {}".format(idx, m.name[1:-2], 
                                            section1[m.name[1:-2]]))
        elif m.name[0] != '.':
            print("{:3}) {:10} - {}".format(idx, m.name, section1[m.name]))

    print("\nSequences:")
    for m in sequenceList:
        idx += 1
        print("{:3}) {:10} - {}".format(idx, m.name, section1[m.name]))
    print()

    # get user's selection
    while True:
        selection = int(input("Enter number of selection: "))
        if selection <= 0:
            print("You have entered an invalid selection")
        elif selection <= len(solitaryList):
            whichField = solitaryList[selection - 1]
            break
        elif selection <= (len(solitaryList) + len(sequenceList)):
            whichField = sequenceList[selection - len(solitaryList) - 1]
            break
        else:
            print("You have entered an invalid selction")              

    return whichField


def dumpBUFRField(BUFRFilePath, obsType, whichField, fd):
    """ dumps the field from the BUFR file. The bulk of the code in this
        function was blatantly plagiarized from Steve Herbener's bufrtest.py.

        Input:
            BUFRFilePath - complete pathname of the BUFR file
            obsType - the observation type code (NCxxxxxx)
            whichField - MnemonicNode object of the field to dump
            fd - file descriptor of file to write output to
    """

    if len(whichField.children) > 0:
        # I don't know what happens if a sequence contains parents. the 
        # following 2 statements may cause errors if the parents are not
        # at the end of the list of children.
        # I've found 1 case so far in which a sequence contains a sequence.
        # I don't know how that is handled, but in this case the child
        # sequence was the last child so I can skip it. If the child sequence
        # isn't the last child, the results will not be correct.
        #sequenceLength = len([x for x in whichField.children if not x.seq])
        #sequenceLength = len([x for x in whichField.children if 
                              #len(x.children) == 0])
        leafIndices = [x.seq_index for x in whichField.children if len(x.children) == 0]
        fd.write("Order of individual fields: {}\n".format(
            [x.name for x in whichField.children if len(x.children) == 0]))
    #else:
        #sequenceLength = 1

    # open file and read through contents
    bufr = ncepbufr.open(BUFRFilePath)

    while (bufr.advance() == 0):
        if bufr.msg_type != obsType:
            continue

        fd.write("  MSG: {0:d} {1:s} {2:d} ({3:d})\n".format(
            bufr.msg_counter,bufr.msg_type,bufr.msg_date,bufr._subsets()))

        isub = 0
        while (bufr.load_subset() == 0):
            isub += 1
            Vals = bufr.read_subset \
                   (whichField.name, seq=len(whichField.children) > 0).data.squeeze()
            if len(whichField.children) > 0:
                leafValues = []
                try:
                    for leaf in leafIndices:
                        leafValues.append(Vals[leaf][:])
                    fd.write(
                        "    SUBSET: {0:d}: MNEMONIC VALUES: {other}\n".
                        format(isub, other=leafValues))
                        #format(isub, other=Vals[:sequenceLength,:]))
                except IndexError:
                    for leaf in leafIndices:
                        leafValues.append(Vals[leaf])
                    fd.write("    SUBSET: {0:d}: MNEMONIC VALUES: {other}\n".
                             format(isub, other=leafValues))
                             #format(isub, other=Vals[:sequenceLength]))
            
            else:
                fd.write("    SUBSET: {0:d}: MNEMONIC VALUES: {other}\n".
                         format(isub, other=Vals))
        #sys.exit(0)

    # clean up
    bufr.close()

    return


def BUFRField2netCDF(BUFRFilePath, obsType, whichField, outputFile):
    """ dumps the field from the BUFR file to a netCDF file.

        Input:
            BUFRFilePath - complete pathname of the BUFR file
            obsType - the observation type code (NCxxxxxx)
            whichField - MnemonicNode object of field to dump
            outputFile - full pathname of the file to write to
    """


    nfd = netCDF4.Dataset(outputFile, 'w')

    if len(whichField.children) > 0:
        # get the individual mnemonics that are in the sequence, faking names
        # where there are duplicates by adding underscores
        # I've found 1 case so far in which a sequence contains a sequence.
        # I don't know how that is handled, but in this case the child
        # sequence was the last child so I can skip it. If the child sequence
        # isn't the last child, the results will not be correct.
        leafIndices = [x.seq_index for x in whichField.children if len(x.children) == 0]
        mnemonics = [x.name for x in whichField.children
                     if not len(x.children) > 0]
        for i in range(1, len(mnemonics)):
            while mnemonics[i] in mnemonics[0:i]:
                mnemonics[i] = mnemonics[i] + '_'
    else:
        mnemonics = [whichField.name]

    dim1 = nfd.createDimension("nlocs", size=0)

    bfd = ncepbufr.open(BUFRFilePath, 'r')

    # read and write
    idxSubset = 0
    while bfd.advance() == 0:
        if bfd.msg_type != obsType:
            continue
        if bfd._subsets() < 1:
            continue
        while bfd.load_subset() == 0:
            vals = bfd.read_subset \
                   (whichField.name, seq=len(whichField.children) > 0).data.squeeze()

            if idxSubset == 0:
                # first time throught create variables
                vars = collections.OrderedDict()
                if len(vals.shape) == 2:
                    dim2 = nfd.createDimension("nlevels", size=0)
                    dims = ("nlocs", "nlevels")
                else:
                    dims = ("nlocs",)

                for m in mnemonics:
                    try:
                        vars[m] = nfd.createVariable(m, "f8", dims)
                    except RuntimeError:
                        print("not able to create variable ", m)

            # write the data. there must be a better way to do this
            idxVal = 0
            for k in vars.keys():
                if len(vals.shape) == 2:
                    vars[k][idxSubset:idxSubset+1,0:vals.shape[1]] \
                        = vals[leafIndices[idxVal],:]
                elif len(vals.shape) == 1:
                    vars[k][idxSubset:idxSubset+1] = vals[leafIndices[idxVal]]
                else:
                    vars[k][idxSubset:idxSubset+1] = vals
                idxVal += 1

            idxSubset += 1

    bfd.close()
    nfd.close()

    return


if __name__ == "__main__":

    # parse command line
    parser = argparse.ArgumentParser()
    parser.add_argument("bufr_file", type=str, 
                        help="full pathname of input file")
    parser.add_argument("observation_type", type=str, 
                        help="observation type (e.g., NC031001)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-o", type=str, required=False, \
                        help="write text output to specified file rather than stdout")
    group.add_argument("-n", type=str, required=False, \
                        help="write output to specified netCDF file rather than stdout")
    args = parser.parse_args()

    # run dump program
    if args.o:
        bufrdump(args.bufr_file, args.observation_type, textFile=args.o)
    elif args.n:
        bufrdump(args.bufr_file, args.observation_type, netCDFFile=args.n)
    else:
        bufrdump(args.bufr_file, args.observation_type)