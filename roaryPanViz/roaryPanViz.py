#!/usr/bin/env python3

# Copyright 2017, Anthony Westbrook <anthony.westbrook@unh.edu>, University of New Hampshire

import sys
import os
import re
import csv
import requests

BATCH = 5000
RETRY = 10
COLUMNS = ['id','go','ec']
UNIPROT_TEMPLATE_INIT = "http://www.uniprot.org/uploadlists/"
UNIPROT_TEMPLATE_JOB = "http://www.uniprot.org/jobs/{0}.stat"
UNIPROT_TEMPLATE_RESULTS = "http://www.uniprot.org/uniprot/?query=job:{0}&format=tab&columns={1}"

# Parse the Gene/Presence definition file (CSV) for metadata, including UniProtKB ID
def parseDefinitions(passFile):
    retDefinitions = dict()

    with open(passFile, 'r') as fileHandle:
        csvReader = csv.reader(fileHandle, delimiter=',', quotechar='"')
        for row in csvReader:
            geneID = row[0]
            geneName = row[2]
            annotation = row[-1]

            # Currently only supports UniProtKB IDs
            result = re.match(".*:UniProtKB:(.*)", annotation)
            if result: 
                retDefinitions[geneID] = (geneName, result.groups()[0])

    return retDefinitions

# Rewrite the contents of the Roary output, inserting in GO/EC terms
def rewriteRoary(passFile, passDefinitions, passUniprot):
    with open(passFile, 'r') as fileHandle:
        csvReader = csv.reader(fileHandle, delimiter="\t")
        header = "name\tgo\tec\t"
        header += "\t".join(next(csvReader)[1:])
        print(header)
        
        for row in csvReader:
            geneID = row[0]
            if geneID in passDefinitions:
                geneName = passDefinitions[geneID][0]
                uniprotID = passDefinitions[geneID][1]

                # Skip unavailable UniProt entries
                if not uniprotID in passUniprot: continue

                # Note terms
                goTerms = passUniprot[uniprotID][0]
                ecTerms = passUniprot[uniprotID][1]

                # Print new information followed by existing p/a data
                print("{0}\t{1}\t{2}\t".format(geneName, goTerms, ecTerms), end='')
                print("\t".join(row[1:]))

# Clean GO and EC terms
def cleanTerms(passUniprot):
    retUniprot = dict()

    for entry in passUniprot:
        # Skip entries with no data
        if not passUniprot[entry]: continue

        # Parse GO terms
        goTerms = ''
        for goRaw in passUniprot[entry][0].split('[GO:')[1:]:
            goTerms += "GO:{0}; ".format(goRaw.split(']')[0])
        goTerms = goTerms[:-2]

        # Parse EC terms
        ecTerms = ''
        if len(passUniprot[entry]) > 1:
            for ecRaw in passUniprot[entry][1].split(';'):
                ecTerms += "EC:{0}; ".format(ecRaw.strip())
            ecTerms = ecTerms[:-2]

        retUniprot[entry] = (goTerms, ecTerms)

    return retUniprot
        
# Retrieve data on the requested reference hits from UniProt
def retrieveData(passEntries):
    retData = dict()

    for batchIdx in range(0, len(passEntries), BATCH):
        # Ready this batch of entries
        batchEntries = ''
        for entryIdx in range(batchIdx, batchIdx + BATCH):
            if entryIdx >= len(passEntries): break
            batchEntries += "{0},".format(passEntries[entryIdx])

        # Construct POST data
        postData = dict()
        postData['uploadQuery'] = batchEntries[:-1]
        postData['format'] = 'job'
        postData['from'] = 'ACC+ID'
        postData['to'] = 'ACC'
        postData['landingPage'] = 'false'

        # Submit batch query, retrieve job ID
        retry = 0
                                                                                                                                                                                                                                             
        while True:
            try:
                endBatch = batchIdx + BATCH
                if endBatch > len(passEntries): endBatch = len(passEntries)

                response = requests.post(UNIPROT_TEMPLATE_INIT, postData)
                jobID = response.text
                response.close()

                # Monitor if job has completed
                url = UNIPROT_TEMPLATE_JOB.format(jobID)
                jobComplete = ''

                while jobComplete != 'COMPLETED':
                    response = requests.post(url)
                    jobComplete = response.text
                    response.close()

                # Fetch data and breakout text
                url = UNIPROT_TEMPLATE_RESULTS.format(jobID, ','.join(COLUMNS))
                response = requests.post(url)

                for line in response.text.split("\n"):
                    line = line.rstrip()
                    fields = line.split("\t")
                    retData[fields[0]] = fields[1:]

                response.close()

                # End retry processing
                break
            except KeyboardInterrupt: raise
            except:
                if retry > RETRY: return ''
                retry += 1

    return retData

# Read definitions from CSV and extract UniProtKB IDs
definitions = parseDefinitions(sys.argv[1])
uniprotIDs = [x[1][1] for x in definitions.items()]

# Retrieve GO and EC terms for these IDs
uniprotRaw = retrieveData(uniprotIDs)
uniprotFull = cleanTerms(uniprotRaw)

# Rewrite Roary output for PanViz
rewriteRoary(sys.argv[2], definitions, uniprotFull)

