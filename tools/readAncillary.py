#!/usr/bin/python

#=============================================================================
# functions that support table and YAML usage with BUFR files
#
# 08/24/2020   Jeffrey Smith          initial version
#=============================================================================

import collections
import os.path
import re
import sys
import yaml

#from marineprofile_consts import *

# Patterns for searching
SECTION1_PATTERN = "\|.{10}\|.{8}\|.{58}\|"
SECTION2_PATTERN = "\|.{10}\|.{67}\|"
SECTION3_PATTERN = "\|.{10}\|.{6}\|.{13}\|.{5}\|.{26}\|-{13}\|"
DEFINED_MNEMONIC_PATTERN = "^\| [A-Z|0-9]{3,}"
DELAYED_REP_PATTERN = "\{|\(|\<[A-Z|0-9]{3,}"
REGULAR_REP_PATTERN = "\"[A-Z|0-9]{3,}\"\d{1,}"

# exception for BUFR files/tables
class BUFRTableError(Exception):
    def __init__(self, message):
        self.message = "BUFRTableError: %s" % (message,)
        return

# exception for .dict files
class YAMLFileError(Exception):
    def __init__(self, message):
        self.message = "YAMLFileError: %s" % (message,)
        return

# class (used like a C struct) for nodes in a tree for mnemonics from
# a BUFR table
class MnemonicNode:
    def __init__(self, name, seq, parent, seqIndex):
        """ contructor

            Input:
                name - mnemonic name
                seq - True if the mnemonic is a sequence, False otherwise
                parent - the MnemonicNode for the current mnemonic's parent
                seqIndex - if the parent is a sequence mnemonic, the position
                           in the list of children
        """

        self.name = name
        self.seq = seq
        self.parent = parent
        self.seq_index = seqIndex
        self.children = []
        return


def readTable(tableFileName):
    """ reads a .tbl file

        Input:
            tableFileName - full path name of the .tbl file

        Return:
            list of lines from the table
    """

    if not os.path.isfile(tableFileName):
        raise BUFRTableError("Table file %s was not found\n" % 
                             (tableFileName,))

    with open(tableFileName, 'r') as fd:
        tblLines = fd.read().split('\n')

    return tblLines


def parseTable(tblLines):
    """ parses an NCEP BUFR table.

        Input:
            tblLines - list containing the lines of an NCEP BUFR table

        Return:
            3 ordered dictionaries containing the information for the 3
            tables contained in a .tbl file
    """

    section1 = collections.OrderedDict()
    section2 = collections.OrderedDict()
    section3 = collections.OrderedDict()

    idx = 0
    try:
        # skip to the first line of information from Section 1.
        while not re.search(SECTION1_PATTERN, tblLines[idx]):
            idx += 1

        # fill in dictionary of Section 1 values
        while re.search(SECTION1_PATTERN, tblLines[idx]):
            if re.search(DEFINED_MNEMONIC_PATTERN, tblLines[idx]) and \
               not ("MNEMONIC" in tblLines[idx]):
                fields = tblLines[idx].split('|')
                section1[fields[1].strip()] = fields[3].strip()
            idx += 1

        # skip to the first line of information from Section 2
        while not re.search(SECTION2_PATTERN, tblLines[idx]):
            idx += 1

        # fill in dictionary of Section 2 values
        currentKey = ""
        while re.search(SECTION2_PATTERN, tblLines[idx]):
            if re.search(DEFINED_MNEMONIC_PATTERN, tblLines[idx]) and \
               not ("MNEMONIC" in tblLines[idx]):
                fields = tblLines[idx].split('|')
                parts = fields[2].split()
                if fields[1].strip() == currentKey:
                    section2[currentKey].extend(parts)
                else:
                    currentKey = fields[1].strip()
                    section2[currentKey] = parts
            idx += 1

        # skip to the first line of information from Section 3.
        while not re.search(SECTION3_PATTERN, tblLines[idx]):
            idx += 1

        # fill in dictionary of Section 3 values
        while re.search(SECTION3_PATTERN, tblLines[idx]):
            if re.search(DEFINED_MNEMONIC_PATTERN, tblLines[idx]) and \
               not ("MNEMONIC" in tblLines[idx]):
                fields = tblLines[idx].split('|')
                section3[fields[1].strip()] \
                    = {"scale":float(fields[2].strip()),
                       "reference":float(fields[3].strip()),
                       "num_bits":int(fields[4].strip()),
                       "units":fields[5].strip()}
            idx += 1

    except IndexError:
        # Didn't find a proper end line, so assume that there is something
        # wrong with the file
        #raise BUFRTableError("Program failed to read table file %s\n" % \
                             #(tableFileName,))
        raise BUFRTableError("Program did not find proper table\n")

    return (section1, section2, section3)


def readYAMLFile(yamlFile):
    """ reads a .dict file

    Input:
        name of the .dict file

    Return:
        a dictionary containing the information from the .dict file. The
        mnemonics are the keys in the dictionary
    """

    if os.path.isfile(yamlFile):
        with open(yamlFile, 'r') as fd:
            yamlDict = yaml.safe_load(fd)
    else:
        yamlDict = None
        raise YAMLFileError("YAML file %s could not be read." % (yamlFile,))

    return yamlDict


