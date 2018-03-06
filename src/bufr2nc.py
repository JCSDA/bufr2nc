#!/usr/bin/env python

from __future__ import print_function
import ncepbufr
import numpy as np
import sys
import os
import re
import netCDF4
from netCDF4 import Dataset
import struct
import bufr2ncConfig as conf

###########################################################################
# SUBROUTINES
###########################################################################

def FindNumObsFromBufrFile(PrepbufrFname, MessageRe,MaxNMsg):
    # This routine will read the BUFR file and figure out how many observations
    # will be read when recording data.

    bufr = ncepbufr.open(PrepbufrFname)

    # The number of observations will be equal to the total number of subsets
    # contained in the selected messages.
    MaxObs = 0
    NMsg = 0 
    while ( (bufr.advance() == 0) ): 
        # Select only the messages that belong to this observation type
        if (re.search(MessageRe, bufr.msg_type)):
            # Attribute "subsets" contains the number of subsets
            # for the current message.
            MaxObs += bufr.subsets
            NMsg += 1
            if (NMsg == MaxNMsg): 
                MaxObsKeep = MaxObs

    bufr.close()
 
    if (MaxNMsg<0): 
        MaxObsKeep=MaxObs

    return [MaxObsKeep, NMsg] 

def ReadBufrData(Fid, Dname, Btype, Dtype):
    # This routine will read one data piece (one mnemonic) from the BUFR file.
    #
    # The bufr.read_subset() method will return a 2D array
    # for non events, and a 3D array for events.
    #
    #   Non-event: data[nm, nlev]
    #     nm is the number of mnemonics
    #     nlev is the nubmer of levels
    #
    #   Event: data[nm, nlev, nec]
    #      nm and nlev as for non-event
    #      nec is the number of event codes
    #
    # Since we are calling these routines with one mnemonic at a time
    # squeeze off the first dimension (it will always be size one).
    #
    # Fid.read_subset() will return a floating point number (for any
    # type) or an empty list if the mnemonic didn't exist. For strings
    # (Dtype = 'string') read the floating point number as characters. Otherwise
    # convert to integer or leave alone.
    #
    # Keep Dtype values in sync with entries in the DataTypes dictionary. For now,
    # these values are "string", "integer" and "float".

    MissingInt = -9999
    MissingFlt = np.nan

    # Check for valid Btype and Dtype
    if ((Btype != 'data') and (Btype != 'event') and
        (Btype != 'rep') and (Btype != 'seq') and (Btype != 'header') ):
        print("ERROR: ReadBufrData: unrecognized BUFR type: ", Btype)
        sys.exit(-1)

    if ((Dtype != 'string') and (Dtype != 'integer') and
        (Dtype != 'float')):
        print("ERROR: ReadBufrData: unrecognized data type: ", Dtype)
        sys.exit(-1)
    
    # Determine flags for the read_subset() call
    Eflag = False  # not an event
    Rflag = False  # not a repetition
    Sflag = False  # not a sequence
    if (Btype == 'event'):
        Eflag = True
    elif (Btype == 'rep'):
        Rflag = True
    elif (Btype == 'seq'):
        Sflag = True

    # Dnum will be a numpy array of floats
    Dnum = np.squeeze(Fid.read_subset(Dname, events=Eflag, rep=Rflag, seq=Sflag ).data, axis=0)

    # Make sure return value is a numpy.array type.
    if (Dnum.size == 0):
        # array is empty
        DataPresent = False 

        if (Dtype == 'string'):
           # character array
           Dval = np.array([ '' ])
        elif (Dtype == 'integer'): 
           Dval = np.array([ MissingInt ])
        elif (Dtype == 'float'):
           Dval = np.array([ np.nan ])
    else:
        # array is not empty
        DataPresent = True

        if (Dtype == 'string'):
            # convert to list of strings
            # assume that an ID is a 1D array of float with only one
            # entry
            #
            # The bytes.join().decode() method wants the byte values
            # < 127 so that they can be mapped to the old style ascii
            # character set. In order to accommodate this, unpack the
            # float value into bytes. Then check the bytes and replace
            # all values > 127 with a blank character. Then convert
            # the byte lists to strings. Replace byte value
            # equal to zero with a blank as well.
            ByteList = list(struct.unpack('8c', Dnum[0]))

            # replace chars < 1 and > 127 with blank space
            for j in range(len(ByteList)):
                ByteVal = struct.unpack('@B', ByteList[j])[0]
                if ( (ByteVal < 1) or (ByteVal > 127)):
                    ByteList[j] = b' '

            TempStr = bytes.join(b'', ByteList).decode('ascii') 
            Dval = np.array(TempStr, dtype='S8')
        elif (Dtype == 'integer'):
            # convert missing vals to MissingInt
            Dval = Dnum.astype(np.integer)
            Dval[Dnum >= 10**9] = MissingInt
        elif (Dtype == 'float'):
            # convert missing vals to nans
            Dval = np.copy(Dnum)
            Dval[Dnum >= 10**9] = MissingFlt

    return [Dval, DataPresent] 

