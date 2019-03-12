#! /usr/bin/env python3

import argparse


def parse_args():
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str, help="path to MSA")
    parser.add_argument("start", type=int, help="retained starting position")
    parser.add_argument("stop", type=int, help="retained stop position (exclusive)")

    return parser.parse_args()


def parse_fasta(input_path):
    """ Parse FASTA MSA file """
    entries = dict()

    # Open FASTA file
    active_header = ""
    with open(input_path, "r") as handle:
        for line in handle:
            line = line.rstrip()

            # Check for header or sequence
            if line.startswith(">"):
                active_header = line[1:]
                entries[active_header] = ""
            else:
                entries[active_header] += line

    return entries


args = parse_args()
entries = parse_fasta(args.input)

# Clip entries and print
for entry in entries:
    print(">{}\n{}".format(entry, entries[entry][args.start:args.stop]))
