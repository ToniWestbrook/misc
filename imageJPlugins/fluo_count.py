# Copyright 2017, Anthony Westbrook <anthony.westbrook@unh.edu>, University of New Hampshire

# To install this script as a FIJI macro, perform the following steps:
#
#    1. From the "Plugins" menu, select "Install..."
#    2. Select this script (fluo_count.py)
#    3. Accept the default installation directory
#    4. Restart FIJI
#    5. The plugin will be available to run from the "Plugins" menu at the bottom

from ij import IJ, WindowManager                                                                                                                                                                                                                                                                     
from ij.measure import ResultsTable
from fiji.util.gui import GenericDialogPlus
from trainableSegmentation import WekaSegmentation
import math
import sys
import os

HEADER = "File\tProbability\tCell\tArea\tPerimeter\tCircularity\tAspectRatio\tRoundness\tSolidity"
RESULTS_FILE = "results.csv"

def setupMeasurements():                                                                                                                                                                                                                                                                             
	options = "area perimeter shape roundness"        
	IJ.run("Set Measurements...", options)
        
def optionsDialog():
	dialog = GenericDialogPlus("Fluorescent Cell Counting")
	dialog.addDirectoryField("Image Directory", "")
	dialog.addFileField("Training Model", "")
	dialog.addStringField("Output Subdirectory", "output", 20)
	dialog.addStringField("Probability Threshold", "0.67", 20)
	dialog.addStringField("Minimum Pixel Size", "2", 20)
	dialog.showDialog()
	
	# Check if canceled
	if dialog.wasCanceled(): return None
	
	textVals = [x.text for x in dialog.getStringFields()]
	
	return textVals

def prepareImage(passDir, passFile):
	# Attempt to open as image, exit if not
	fullPath = os.path.join(passDir, passFile)
	retImage = IJ.openImage(fullPath)
	if not retImage: return None
	retImage.show()
	
	return retImage

def finalizeImage(passImage):
	passImage.changes = False
	passImage.close()

def analyzeImage(passImage, passModel, passProbability, passPixels, passOutput):
	retResults = list()

	# Apply WEKA training model to image
	wekaSeg = WekaSegmentation(passImage)
	wekaSeg.loadClassifier(passModel)
	wekaSeg.applyClassifier(True)

	# Extract first slice of probability map
	wekaImg = wekaSeg.getClassifiedImage();
	wekaImg.show()
	
	IJ.selectWindow("Probability maps")
	IJ.setSlice(1)
	IJ.run("Duplicate...", "title=temp")

	# Apply threshold and save
	IJ.setThreshold(passProbability, 1, "Black & White")
	fileParts = passImage.getTitle().split(".")
	IJ.save(os.path.join(passOutput, "{0}-probmap.png".format(fileParts[0], '.'.join(fileParts[1:]))))

	# Perform particle analysis and save
	IJ.run("Analyze Particles...", "size={0}-Infinity show=Outlines pixel clear".format(passPixels))
	IJ.selectWindow("Drawing of temp")
	IJ.save(os.path.join(passOutput, "{0}-particles.png".format(fileParts[0], '.'.join(fileParts[1:]))))
	
    # Get measurements (skip final row, this will correspond to legend)
	tableResults = ResultsTable.getResultsTable()
	for rowIdx in range(tableResults.size() - 1):
		retResults.append(tableResults.getRowAsString(rowIdx).split())

	# Close interim windows		
	IJ.run("Close")
	IJ.selectWindow("temp")
	IJ.run("Close")
	IJ.selectWindow("Probability maps")
	IJ.run("Close")
    	
	return retResults

def processImages(passOptions):
	optImageDir = passOptions[0]
	optModel = passOptions[1]
	optOutput = passOptions[2]
	optProbability = 1.0 - float(passOptions[3])
	optPixels = int(passOptions[4])

	retResults = dict()
	
	# Iterate through all images in chosen directory
	root, dirs, files = next(os.walk(optImageDir))
	for curFile in files:
		# Prepare image
		curImage = prepareImage(root, curFile)
		if not curImage: continue
		
		# Analyze image
		retResults[curFile] = analyzeImage(curImage, optModel, optProbability, optPixels, os.path.join(options[0], optOutput))
		
		# Close image
		finalizeImage(curImage)                                                                                                                                                                                                                                                              
	
	return retResults

def writeResults(passResults, passOutput, passProbability):
	# Create results TSV
	with open(passOutput, "w") as fileHandle:
		fileHandle.write("{0}\n".format(HEADER))
		
		for image in passResults:
			for row in passResults[image]:
				fieldText = "\t".join(map(str, row))
				fileHandle.write("{0}\t{1}\t{2}\n".format(image, passProbability, fieldText))
			

# Setup measurements to record in CSV
setupMeasurements()

# Present user definable options, then process
options = optionsDialog()
if options:
	# Prepare output directory
	if not os.path.exists(os.path.join(options[0], options[2])):
		os.makedirs(os.path.join(options[0], options[2]))
	
	# Analyze images
	results = processImages(options)
	writeResults(results, os.path.join(options[0], options[2], RESULTS_FILE), options[3])
	IJ.showMessage("Analysis Complete!")        