def CreateNcVar(Fid, Dname, Btype, Dtype,
                NobsDname, NlevsDname, NeventsDname, StrDname,
                MaxLevels, MaxEvents, MaxStringLen, MaxObs):
    # This routine will create a variable in the output netCDF file
    #
    # The dimensions are set according to the Dtype and Btype inputs.
    #
    # If Btype is 'header'
    #   Dtype       Dims
    #  'string'  [nobs, nstring]
    #  'integer' [nobs]
    #  'float'   [nobs]
    #
    # If Btype is 'data' 
    #   Dtype       Dims
    #  'string'  [nobs, nstring, nlevs]  # CSD: added levs here, since header type replaces non-lev example
    #  'integer' [nobs, nlevs]
    #  'float'   [nobs, nlevs]
    #
    # If Btype is 'event', then append the nevents dim on the end
    # of the dim specification.
    #
    #  'string'  [nobs, nstring, nevents] # CSD: suppose we should add nlevs here.  See WriteNcVar
    #  'integer' [nobs, nlevs, nevents]
    #  'float'   [nobs, nlevs, nevents]
    #
    if (Dtype == 'string'):
        Vtype = 'S1'
        DimSpec = [NobsDname, StrDname]
        ChunkSpec = [MaxObs, MaxStringLen]
    elif (Dtype == 'integer'):
        Vtype = 'i4'
        DimSpec = [NobsDname]
        ChunkSpec = [MaxObs]
    elif (Dtype == 'float'):
        Vtype = 'f4'
        DimSpec = [NobsDname]
        ChunkSpec = [MaxObs]

    # Add addditonal dimensions for data and events

    Vname = Dname
    # add levels for event and data
    if ( (Btype == 'data') or  (Btype == 'event')):
        DimSpec.append(NlevsDname)
        ChunkSpec.append(MaxLevels)

        if (Btype == 'event'):
            Vname = "{0:s}_benv".format(Dname)
            DimSpec.append(NeventsDname)
            ChunkSpec.append(MaxEvents)

    Fid.createVariable(Vname, Vtype, DimSpec, chunksizes=ChunkSpec,
        zlib=True, shuffle=True, complevel=6)

def WriteNcVar(Fid, obs_num, Dname, Btype, Dval, MaxStringLen, MaxEvents):
    # This routine will write into a variable in the output netCDF file

    # Set the variable name according to Btype
    if ( (Btype == 'data') or  (Btype == 'header') ):
        Vname = Dname
    elif (Btype == 'event'):
        Vname = "{0:s}_benv".format(Dname)

    # For the string data, convert to a numpy character array
    if ((Dval.dtype.char == 'S') or (Dval.dtype.char == 'U')):
        IsString=True
        StrSpec = "S{0:d}".format(MaxStringLen)
        Value = netCDF4.stringtochar(Dval.astype(StrSpec))
    else:
        IsString=False
        if (Btype == 'event'):
            # Trim the dimension representing events to 0:MaxEvents.
            # This will be the last dimension of a 2D array [nlev, nevent].
            Value = Dval[:,0:MaxEvents].copy()
        else:
            Value = Dval.copy()
# CSD: above will not work for string events or levels. See CreateNcVar. 

    # Find the dimension size of the value and use that to write out
    # the variable.

# CSD:changed to N1 as dimensions are switched around for strings
    Ndims = Value.ndim
    if (Ndims == 1):
        N1 = Value.shape[0]
        # for header variables, there is no lvl dimension.
        if ( (Btype == 'header') and (not IsString) ): 
            Fid[Vname][obs_num] = Value
            if (N1>1): 
                print('header '+Vname+' has an extra dimension. Check that this is intended.') 
        else: 
            Fid[Vname][obs_num,0:N1] = Value
    elif (Ndims == 2):
        N1, N2 = Value.shape
        Fid[Vname][obs_num,0:N1,0:N2] = Value
    elif (Ndims == 3):
        N1, N2, N3 = Value.shape
        Fid[Vname][obs_num,0:N1,0:N2,0:N3] = Value # second dim was N1. Intentional? 
    