def getMnemonicList(obsType, section2, parentsToPrune=[], leavesToPrune=[]):
    """ returns a list of the mnemonics that can be extracted from a BUFR
        file for a specific observation type

        Input:
            obsType - observation type (e.g., "NC031001") or parent key
            section2 - dictionary containing Section 2 from a .tbl file
            parentsToPrune - list of mnemonic objects for nodes that
                             are parents, so that the node and all its
                             descendents are pruned
            leavesToPrune - list for pruning mnemonics that are leaves.
                            Each element is a list that contains the Menomic
                            objects for the leaf and its parent (so that
                            mnemonics with duplicate names can be differinated)

        Return:
            list of mnemonics that will be output
    """

    # need to create a root node for a tree
    treeTop = MnemonicNode(obsType, False, None, 0)

    buildMnemonicTree(treeTop, section2)
    if parentsToPrune or leavesToPrune:
        status = pruneTree(treeTop, parentsToPrune, leavesToPrune)
    mnemonicList = findSearchableNodes(treeTop)

    return mnemonicList


def buildMnemonicTree(root, section2):
    """ builds a hierarchical tree for the mnemonics for a given observation 
        type

        Input:
            root - root node for segment of tree to process
            section2 - dictionary containing Section 2 from a .tbl file

        Return:
            list of mnemonics that will be output
    """

    mnemonicsForID = section2[root.name]
    for m in mnemonicsForID:
        if re.search(DELAYED_REP_PATTERN, m):
            m = m[1:-1]
            seq = True
        elif re.search(REGULAR_REP_PATTERN, m):
            m = m[1:-2]
            seq = True
        elif m[0] == '.':
            # don't know how to handle mnemonics beginning with a .
            continue
        else:
            seq = False

        node = MnemonicNode(m, seq, root, len(root.children))

        if m in section2.keys():
            # if m is a key then it is a parent, so get its members
            root.children.append(node)
            buildMnemonicTree(node, section2)
        else:
            # not a parent, so it is a field name.
            root.children.append(node)

    return 


def findSearchableNodes(root):
    """ finds the nodes that reference a mnemonic that can be retrieved
        from a BUFR file. These nodes are the leaves except when a node
        that is a sequence is a parent of 1 or more leaves.

        Input:
            root - the root node of the tree to search

        Return:
            a list of nodes that reference mnemonics that can be retrieved
            from a BUFR file
    """

    nodeList = []

    if len(root.children) > 0:
        # root is not a leaf so visit its children
        for node in root.children:
            nodeList.extend(findSearchableNodes(node))
    else:
        # a leaf, so it is added to the list unless its parent is a sequence,
        # in which case its parent is added
        if root.parent.seq:
            nodeList.append(root.parent)
        else:
            nodeList.append(root)

    # remove duplicates (will happen if leaf nodes share a parent that is
    # a sequence)
    nodeList = [x for i,x in enumerate(nodeList) if not x in nodeList[:i]
                or not x.seq]

    return nodeList


def traverseMnemonicTree(root):
    """ returns the leaves of a mnemonic tree by performing a standard
        tree traversal

        Input:
            root - root node of the tree to traverse

        Return:
            list of leaves in the tree (MnemonicNode objects)
    """

    leafList = []

    if len(root.children) > 0:
        for node in root.children:
            leafList.extend(traverseMnemonicTree(node))
    else:
        leafList.append(root)

    return leafList


def pruneTree(root, parentsToPrune, leavesToPrune):
    """ prunes nodes from a tree of Mnemonics. An entire subtree can be
        pruned (mnemonic object for top of subtree in parentsToPrune) or
        individual leaves can be pruned (from leavesToPrune).

        Input:
            root - root node of the tree
            parentsToPrune - list of mnemonic objects for nodes that
                             are parents, so that the node and all its
                             descendents are pruned
            leavesToPrune - list for pruning mnemonics that are leaves.
                            Each element is a list that contains the Menomic
                            objects for the leaf and its parent (so that
                            mnemonics with duplicate names can be differinated)

        Return:
            True if root and its descendants were pruned, False otherwise
    """


    pruned = False

    if root.name in parentsToPrune:
        idx = 0
        while idx < len(root.children):
            # if the field is a sequence, prune all its children
            if root.children[idx].seq:
                # if the child is a sequence, add its name to the list
                # of sequences to prune
                pruned = pruneTree(root.children[idx],
                                   [x for x in parentsToPrune or
                                    x in root.children[idx].name],
                                   leavesToPrune)
            else:
                # child is not a sequence, so add its name and parent's
                # name to list of leaves to prune
                pruned = pruneTree(root.children[idx], parentsToPrune,
                                   [x for x in leavesToPrune or
                                    x in [root.children[idx].name, root.name]])
            if not pruned:
                idx += 1
        root.parent.children.remove(root)
        pruned = True
    elif root.parent and (root.name, root.parent.name) \
         in [(x[0], x[1]) for x in leavesToPrune]:
        # first clause handles when root is the root of the entire tree
        root.parent.children.remove(root)
        pruned = True
    else:
        # node is not in prune list but if it has any children then
        # process the children
        idx = 0
        while idx < len(root.children):
            pruned = pruneTree(root.children[idx], parentsToPrune,
                               leavesToPrune)
            if not pruned:
                idx += 1
        
    return pruned


def addNamesForNetCDF(outputVarList, yamlDict):
    """ changes spaces and slashes in the name field to underscores
        so that they can be used as netCDF variable names

        Input:
            outputVarList - list of mnemonics of fields written to output file
            yamlDict - a dictionary created from reading a .dict file

        Return:
            dictionary that maps mnemonics of output fields to the netCDF
            variable names for the fields
    """

    netCDFNameDict = {}
    for v in outputVarList:
        netCDFNameDict[v] = yamlDict[v]["name"].lower()
        netCDFNameDict[v] = netCDFNameDict[v].replace(' ', '_')
        netCDFNameDict[v] = netCDFNameDict[v].replace('/', '_')

    return netCDFNameDict
