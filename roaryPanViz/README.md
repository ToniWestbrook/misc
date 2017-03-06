# Roary to PanViz Utility

Converts the output produced by [Roary](https://sanger-pathogens.github.io/Roary/) into the expected input format required by [PanVizGenerator](https://github.com/thomasp85/PanVizGenerator) for annotations containing UniProtKB IDs in their inference descriptions.

**Note: Features without a UniProtKB ID will not be included in the final output.**

### USAGE

```
roaryPanViz.py <gene_presence_absence.csv> <gene_presence_absence.Rtab>
```

These two files are located in the directory containing Roary's output.  The CSV file contains annotation information related to each gene (with a potential UniProtKB ID), while the Rtab file contains the actual presence/absence matrix to be used by PanViz.  This script will parse the UniProtKB IDs, contact UniProt, and download the associated GO and EC terms for each entry.  These are then used in conjunction with the Rtab file to provide an presence/absence matrix containing GO and EC terms, as expected by PanVizGenerator.