###########################################################################
# MAIN
###########################################################################

# Grab input arguemnts
ScriptName = os.path.basename(sys.argv[0])
UsageString = "USAGE: {0:s} <obs_type> <input_prepbufr> <output_netcdf>".format(ScriptName)

#if len(sys.argv) != 4:
#    print("ERROR: must supply exactly 3 arguments")
#    print(UsageString)
#    sys.exit(1)
#ObsType = sys.argv[1]
ObsType = 'Sondes'
#PrepbufrFname = sys.argv[2]
PrepbufrFname = 'prepbufr.gdas.2016030406'
#NetcdfFname = sys.argv[3]
NetcdfFname = 'test.nc4'



print("Converting BUFR to netCDF")
print("  Observation Type: {0:s}".format(ObsType))
print("  Input BUFR file: {0:s}".format(PrepbufrFname))
print("  Output netCDF file: {0:s}".format(NetcdfFname))
print("")

# Set up selection lists
MaxLevels = conf.ObsList[ObsType][0]
MessageRe = conf.ObsList[ObsType][1]
HeadList  = conf.ObsList[ObsType][2]
DataList  = conf.ObsList[ObsType][3]
EventList = conf.ObsList[ObsType][4]

# It turns out that using multiple unlimited dimensions in the netCDF file
# can be very detrimental to the file's size, and can also be detrimental
# to the runtime for creating the file.
#
# In order to mitigate this, we want to use fixed size dimensions instead.
#
# Reading in the dictionary table is fast, but this won't reveal the number of
# observations nor the number of levels in the data. Unfortunately, reading in
# all of the data pieces is slow.
#
# Set the number of levels from the config file (first entry in the ObsList).
#
# MaxEvents will usually be set to 255 due to an array limit in the Fortran
# interface. In practice, there are typically a handful of events (4 or 5) since
# the events are related to the steps that are gone through to convert a raw
# BUFR file to a prepBUFR file (at NCEP). It is generally accepted that 20 is
# a safe limit (instead of 255) for the max number of events, so set MaxEvents
# to 20 to help conserve file space.
#
# MaxStringLen is good with 10 characters. This is the length of the long format
# for date and time. Most of the id labels are 6 or 8 characters.

# Make a pass through the BUFR file to determine the number of observations
print("Finding dimension sizes from BUFR file")
MaxStringLen = 10
MaxEvents = 20
MaxNMsg = 10 # set to < 0 to read all messages
[MaxObs, FilNMsg] = FindNumObsFromBufrFile(PrepbufrFname, MessageRe,MaxNMsg)

print("")

if (MaxNMsg>0): 
    print("  Writing out {} of {} messages".format(MaxNMsg,FilNMsg))
    NMsgRead = MaxNMsg 
else: 
    print("  Writing out all messages" ) 
    NMsgRead = FilNMsg

print("Dimension sizes for output netCDF file")
print("  Maximum number of levels: {}".format(MaxLevels))
print("  Maximum number of events: {}".format(MaxEvents))
print("  Maximum number of characters in strings: {}".format(MaxStringLen))
print("  Maximum number of observations: {}".format(MaxObs))
print("")

# Create the dimensions and variables in the netCDF file in preparation for
# recording the selected observations.
nc = Dataset(NetcdfFname, 'w', format='NETCDF4')

# ReadBurfData will return a 1D array for non events,
# and a 2D array for events.
#
#   Non-event: data[nlevs]
#     nlevs is the nubmer of levels
#
#   Event: data[nlevs, nevents]
#     nlevs is the nubmer of levels
#     nevents is the number of event codes
#
# Each variable will add a dimension (in the front) to hold
# each observation (subset). This results in:
#
#   Non-event: data[nobs,nlevs]
#   Event: data[nobs,nlevs,nevents]
#
NobsDname = "nobs"
NlevsDname = "nlevs"
NeventsDname = "nevents"
StrDname = "nstring"

# dimsensions plus corresponding vars to hold coordinate values
nc.createDimension(NlevsDname, MaxLevels)
nc.createDimension(NeventsDname, MaxEvents)
nc.createDimension(StrDname, MaxStringLen)
nc.createDimension(NobsDname, MaxObs)

