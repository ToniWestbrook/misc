# Copyright 2017, Anthony Westbrook <anthony.westbrook@unh.edu>, University of New Hampshire

# To install this script as a FIJI macro, perform the following steps:
# 
#    1. From the "Plugins" menu, select "Install..."
#    2. Select this script (weka_percentage.py)
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

HEADER = "Image\tThresholds\tmfMale\tmfFemale\tMale\tFemale\tUndif\tExtra\tMF\tTotal"
RESULTS_FILE = "results.csv"

ROW_MALE = 0
ROW_FEMALE = 1
ROW_UNDIF = 2
ROW_EXTRA = 3
ROW_BACKGROUND = 4
FIELD_IDX = 0
FIELD_AREA = 1
FILE_TYPE = ('male', 'female', 'undif', 'extra', 'background')

def setupMeasurements():
	options = "area"	
	IJ.run("Set Measurements...", options)

def optionsDialog():
	dialog = GenericDialogPlus("Automated Weka Percentages")
	dialog.addDirectoryField("Image Directory", "")
	dialog.addFileField("Training Model", "")
	dialog.addStringField("Output Subdirectory", "output", 20)
	dialog.addStringField("Probability Threshold", "0.75", 20)
	dialog.showDialog()

	# Check if canceled
	if dialog.wasCanceled(): return None

	textVals = [x.text for x in dialog.getStringFields()]
	#boolVals = [x.getState() for x in dialog.getCheckboxes()]

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

def analyzeImage(passImage, passModel, passProbability, passOutput):
	retResults = list()

	# Apply weka training model to image
	wekaSeg = WekaSegmentation(passImage)
	wekaSeg.loadClassifier(passModel)
	wekaSeg.applyClassifier(True)

	# Extract probability map
	wekaImg = wekaSeg.getClassifiedImage();
	wekaImg.show()
	IJ.run("Clear Results")

	# Process each slice
	for sliceIdx in range(ROW_BACKGROUND + 1):
		# Select slice and duplicate
		IJ.selectWindow("Probability maps")
		IJ.setSlice(sliceIdx + 1)
		IJ.run("Duplicate...", "title=temp")
		
		# Apply threshold to probability
		IJ.setThreshold(passProbability, 1, "Black & White")

		# For background, take inverse
		if sliceIdx == ROW_BACKGROUND: IJ.run("Invert")
		
		# Change background to NaN for area, then measure
		IJ.run("NaN Background", ".")
		IJ.run("Measure")

		# Save image to output directory
		fileParts = passImage.getTitle().split(".")
		IJ.save(os.path.join(passOutput, "{0}-{1}.{2}".format(fileParts[0], FILE_TYPE[sliceIdx], '.'.join(fileParts[1:]))))

		IJ.selectWindow("temp")
		IJ.run("Close")

	# Close probability maps
	IJ.selectWindow("Probability maps")
	IJ.run("Close")
		
	# Obtain results
	tempResults = list()
	tableResults = ResultsTable.getResultsTable()
	for rowIdx in range(tableResults.size()):		
		tempResults.append([float(x) for x in tableResults.getRowAsString(rowIdx).split()])

	# Compile image statistics as M/(M+F), F/(M+F), M/total, F/total, U/total, E/total, M+F, total
	mfTotal = tempResults[ROW_MALE][FIELD_AREA] + tempResults[ROW_FEMALE][FIELD_AREA]
	total = tempResults[ROW_BACKGROUND][FIELD_AREA]
	
	retResults.append(tempResults[ROW_MALE][FIELD_AREA]/mfTotal)
	retResults.append(tempResults[ROW_FEMALE][FIELD_AREA]/mfTotal)
	retResults.append(tempResults[ROW_MALE][FIELD_AREA]/total)
	retResults.append(tempResults[ROW_FEMALE][FIELD_AREA]/total)
	retResults.append(tempResults[ROW_UNDIF][FIELD_AREA]/total)
	retResults.append(tempResults[ROW_EXTRA][FIELD_AREA]/total)
	retResults.append(mfTotal)
	retResults.append(total)
	
	return retResults
	
def processImages(passOptions):
	optImageDir = passOptions[0]
	optModel = passOptions[1]
	optOutput = passOptions[2]
	optProbability = float(passOptions[3])

	retResults = dict()
	
	# Iterate through all images in chosen directory
	root, dirs, files = next(os.walk(optImageDir))
	for curFile in files:
		# Prepare image
		curImage = prepareImage(root, curFile)
		if not curImage: continue

		# Analyze image
		retResults[curFile] = analyzeImage(curImage, optModel, optProbability, os.path.join(options[0], optOutput))

		# Close image
		finalizeImage(curImage)

	return retResults

def writeResults(passResults, passOutput, passProbability):
	# Create results TSV
	with open(passOutput, "w") as fileHandle:
		fileHandle.write("{0}\n".format(HEADER))
		
		for image in passResults:	
			fieldText = "\t".join(map(str, passResults[image]))
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