# coordinates
#   these are just counts so use unsigned ints
#
# Use chunk sizes that match the dimension sizes. Don't want a total chunk
# size to exceed ~ 1MB, but if that is true, the data size is getting too
# big anyway (a dimension size is over a million items!).
nc.createVariable(NlevsDname, 'u4', (NlevsDname), chunksizes=[MaxLevels])
nc.createVariable(NeventsDname, 'u4', (NeventsDname), chunksizes=[MaxEvents])
nc.createVariable(StrDname, 'u4', (StrDname), chunksizes=[MaxStringLen])
nc.createVariable(NobsDname, 'u4', (NobsDname), chunksizes=[MaxObs])

# variables
MtypeVname = "msg_type"
MtypeDtype = "string"
MdateVname = "msg_date"
MdateDtype = "integer"

CreateNcVar(nc, MtypeVname, 'header', MtypeDtype,
            NobsDname, NlevsDname, NeventsDname, StrDname,
            MaxLevels, MaxEvents, MaxStringLen, MaxObs)
CreateNcVar(nc, MdateVname, 'header', MdateDtype,
            NobsDname, NlevsDname, NeventsDname, StrDname,
            MaxLevels, MaxEvents, MaxStringLen, MaxObs)

for HHname in HeadList:
    CreateNcVar(nc, HHname, 'header', conf.DataTypes[HHname],
                NobsDname, NlevsDname, NeventsDname, StrDname,
                MaxLevels, MaxEvents, MaxStringLen, MaxObs)

for DDname in DataList:
    CreateNcVar(nc, DDname, 'data', conf.DataTypes[DDname],
                NobsDname, NlevsDname, NeventsDname, StrDname,
                MaxLevels, MaxEvents, MaxStringLen, MaxObs)

for EEname in EventList:
    CreateNcVar(nc, EEname, 'event', conf.DataTypes[EEname],
                NobsDname, NlevsDname, NeventsDname, StrDname,
                MaxLevels, MaxEvents, MaxStringLen, MaxObs)

# Make a second pass through the BUFR file, this time to record
# the selected observations.
#
bufr = ncepbufr.open(PrepbufrFname)

NumMsgs= 0
NumSelectedMsgs = 0
NumObs = 0
while ( (bufr.advance() == 0) and (NumSelectedMsgs < NMsgRead)): 
    NumMsgs += 1
    MsgType = np.array(bufr.msg_type)
    MsgDate = np.array([bufr.msg_date])

    # Select only the messages that belong to this observation type
    if (re.search(MessageRe, bufr.msg_type)):
        # Write out obs into the netCDF file as they are read from
        # the BUFR file. Need to start with index zero in the netCDF
        # file so don't increment the counter until after the write.
        while (bufr.load_subset() == 0):
            # Record message type and date with each subset. This is
            # inefficient in storage (lots of redundancy), but is the
            # expected format for now.
            WriteNcVar(nc, NumObs, MtypeVname, 'header', MsgType, MaxStringLen, MaxEvents)
            WriteNcVar(nc, NumObs, MdateVname, 'header', MsgDate, MaxStringLen, MaxEvents)

            for HHname in HeadList:
                [Hval,VarInBufr] = ReadBufrData(bufr, HHname, 'header', conf.DataTypes[HHname])
                if VarInBufr: WriteNcVar(nc, NumObs, HHname, 'header', Hval, MaxStringLen, MaxEvents)

            for DDname in DataList:
                [Dval, VarInBufr] = ReadBufrData(bufr, DDname, 'data', conf.DataTypes[DDname])
                if VarInBufr: WriteNcVar(nc, NumObs, DDname, 'data', Dval, MaxStringLen, MaxEvents)

            for EEname in EventList:
                [Eval, VarInBufr] = ReadBufrData(bufr, EEname, 'event', conf.DataTypes[EEname])
                if VarInBufr: WriteNcVar(nc, NumObs, Ename, 'event', Eval, MaxStringLen, MaxEvents)

            NumObs += 1


        NumSelectedMsgs += 1


# Fill in coordinate values. Simply put in the numbers 1 through N for each
# dimension variable according to that dimension's size.
nc[NobsDname][0:MaxObs]       = np.arange(MaxObs) + 1
nc[NlevsDname][0:MaxLevels]   = np.arange(MaxLevels) + 1
nc[NeventsDname][0:MaxEvents] = np.arange(MaxEvents) + 1
nc[StrDname][0:MaxStringLen]  = np.arange(MaxStringLen) + 1


nc.virtmp_code = bufr.get_program_code('VIRTMP')

print("{0:d} messages selected out of {1:d} total messages".format(NumSelectedMsgs, NumMsgs))
print("  {0:d} observations recorded in output netCDF file".format(MaxObs))


bufr.close()

nc.sync()
nc.close()
